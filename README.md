quicktill-nfc-bridge
====================

This is a quick and dirty interface between pyscard / pcsc and
quicktill, to convert NFC card taps on an NFC reader into user tokens
delivered as UDP packets to localhost:8455.

Any CCID compatible NFC reader should work: there's a standard way to
retrieve contactless UIDs.  This package has additional code to deal
with ACR122, ACR1252 and ACR1255 readers (with suitably recent
firmware), to turn off the "beep on card insert/remove" options when
the reader is discovered.

The reader configuration code can only work when CCID escape is
enabled in the pcsc driver. To do this, edit the driver config file
(`/etc/libccid_Info.plist` on Linux) and set key `ifdDriverOptions` to
`0x0001`.  On ACR1252 and ACR1255 the configuration is stored in
non-volatile memory on the reader, so once all your readers have been
configured you can change the driver config file back to the default
setting of `0x0000`. You may need to restart `pcscd` to pick up the
configuration file change. ACR122 doesn't have any non-volatile memory
so the beeps need turning off every time it's plugged in.

If you want to keep card-inserted beeps, create
`/etc/systemd/system/quicktill-nfc-bridge.service.d/override.conf` and
override ExecStart to add the --beep option to the command line:

```
[Service]
ExecStart=
ExecStart=/usr/sbin/quicktill-nfc-bridge --beep
```

Copying
-------

quicktill-nfc-bridge is Copyright (C) 2014–2024 Stephen Early <steve@assorted.org.uk>

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

To build quicktill-nfc-bridge, start with this repository as the
current working directory:

    make

To build the Debian package:

    dpkg-buildpackage
