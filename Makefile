.PHONY: all clean install

libnfcdir=../libnfc-1.7.0

# Places to install to
sbindir=usr/sbin/
upstartdir=etc/init/

CFLAGS:=-Wall -I$(libnfcdir)/include/
LDFLAGS:=-L $(libnfcdir)/

all:	quicktill-nfc-bridge

clean:
	rm -f quicktill-nfc-bridge quicktill-nfc-bridge.o

install:	all
	install -d $(DESTDIR)/$(sbindir)
	install -d $(DESTDIR)/$(upstartdir)
	install -d $(DESTDIR)/etc/modprobe.d/
	install -s quicktill-nfc-bridge $(DESTDIR)/$(sbindir)
	install quicktill-nfc-bridge.conf $(DESTDIR)/$(upstartdir)
	install blacklist-quicktill.conf $(DESTDIR)/etc/modprobe.d/

quicktill-nfc-bridge:	quicktill-nfc-bridge.o
	gcc -o quicktill-nfc-bridge quicktill-nfc-bridge.o \
	$(libnfcdir)/libnfc/.libs/libnfc.a -lusb
