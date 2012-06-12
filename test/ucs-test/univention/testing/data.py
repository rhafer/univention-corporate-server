import sys
from os import uname
import os.path
from univention.config_registry import ConfigRegistry
import yaml
from univention.testing.codes import TestCodes
from univention.testing.utils import UCSVersion
from univention.testing.errors import TestConditionError
from operator import and_, or_
from subprocess import call, Popen, PIPE, STDOUT
import apt
from time import time
import logging
import signal
import select
import errno
try: # >= Python 2.5
	from hashlib import md5
except ImportError:
	from md5 import new as md5

__all__ = ['TestEnvironment', 'TestCase', 'TestResult']

class TestEnvironment(object):
	logger = logging.getLogger('test.env')

	def __init__(self, interactive=True, logfile=None):
		self.exposure = 'safe'
		self.interactive = interactive

		self._load_host()
		self._load_ucr()
		self._load_join()
		self._load_apt()

		if interactive:
			self.tags_required = None
			self.tags_prohibited = None
		else:
			self.tags_required = set()
			self.tags_prohibited = set(('SKIP', 'WIP'))

		self.log = open(logfile or os.path.devnull, 'a')

	def _load_host(self):
		(sysname, nodename, release, version, machine) = uname()
		self.hostname = nodename
		self.architecture = machine

	def _load_ucr(self):
		self.ucr = ConfigRegistry()
		self.ucr.load()
		self.role = self.ucr.get('server/role', '')
		TestEnvironment.logger.debug('Role=%r' % self.role)

		major, minor = map(int, self.ucr.get('version/version').split('.', 1))
		patchlevel = int(self.ucr.get('version/patchlevel'))
		if (major, minor) < (3, 0):
			securitylevel = int(self.ucr.get('version/security-patchlevel', 0))
			self.ucs_version = UCSVersion((major, minor, patchlevel, securitylevel))
		else:
			erratalevel = int(self.ucr.get('version/erratalevel', 0))
			self.ucs_version = UCSVersion((major, minor, patchlevel, erratalevel))
		TestEnvironment.logger.debug('Version=%r' % self.ucs_version)

	def _load_join(self):
		devnull = open(os.path.devnull, 'w+')
		try:
			ret = call(('/usr/sbin/univention-check-join-status',), stdin=devnull, stdout=devnull, stderr=devnull)
			self.joined = ret == 0
		finally:
			devnull.close()
		TestEnvironment.logger.debug('Join=%r' % self.joined)

	def _load_apt(self):
		self.apt = apt.Cache()

	def dump(self, stream=sys.stdout):
		print >>stream, 'hostname: %s' % (self.hostname,)
		print >>stream, 'architecture: %s' % (self.architecture,)
		print >>stream, 'version: %s' % (self.ucs_version,)
		print >>stream, 'role: %s' % (self.role,)
		print >>stream, 'joined: %s' % (self.joined,)
		print >>stream, 'tags_required: %s' % (' '.join(self.tags_required) or '-',)
		print >>stream, 'tags_prohibited: %s' % (' '.join(self.tags_prohibited) or '-',)

	def tag(self, require=set(), ignore=set(), prohibit=set()):
		"""Update required, ignored, prohibited tags."""
		if self.tags_required is not None:
			self.tags_required -= set(ignore)
			self.tags_required |= set(require)
		if self.tags_prohibited is not None:
			self.tags_prohibited -= set(ignore)
			self.tags_prohibited |= set(prohibit)
		TestEnvironment.logger.debug('tags_required=%r tags_prohibited=%r' % (self.tags_required, self.tags_prohibited))

	def set_exposure(self, exposure):
		self.exposure = exposure

class _TestReader(object):
	"""
	Read test case header lines starting with ##.
	"""
	def __init__(self, stream, digest):
		self.stream = stream
		self.digest = digest

	def read(self, size=-1):
		while True:
			line = self.stream.readline(size)
			if not line:
				return '' # EOF
			if line.startswith('## '):
				return line[3:]
			while line:
				self.digest.update(line)
				line = self.stream.readline(size)

class Verdict(object):
	"""
	Result of a test, either successful or failed.
	"""
	INFO = 0 # Successful check, continue
	WARNING = 1 # Non-critical condition, may continue
	ERROR = 2 # Critical contion, abort

	logger = logging.getLogger('test.cond')

	def __init__(self, level, message, reason=None):
		self.level = level
		self.message = message
		self.reason = reason
		Verdict.logger.debug(self)

	def __nonzero__(self):
		return self.level < Verdict.ERROR

	def __str__(self):
		return '%s: %s' % ('IWE'[self.level], self.message)

	def __repr__(self):
		return '%s(level=%r, message=%r)' % (self.__class__.__name__, self.level, self.message)

class Check(object):
	"""
	Abstract check.
	"""
	def check(self, environment):
		raise NotImplemented()

class CheckExecutable(Check):
	"""
	Check language.
	"""
	def __init__(self, filename):
		self.filename = filename

	def check(self, environment):
		if not os.path.isabs(self.filename):
			if self.filename.startswith('python'):
				self.filename = '/usr/bin/' + self.filename
			elif self.filename.endswith('sh'):
				self.filename = '/bin/' + self.filename
			else:
				yield Verdict(Verdict.ERROR, 'Unknown executable: %s' % (self.filename,), TestCodes.REASON_INSTALL)
				return
		if os.path.isfile(self.filename):
			yield Verdict(Verdict.INFO, 'Executable: %s' % (self.filename,))
		else:
			yield Verdict(Verdict.ERROR, 'Missing executable: %s' % (self.filename,), TestCodes.REASON_INSTALL)

	def __str__(self):
		return self.filename

class CheckVersion(Check):
	"""
	Check expected result of test for version.
	"""
	STATES = frozenset(('found', 'fixed', 'skip', 'run'))

	def __init__(self, versions):
		self.versions = versions
		self.state = 'run'

	def check(self, environment):
		versions = []
		for version, state in self.versions.items():
			ucs_version = UCSVersion(version)
			if state not in CheckVersion.STATES:
				yield Verdict(Verdict.WARNING, 'Unknown state "%s" for version "%s"' % (state, version))
				continue
			versions.append((ucs_version, state))
		versions.sort()
		for (ucs_version, state) in versions:
			if ucs_version <= environment.ucs_version:
				self.state = state
		if self.state == 'skip':
			yield Verdict(Verdict.INFO, 'Skipped for version %s' % (environment.ucs_version,), TestCodes.REASON_VERSION_MISMATCH)

class CheckTags(Check):
	"""
	Check for required / prohibited tags.
	"""
	def __init__(self, tags):
		self.tags = set(tags)

	def check(self, environment):
		if environment.tags_required is None or environment.tags_prohibited is None:
			yield Verdict(Verdict.INFO, 'Tags disabled')
			return
		prohibited = self.tags & environment.tags_prohibited
		if prohibited:
			yield Verdict(Verdict.ERROR, 'De-selected by tag: %s' % (' '.join(prohibited),), TestCodes.REASON_ROLE_MISMATCH)
		elif environment.tags_required:
			required = self.tags & environment.tags_required
			if required:
				yield Verdict(Verdict.INFO, 'Selected by tag: %s' % (' '.join(required),))
			else:
				yield Verdict(Verdict.ERROR, 'De-selected by tag: %s' % (' '.join(environment.tags_required),), TestCodes.REASON_ROLE_MISMATCH)

class CheckRoles(Check):
	"""
	Check server role.
	"""
	ROLES = frozenset(('domaincontroller_master', 'domaincontroller_backup', 'domaincontroller_slave', 'memberserver', 'basesystem', 'mobileclient', 'fatclient', 'managedclient', 'thinclient'))

	def __init__(self, roles_required=[], roles_prohibited=[]):
		self.roles_required = set(roles_required)
		self.roles_prohibited = set(roles_prohibited)

	def check(self, environment):
		overlap = self.roles_required & self.roles_prohibited
		if overlap:
			yield Verdict(Verdict.WARNING, 'Overlapping roles: %s' % (' '.join(overlap),))
			roles = self.roles_required - self.roles_prohibited
		elif self.roles_required:
			roles = set(self.roles_required)
		else:
			roles = CheckRoles.ROLES - set(self.roles_prohibited)

		unknown_roles = roles - CheckRoles.ROLES
		if unknown_roles:
			yield Verdict(Verdict.WARNING, 'Unknown roles: %s' % (' '.join(unknown_roles),))

		if environment.role not in roles:
			yield Verdict(Verdict.ERROR, 'Wrong role: %s not in (%s)' % (environment.role, ','.join(roles)), TestCodes.REASON_ROLE_MISMATCH)

class CheckJoin(Check):
	"""
	Check join status.
	"""
	def __init__(self, joined):
		self.joined = joined

	def check(self, environment):
		if self.joined is None:
			yield Verdict(Verdict.INFO, 'No required join status')
		elif self.joined and not environment.joined:
			yield Verdict(Verdict.ERROR, 'Test requires system to be joined', TestCodes.REASON_JOIN)
		elif not self.joined and environment.joined:
			yield Verdict(Verdict.ERROR, 'Test requires system to be not joined', TestCodes.REASON_JOINED)
		else:
			yield Verdict(Verdict.INFO, 'Joined: %s' % (environment.joined,))

class CheckComponents(Check):
	"""
	Check for required / prohibited components.
	"""
	def __init__(self, components):
		self.components = components

	def check(self, environment):
		for component, required in self.components.items():
			key = 'repository/online/component/%s' % (component,)
			active = environment.ucr.is_true(key, False)
			if required:
				if active:
					yield Verdict(Verdict.INFO, 'Required component %s active' % (component,))
				else:
					yield Verdict(Verdict.ERROR, 'Required component %s missing' % (component,), TestCodes.REASON_INSTALL)
			else: # not required
				if active:
					yield Verdict(Verdict.ERROR, 'Prohibited component %s active' % (component,), TestCodes.REASON_INSTALLED)
				else:
					yield Verdict(Verdict.INFO, 'Prohibited component %s not active' % (component,))

class CheckPackages(Check):
	"""
	Check for required packages.
	"""
	def __init__(self, packages):
		self.packages = packages

	def check(self, environment):
		def check_disjunction(conjunction):
			for name, dep_version, dep_op in conjunction:
				try:
					pkg = environment.apt[name]
				except KeyError:
					yield Verdict(Verdict.ERROR, 'Package %s not found' % (name,), TestCodes.REASON_INSTALL)
					continue
				ver = pkg.installed
				if ver is None:
					yield Verdict(Verdict.ERROR, 'Package %s not installed' % (name,), TestCodes.REASON_INSTALL)
					continue
				if dep_version and not apt.apt_pkg.CheckDep(ver.version, dep_op, dep_version):
					yield Verdict(Verdict.ERROR, 'Package %s version mismatch' % (name,), TestCodes.REASON_INSTALL)
					continue
				yield Verdict(Verdict.INFO, 'Package %s installed' % (name,))
				break

		for dependency in self.packages:
			deps = apt.apt_pkg.ParseDepends(dependency)
			for conjunction in deps:
				conditions = list(check_disjunction(conjunction))
				success = reduce(or_, map(bool, conditions), False)
				if success:
					for condition in conditions:
						if condition.level < Verdict.ERROR:
							yield condition
				else:
					for condition in conditions:
						yield condition

class CheckExposure(Check):
	"""
	Check for signed exposure.
	"""
	STATES = ['safe', 'careful', 'dangerous']

	def __init__(self, exposure, digest):
		self.exposure = exposure
		self.digest = digest

	def check(self, environment):
		exposure = 'DANGEROUS'
		try:
			exposure, expected_md5 = self.exposure.split(None, 1)
		except ValueError, e:
			exposure = self.exposure
		else:
			current_md5 = self.digest.hexdigest()
			if current_md5 != expected_md5:
				yield Verdict(Verdict.ERROR, 'MD5 mismatch: %s' % (current_md5,))
			else:
				yield Verdict(Verdict.INFO, 'MD5 matched: %s' % (current_md5,))
		if exposure not in CheckExposure.STATES:
			yield Verdict(Verdict.WARNING, 'Unknown exposure: %s' % (exposure,))
			return
		if CheckExposure.STATES.index(exposure) > CheckExposure.STATES.index(environment.exposure):
			yield Verdict(Verdict.ERROR, 'Too dangerous: %s > %s' % (exposure, environment.exposure), TestCodes.REASON_DANGER)
		else:
			yield Verdict(Verdict.INFO, 'Safe enough: %s <= %s' % (exposure, environment.exposure))

class TestCase(object):
	logger = logging.getLogger('test.case')

	def __init__(self):
		self.exe = None
		self.args = []
		self.filename = None
		self.id = None
		self.description = None
		self.bugs = set()
		self.otrs = set()

	def load(self, filename):
		"""
		Load test case from stream.
		"""
		TestCase.logger.info('Loading test %s' % (filename,))
		digest = md5()
		f = open(filename, 'r')
		try:
			firstline = f.readline()
			if not firstline.startswith('#!'):
				raise ValueError('Missing hash-bang')
			args = firstline.split(None)
			try:
				lang = args[1]
			except IndexError, e:
				lang = ''
			self.exe = CheckExecutable(lang)
			self.args = args[2:]

			digest.update(firstline)
			r = _TestReader(f, digest)
			d = yaml.load(r) or {}
		finally:
			f.close()

		self.filename = os.path.abspath(filename)
		self.id = os.path.sep.join(self.filename.rsplit(os.path.sep, 2)[-2:])

		self.description = d.get('desc', '').strip()
		self.bugs = set(d.get('bugs', []))
		self.otrs = set(d.get('otrs', []))
		self.versions = CheckVersion(d.get('versions', {}))
		self.tags = CheckTags(d.get('tags', []))
		self.roles = CheckRoles(d.get('roles', []), d.get('roles-not', []))
		self.join = CheckJoin(d.get('join', None))
		self.components = CheckComponents(d.get('components', {}))
		self.packages = CheckPackages(d.get('packages', []))
		self.exposure = CheckExposure(d.get('exposure', 'dangerous'), digest)

		return self

	def check(self, environment):
		"""
		Check if the test case should run.
		"""
		TestCase.logger.info('Checking test %s' % (self.filename,))
		conditions = []
		conditions += list(self.exe.check(environment))
		conditions += list(self.versions.check(environment))
		conditions += list(self.tags.check(environment))
		conditions += list(self.roles.check(environment))
		conditions += list(self.components.check(environment))
		conditions += list(self.packages.check(environment))
		conditions += list(self.exposure.check(environment))
		return conditions

	def run(self, result):
		"""Run the test case and fill in result."""
		base = os.path.basename(self.filename)
		dir = os.path.dirname(self.filename)
		cmd = [self.exe.filename, base] + self.args

		time_start = time()

		# Protect wrapper from Ctrl-C as long as test case is running
		def handle_int(signal, frame):
			result.result = TestCodes.RESULT_SKIP
			result.reason = TestCodes.REASON_ABORT
		old_sig_int = signal.signal(signal.SIGINT, handle_int)
		def prepare_child():
			signal.signal(signal.SIGINT, signal.SIG_IGN)
		try:
			TestCase.logger.debug('Running %r using %s in %s' % (cmd, self.exe, dir))
			try:
				print >>result.environment.log, '*** BEGIN *** %r ***' % (cmd,)
				result.environment.log.flush()
				if result.environment.interactive:
					p = Popen(cmd, executable=self.exe.filename, stdout=PIPE, stderr=PIPE, close_fds=True, shell=False, cwd=dir)
					to_stdout, to_stderr = sys.stdout, sys.stderr
				else:
					devnull = open(os.path.devnull, 'r')
					try:
						p = Popen(cmd, executable=self.exe.filename, stdin=devnull, stdout=PIPE, stderr=PIPE, close_fds=True, shell=False, cwd=dir, preexec_fn=prepare_child)
					finally:
						devnull.close()
					to_stdout = to_stderr = result.environment.log

				log_stdout, log_stderr = [], []
				fd_stdout, fd_stderr = p.stdout.fileno(), p.stderr.fileno()
				read_set = [fd_stdout, fd_stderr]
				while read_set:
					try:
						rlist, wlist, elist = select.select(read_set, [], [])
					except select.error, e:
						if e.args[0] == errno.EINTR:
							continue
						raise
					if fd_stdout in rlist:
						data = p.stdout.read(1024)
						if data == '':
							read_set.remove(fd_stdout)
							p.stdout.close()
						else:
							to_stdout.write(data)
							log_stdout.append(data)
					if fd_stderr in rlist:
						data = p.stderr.read(1024)
						if data == '':
							read_set.remove(fd_stderr)
							p.stderr.close()
						else:
							to_stderr.write(data)
							log_stderr.append(data)
				result.result = p.wait()
				print >>result.environment.log, '*** END *** %d ***' % (result.result,)
				result.environment.log.flush()
			except OSError, e:
				TestCase.logger.error('Failed to execute %r using %s in %s' % (cmd, self.exe, dir))
				raise
		finally:
			signal.signal(signal.SIGINT, old_sig_int)
			if result.reason == TestCodes.REASON_ABORT:
				raise KeyboardInterrupt()

		time_end = time()

		result.duration = int(time_end * 1000.0 - time_start * 1000.0)
		TestCase.logger.info('Test %r using %s in %s returned %s in %s ms' % (cmd, self.exe, dir, result.result, result.duration))
		if log_stdout:
			result.attach('stdout', 'text/plain', ''.join(log_stdout))
		if log_stderr:
			result.attach('stderr', 'text/plain', ''.join(log_stderr))
		if result.result == TestCodes.RESULT_OKAY:
			result.reason = {
					'fixed': TestCodes.REASON_FIXED_EXPECTED,
					'found': TestCodes.REASON_FIXED_UNEXPECTED,
					'run': TestCodes.REASON_OKAY,
					}.get(self.versions.state, result.result)
		elif result.result == TestCodes.RESULT_SKIP:
			result.reason = TestCodes.REASON_INTERNAL
		else:
			if result.result in TestResult.MESSAGE:
				result.reason = result.result
			else:
				result.reason = {
						'fixed': TestCodes.REASON_FAIL_UNEXPECTED,
						'found': TestCodes.REASON_FAIL_EXPECTED,
						'run': TestCodes.REASON_FAIL,
						}.get(self.versions.state, result.result)
		result.eofs = TestCodes.EOFS.get(result.reason, 'E')

class TestResult(TestCodes):
	def __init__(self, case, environment=None):
		self.case = case
		self.environment = environment
		self.result = -1
		self.reason = None
		self.duration = 0
		self.artifacts = {}
		self.condition = None
		self.eofs = None

	def dump(self, stream=sys.stdout):
		"""Dump test result data."""
		print >>stream, 'Case: %s' % (self.case.id,)
		print >>stream, 'Environment: %s' % (self.environment.hostname,)
		print >>stream, 'Result: %d %s' % (self.result, self.eofs)
		print >>stream, 'Reason: %s (%s)' % (self.reason, TestResult.MESSAGE.get(self.reason, ''))
		print >>stream, 'Duration: %d' % (self.duration or 0,)
		for (id, (mime, content)) in self.artifacts.items():
			print 'Artifact[%s]: %s %r' % (id, mime, content)

	def attach(self, id, mime, content):
		"""Attach artifact 'content' of mime-type 'mime'."""
		self.artifacts[id] = (mime, content)

	def success(self, reason=TestCodes.REASON_OKAY):
		"""Mark result as successful."""
		self.result = TestCodes.RESULT_OKAY
		self.reason = reason
		self.eofs = 'O'

	def fail(self, reason=TestCodes.REASON_FAIL):
		"""Mark result as failed."""
		self.result = TestCodes.RESULT_FAIL
		self.reason = reason
		self.eofs = 'F'

	def skip(self, reason=TestCodes.REASON_INTERNAL):
		"""Mark result as skipped."""
		self.result = TestCodes.RESULT_SKIP
		self.reason = self.reason or reason
		self.eofs = 'S'

	def check(self):
		"""Test conditions to run test."""
		conditions = self.case.check(self.environment)
		self.attach('check', 'python', conditions)
		self.condition = reduce(and_, map(bool, conditions), True)
		self.reason = ([c.reason for c in conditions if c.reason is not None] + [None])[0]
		return self.condition

	def run(self):
		"""Return test."""
		if self.condition is None:
			self.check()
		if self.condition:
			self.case.run(self)
		else:
			self.skip()
		return self

if __name__ == '__main__':
	import doctest
	doctest.testmod()
	te = TestEnvironment()
	#te.dump()
	tc = TestCase().load('tst3')
	#try:
	#	tc.check(te)
	#except TestConditionError, e:
	#	for m in e:
	#		print m
	tr = TestResult(tc, te)
	tr.dump()

# vim:set ts=4:
