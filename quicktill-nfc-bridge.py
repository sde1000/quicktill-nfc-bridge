#!/usr/bin/env python3

# To turn off card removed beeps: this will only work if the driver
# has been configured to allow CCID escape.
#
# On Linux: edit /etc/libccid_Info.plist and set key
# ifdDriverOptions to 0x0001
#
# On Mac: see https://github.com/pokusew/nfc-pcsc/issues/13
#
# On Windows: use SCARD_CTL_CODE(3500) instead of
# SCARD_CTL_CODE(1)
#
# The setting is stored in non-volatile memory in the reader, so once
# the beeps have been turned off on a particular reader the config
# file can be returned to its original state.

from smartcard.scard import *
import socket

class SCardException(Exception):
    def __init__(self, msg, result):
        super().__init__(msg + f": {SCardGetErrorMessage(result)}")

class PCSCCard:
    pci_headers = {
        SCARD_PROTOCOL_T0: SCARD_PCI_T0,
        SCARD_PROTOCOL_T1: SCARD_PCI_T1,
        SCARD_PROTOCOL_RAW: SCARD_PCI_RAW,
    }

    def __init__(self, handle, protocol):
        self.handle = handle
        self.protocol = protocol

    def close(self, disposition=SCARD_LEAVE_CARD):
        if self.handle:
            result = SCardDisconnect(self.handle, disposition)
            self.handle = None

    def __del__(self):
        self.close()

    def control(self, control_code, command):
        result, response = SCardControl(
            self.handle, control_code, command)
        if result != SCARD_S_SUCCESS:
            raise SCardException("Failed to control card", result)
        return response

    def transmit(self, apdu):
        result, response = SCardTransmit(
            self.handle, self.pci_headers[self.protocol], apdu)
        if result != SCARD_S_SUCCESS:
            raise SCardException("Failed to transmit", result)
        return response

class PCSCContext:
    pnp_notification = r"\\?PnP?\Notification"

    def __init__(self):
        self.context = None
        result, self.context = SCardEstablishContext(SCARD_SCOPE_SYSTEM)

        if result != SCARD_S_SUCCESS:
            raise SCardException("Failed to get SCard context", result)

    def close(self):
        if self.context:
            SCardReleaseContext(self.context)
            self.hcontext = None

    def getReaderNames(self):
        result, pcscreaders = SCardListReaders(self.context, [])
        if result != SCARD_S_SUCCESS \
           and result != SCARD_E_NO_READERS_AVAILABLE:
            raise SCardException("Failed to list readers", result)

        return pcscreaders

    def getStatusChange(self, readerstates, timeout=INFINITE):
        """Wait for a change in state

        readerstates is a list of (readername, state) tuples

        Magic reader name PCSCContext.pnp_notification can be used to
        wait for reader add and remove events

        timeout is in milliseconds
        """
        result, newstates = SCardGetStatusChange(
            self.context, timeout, readerstates)

        if result == SCARD_E_TIMEOUT:
            return []

        if result != SCARD_S_SUCCESS:
            raise SCardException("Failed to get status change", result)

        return newstates

    def connect(self, reader, mode, protocol):
        result, card_handle, active_protocol = SCardConnect(
            self.context, reader, mode, protocol)
        if result != SCARD_S_SUCCESS:
            raise SCardException("Failed to connect", result)
        return PCSCCard(card_handle, active_protocol)
        
    def __del__(self):
        self.close()

class ReaderMonitor:
    def __init__(self, ctx, s=None):
        self.ctx = ctx
        self.s = s
        self.readers = {} # name -> current state
        self.update_readers()

    def update_readers(self):
        # Check current list of reader names and add/remove from readerstates
        current_readers = self.ctx.getReaderNames()
        for r in current_readers:
            if r not in self.readers:
                self.readers[r] = SCARD_STATE_UNAWARE
                self.new_reader(r)
        for r in list(self.readers.keys()):
            if r not in current_readers:
                del self.readers[r]

    def await_changes(self, timeout=INFINITE):
        rs = list(self.readers.items()) + [(self.ctx.pnp_notification, 0)]
        ns = self.ctx.getStatusChange(rs, timeout)
        readers_changed = False
        for r, eventstate, atr in ns:
            if r == self.ctx.pnp_notification:
                if eventstate & SCARD_STATE_CHANGED:
                    readers_changed = True
                continue
            self.readers[r] = eventstate
            if eventstate & SCARD_STATE_PRESENT:
                self.new_card(r)
        if readers_changed:
            self.update_readers()

    def new_reader(self, r):
        # Called when a new reader is detected
        if r.startswith("ACS ACR1252") or r.startswith("ACS ACR1255U-J1"):
            card = self.ctx.connect(r, SCARD_SHARE_DIRECT, SCARD_PROTOCOL_RAW)
            try:
                apdu = [ 0xe0, 0x00, 0x00, 0x21, 0x01, 0x6f ]
                out = card.control(SCARD_CTL_CODE(1), apdu)
            except SCardException:
                pass
            card.close()

    def new_card(self, r):
        # Called when a card insertion is detected
        out = []
        card = self.ctx.connect(
            r, SCARD_SHARE_SHARED,
            SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1 | SCARD_PROTOCOL_RAW)
        try:
            out = card.transmit([ 0xff, 0xca, 0x00, 0x00, 0x00 ])
        finally:
            card.close()
        if len(out) < 2:
            return # Not a valid response
        sw1 = out[-2]
        sw2 = out[-1]
        if sw1 != 0x90 or sw2 != 0x00:
            return # Error
        nfc = "nfc:" + ''.join(f"{x:02x}" for x in out[:-2])
        if self.s:
            self.s.sendto(nfc.encode('utf-8'), ('127.0.0.1', 8455))

if __name__ == "__main__":
    ctx = PCSCContext()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    mon = ReaderMonitor(ctx, s)

    while True:
        mon.await_changes(timeout=INFINITE)
