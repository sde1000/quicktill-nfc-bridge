.PHONY: all clean install

# Places to install to
sbindir=usr/sbin/
systemddir=lib/systemd/system/

CFLAGS:=-Wall

all:	quicktill-nfc-bridge

clean:
	rm -f quicktill-nfc-bridge quicktill-nfc-bridge.o

install:	all
	install -d $(DESTDIR)/$(sbindir)
	install -d $(DESTDIR)/$(upstartdir)
	install -d $(DESTDIR)/$(systemddir)
	install -d $(DESTDIR)/etc/modprobe.d/
	install -s quicktill-nfc-bridge $(DESTDIR)/$(sbindir)
	install -m 644 quicktill-nfc-bridge@.service $(DESTDIR)/$(systemddir)
	install -m 644 blacklist-quicktill.conf $(DESTDIR)/etc/modprobe.d/

quicktill-nfc-bridge:	quicktill-nfc-bridge.o
	gcc -o quicktill-nfc-bridge quicktill-nfc-bridge.o \
	-lnfc
