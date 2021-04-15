.PHONY: install all

# Places to install to
sbindir=usr/sbin
systemddir=lib/systemd/system

all:

install:
	install -d $(DESTDIR)/$(sbindir)
	install -d $(DESTDIR)/$(systemddir)
	install -d $(DESTDIR)/etc/modprobe.d/
	install -m 755 quicktill-nfc-bridge.py $(DESTDIR)/$(sbindir)/quicktill-nfc-bridge
	install -m 644 quicktill-nfc-bridge.service $(DESTDIR)/$(systemddir)
	install -m 644 blacklist-quicktill.conf $(DESTDIR)/etc/modprobe.d/
