quicktill-nfc-bridge
====================

This is a quick and dirty interface between libnfc and quicktill, to
convert NFC card taps on an ACR122U NFC reader into user tokens
delivered as UDP packets to localhost:8455.  It's intended for use
with Ubuntu 14.04, but might work with later versions as well.

Copying
-------

quicktill-nfc-bridge is Copyright (C) 2014 Stephen Early <sde@individualpubs.co.uk>

It is distributed under the terms of the GNU General Public License
as published by the Free Software Foundation, either version 3
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see [this
link](http://www.gnu.org/licenses/).

Building
--------

Make sure the 'libnfc-dev' package is installed.

To build quicktill-nfc-bridge, start with this repository as the
current working directory:

    make

To build the Debian package:

    dpkg-buildpackage
