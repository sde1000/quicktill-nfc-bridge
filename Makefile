.PHONY: all clean install

libnfcdir=../libnfc-1.7.0

# Places to install to
libdir=lib/quicktill-nfc-bridge/
udevruledir=lib/udev/rules.d/

CFLAGS:=-Wall -I$(libnfcdir)/include/
LDFLAGS:=-L $(libnfcdir)/

all:	quicktill-nfc-bridge

clean:
	rm -f quicktill-nfc-bridge quicktill-nfc-bridge.o

install:	all
	install -d $(DESTDIR)/$(libdir)
	install -d $(DESTDIR)/$(udevruledir)
	install -d $(DESTDIR)/etc/modprobe.d/
	install -s quicktill-nfc-bridge $(DESTDIR)/$(libdir)
	install start-quicktill-nfc-bridge.sh $(DESTDIR)/$(libdir)
	install 85-quicktill-nfc-bridge.rules $(DESTDIR)/$(udevruledir)
	install blacklist-quicktill.conf $(DESTDIR)/etc/modprobe.d/

quicktill-nfc-bridge:	quicktill-nfc-bridge.o
	gcc -o quicktill-nfc-bridge quicktill-nfc-bridge.o \
	$(libnfcdir)/libnfc/.libs/libnfc.a -lusb
