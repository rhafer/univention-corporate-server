# -*- coding: utf-8 -*-
#
# Univention Password Self Service frontend base class
#
# Copyright 2015 Univention GmbH
#
# http://www.univention.de/
#
# All rights reserved.
#
# The source code of this program is made available
# under the terms of the GNU Affero General Public License version 3
# (GNU AGPL V3) as published by the Free Software Foundation.
#
# Binary versions of this program provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention and not subject to the GNU AGPL V3.
#
# In the case you use this program under the terms of the GNU AGPL V3,
# the program is provided in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License with the Debian GNU/Linux or Univention distribution in file
# /usr/share/common-licenses/AGPL-3; if not, see
# <http://www.gnu.org/licenses/>.

import cherrypy

from httplib import HTTPException
from socket import error as SocketError

from univention.lib.umc_connection import UMCConnection
from univention.management.console.config import ucr

LDAP_SECRETS_FILE = "/etc/self-service-ldap.secret"


class UniventionSelfServiceFrontend(object):
	"""
	base class
	"""
	def __init__(self):
		self.log("init")

	def log(self, msg, traceback=False):
		cherrypy.log("{}: {}".format(self.__class__.__name__, msg), traceback=traceback)

	@property
	def cherrypy_conf(self):
		return {}

	@property
	def url(self):
		return "test/"

	@property
	def name(self):
		return self.__class__.__name__

	def get_umc_connection(self):
		"""
		This is UMCConnection.get_machine_connection(), but using
		LDAP_SECRETS_FILE instead of /etc/machine.secret.
		:return: UMCConnection
		"""
		username = '%s$' % ucr.get('hostname')
		try:
			with open(LDAP_SECRETS_FILE) as machine_file:
				password = machine_file.readline().strip()
		except (OSError, IOError) as e:
			self.log('Could not read {}: {}'.format(LDAP_SECRETS_FILE, e))
			raise

		error_handler = self.log
		try:
			connection = UMCConnection(ucr.get('ldap/master'), username, password)
			return connection
		except (HTTPException, SocketError) as e:
			if error_handler:
				error_handler('Could not connect to UMC on %s: %s' % (ucr.get('ldap/master'), e))
			return None
