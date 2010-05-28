#!/usr/bin/python2.4
# -*- coding: utf-8 -*-
#
# Univention Virtual Machine Manager
#  UDM Virtual Machine Manager Profiles
#
# Copyright (C) 2010 Univention GmbH
#
# http://www.univention.de/
#
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# Binary versions of this file provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import univention.admin.filter
import univention.admin.handlers
import univention.admin.syntax
import univention.admin.localization

translation=univention.admin.localization.translation('univention.admin.handlers.uvmm')
_=translation.translate

module = 'uvmm/profile'

childs = 0
short_description = _('UVMM: Profile')
long_description = ''
operations = [ 'search', 'edit', 'add', 'remove' ]

property_descriptions={
	'name': univention.admin.property(
			short_description= _('Name'),
			long_description= _('Name'),
			syntax=univention.admin.syntax.string,
			multivalue=0,
			options=[],
			required=1,
			may_change=1,
			identifies=1
		),
	'name_prefix': univention.admin.property(
			short_description= _('Name prefix'),
			long_description= _('Prefix for the name of virtual machines'),
			syntax=univention.admin.syntax.string,
			multivalue=0,
			options=[],
			required=0,
			may_change=1,
			identifies=0
		),
	'arch': univention.admin.property(
			short_description= _('Architecture'),
			long_description= _('Architecture of the virtual machine'),
			syntax=univention.admin.syntax.string,
			multivalue=0,
			options=[],
			required=0,
			may_change=1,
			identifies=0
		),
	'virttech': univention.admin.property(
			short_description= _('Virtualisation Technology'),
			long_description= _('Virtualisation Technology'),
			syntax=univention.admin.syntax.string,
			multivalue=0,
			options=[],
			required=0,
			may_change=1,
			identifies=0
		),
	'cpus': univention.admin.property(
			short_description= _('CPUs'),
			long_description= _('Number of virtual CPUs'),
			syntax=univention.admin.syntax.integer,
			multivalue=0,
			options=[],
			required=0,
			may_change=1,
			identifies=0
		),
	'ram': univention.admin.property(
			short_description= _('Memory'),
			long_description= _('Amount of memory'),
			syntax=univention.admin.syntax.string,
			multivalue=0,
			options=[],
			required=0,
			may_change=1,
			identifies=0
		),
	'interface': univention.admin.property(
			short_description= _('Network interface'),
			long_description= _('Bridging interface'),
			syntax=univention.admin.syntax.string,
			multivalue=0,
			options=[],
			required=0,
			may_change=1,
			identifies=0
		),
	'vnc': univention.admin.property(
			short_description= _('Remote access'),
			long_description= _('Active VNC remote acess'),
			syntax=univention.admin.syntax.boolean,
			multivalue=0,
			options=[],
			required=0,
			may_change=1,
			identifies=0
		),
	'kblayout': univention.admin.property(
			short_description= _('Keyboard layout'),
			long_description= _('Keyboard layout'),
			syntax=univention.admin.syntax.string,
			multivalue=0,
			options=[],
			required=0,
			may_change=1,
			identifies=0
		),
}


layout=[
	univention.admin.tab( _('General'), _('Virtual machine profile'),
	      [
			[ univention.admin.field( "name" ), ],
			[ univention.admin.field( "name_prefix" ), ],
			[ univention.admin.field( "arch" ),  univention.admin.field( "cpus" ) ],
			[ univention.admin.field( "virttech" ),  univention.admin.field( "ram" ) ],
			[ univention.admin.field( "interface" ), ],
			[ univention.admin.field( "vnc" ),  univention.admin.field( "kblayout" ) ],
		  ] )
	]



mapping=univention.admin.mapping.mapping()
mapping.register('name', 'cn', None, univention.admin.mapping.ListToString)
mapping.register('name_prefix', 'univentionVirtualMachineProfileNamePrefix', None, univention.admin.mapping.ListToString)
mapping.register('arch', 'univentionVirtualMachineProfileArch', None, univention.admin.mapping.ListToString)
mapping.register('cpus', 'univentionVirtualMachineProfileCPUs', None, univention.admin.mapping.ListToString)
mapping.register('virttech', 'univentionVirtualMachineProfileVirtTech', None, univention.admin.mapping.ListToString)
mapping.register('ram', 'univentionVirtualMachineProfileRAM', None, univention.admin.mapping.ListToString)
mapping.register('vnc', 'univentionVirtualMachineProfileVNC', None, univention.admin.mapping.ListToString)
mapping.register('interface', 'univentionVirtualMachineProfileInterface', None, univention.admin.mapping.ListToString)
mapping.register('kblayout', 'univentionVirtualMachineProfileKBLayout', None, univention.admin.mapping.ListToString)


class object(univention.admin.handlers.simpleLdap):
	module=module

	def __init__(self, co, lo, position, dn='', superordinate=None, arg=None):
		global mapping
		global property_descriptions

		self.co=co
		self.lo=lo
		self.dn=dn
		self.position=position
		self._exists=0
		self.mapping=mapping
		self.descriptions=property_descriptions

		univention.admin.handlers.simpleLdap.__init__(self, co, lo, position, dn, superordinate)

	def exists(self):
		return self._exists

	def _ldap_pre_create(self):
		self.dn='%s=%s,%s' % (mapping.mapName('name'), mapping.mapValue('name', self.info['name']), self.position.getDn())

	def _ldap_addlist(self):
		return [ ('objectClass', [ 'univentionVirtualMachineProfile' ] ) ]

def lookup(co, lo, filter_s, base='', superordinate=None, scope='sub', unique=0, required=0, timeout=-1, sizelimit=0):
	filter=univention.admin.filter.conjunction('&', [
				univention.admin.filter.expression('objectClass', 'univentionVirtualMachineProfile'),
				])

	if filter_s:
		filter_p=univention.admin.filter.parse(filter_s)
		univention.admin.filter.walk(filter_p, univention.admin.mapping.mapRewrite, arg=mapping)
		filter.expressions.append(filter_p)

	res=[]
	for dn in lo.searchDn(unicode(filter), base, scope, unique, required, timeout, sizelimit):
		res.append(object(co, lo, None, dn))
	return res


def identify(dn, attr, canonical=0):
	return 'univentionVirtualMachineProfile' in attr.get('objectClass', [])
