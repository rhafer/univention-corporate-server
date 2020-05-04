# -*- coding: utf-8 -*-
#
# Univention Python
#  IPv4 address calculation utilities
#
# Copyright 2002-2020 Univention GmbH
#
# https://www.univention.de/
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
# <https://www.gnu.org/licenses/>.

import ipaddress


def networkNumber(dottedIp, dottedNetmask):
	"""
	Calculate network number from dotted quad IPv4 address string and network mask.

	>>> networkNumber('1.2.3.4', '255.255.254.0')
	'1.2.2.0'
	"""
	return str(ipaddress.IPv4Network(u'%s/%s' % (dottedIp, dottedNetmask), strict=False).network_address)


def broadcastNumber(dottedNetwork, dottedNetmask):
	"""
	Calculate broadcast address from dotted quad IPv4 address string and network mask.

	>>> broadcastNumber('1.2.2.0', '255.255.254.0')
	'1.2.3.255'
	>>> broadcastNumber('1.2.3.4', '255.255.254.0')
	'1.2.3.255'
	"""
	return str(ipaddress.IPv4Network(u'%s/%s' % (dottedNetwork, dottedNetmask), strict=False).broadcast_address)


if __name__ == '__main__':
	import doctest
	doctest.testmod()
