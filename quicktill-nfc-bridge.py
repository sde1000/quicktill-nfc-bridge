#!/usr/bin/env python3

# To turn off card removed/inserted beeps: this will only work if the
# driver has been configured to allow CCID escape.
#
# On Linux: edit /etc/libccid_Info.plist and set key
# ifdDriverOptions to 0x0001
#
# On Mac: see https://github.com/pokusew/nfc-pcsc/issues/13
#
# On Windows: use SCARD_CTL_CODE(3500) instead of
# SCARD_CTL_CODE(1)
#
# On ACR1252 and ACR1255, the setting is stored in non-volatile memory
# in the reader, so once the beeps have been turned off on a
# particular reader the config file can be returned to its original
# state. ACR122 does not have any non-volatile storage and the beeps
# must be turned off every time it is plugged in.

from smartcard.scard import SCARD_PROTOCOL_T0, SCARD_PCI_T0, \
    SCARD_PROTOCOL_T1, SCARD_PCI_T1, SCARD_PROTOCOL_RAW, SCARD_PCI_RAW, \
    SCARD_LEAVE_CARD, SCARD_S_SUCCESS, SCARD_SCOPE_SYSTEM, \
    SCARD_E_NO_READERS_AVAILABLE, SCARD_E_TIMEOUT, SCARD_STATE_UNAWARE, \
    SCARD_STATE_CHANGED, SCARD_STATE_PRESENT, SCARD_SHARE_DIRECT, \
    SCARD_SHARE_SHARED, INFINITE, SCARD_CTL_CODE, \
    SCardGetErrorMessage, SCardDisconnect, SCardControl, \
    SCardTransmit, SCardEstablishContext, SCardReleaseContext, \
    SCardGetStatusChange, SCardConnect, SCardListReaders

import socket
import argparse
import logging
import libevdev
import pwd
import os
import sys
import sdnotify

log = logging.getLogger("quicktill-nfc-bridge")

# Wake terminal by simulating brief press of left Ctrl key on fake keyboard
keypress = [
    libevdev.InputEvent(libevdev.EV_KEY.KEY_LEFTCTRL, 1),
    libevdev.InputEvent(libevdev.EV_SYN.SYN_REPORT, 0),
    libevdev.InputEvent(libevdev.EV_KEY.KEY_LEFTCTRL, 0),
    libevdev.InputEvent(libevdev.EV_SYN.SYN_REPORT, 0),
]


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
            SCardDisconnect(self.handle, disposition)
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
            self.context = None

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
    def __init__(self, ctx, s, beep, uinput):
        self.ctx = ctx
        self.s = s
        self.beep = beep
        self.uinput = uinput
        self.readers = {}  # name -> current state
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
                log.info("reader '%s' disconnected", r)
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
        log.info("new reader '%s' connected", r)
        if r.startswith("ACS ACR122U "):
            log.debug("initialising ACR122U")
            card = self.ctx.connect(r, SCARD_SHARE_DIRECT, SCARD_PROTOCOL_RAW)
            try:
                apdu = [0xff, 0x00, 0x52, 0xff if self.beep else 0x00, 0x00]
                out = card.control(SCARD_CTL_CODE(1), apdu)
                log.debug("out=%r", out)
            except SCardException:
                log.info("ACR122U init failed")
            finally:
                card.close()
        elif r.startswith("ACS ACR1252"):
            log.debug("initialising ACR1252")
            # bits 6 and 7 control the LED colour: 0x80=red, 0x40=green
            if self.beep:
                desired_behaviour = 0xaf
            else:
                desired_behaviour = 0xa7
            card = self.ctx.connect(r, SCARD_SHARE_DIRECT, SCARD_PROTOCOL_RAW)
            try:
                out = card.control(SCARD_CTL_CODE(1), [
                    0xe0, 0x00, 0x00, 0x21, 0x00])
                log.debug("read current behaviour: out=%r", out)
                current_behaviour = out[5]
                if current_behaviour != desired_behaviour:
                    log.debug("setting new behaviour: %d", desired_behaviour)
                    out = card.control(SCARD_CTL_CODE(1), [
                        0xe0, 0x00, 0x00, 0x21, 0x01, desired_behaviour])
                    log.debug("set behaviour: out=%r", out)
            except SCardException:
                pass
            finally:
                card.close()
        elif r.startswith("ACS ACR1255U-J1"):
            log.debug("initialising ACR1255")
            # XXX bit 6 (0x40) of behaviour must not be set for this device
            if self.beep:
                desired_behaviour = 0xaf
            else:
                desired_behaviour = 0xa7
            card = self.ctx.connect(r, SCARD_SHARE_DIRECT, SCARD_PROTOCOL_RAW)
            try:
                out = card.control(SCARD_CTL_CODE(1), [
                    0xe0, 0x00, 0x00, 0x21, 0x00])
                log.debug("read current behaviour: out=%r", out)
                current_behaviour = out[5]
                if current_behaviour != desired_behaviour:
                    log.debug("setting new behaviour: %d", desired_behaviour)
                    out = card.control(SCARD_CTL_CODE(1), [
                        0xe0, 0x00, 0x00, 0x21, 0x01, desired_behaviour])
                    log.debug("set behaviour: out=%r", out)
            except SCardException:
                pass
            finally:
                card.close()
        else:
            log.info("don't know how to set beep behaviour for this reader")

    def new_card(self, r):
        # Called when a card insertion is detected
        out = []
        card = self.ctx.connect(
            r, SCARD_SHARE_SHARED,
            SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1 | SCARD_PROTOCOL_RAW)
        try:
            out = card.transmit([0xff, 0xca, 0x00, 0x00, 0x00])
        finally:
            card.close()
        if len(out) < 2:
            return  # Not a valid response
        sw1 = out[-2]
        sw2 = out[-1]
        if sw1 != 0x90 or sw2 != 0x00:
            return  # Error
        nfc = "nfc:" + ''.join(f"{x:02x}" for x in out[:-2])
        log.info('card read: %s', nfc)
        if self.uinput:
            self.uinput.send_events(keypress)
        try:
            self.s.send(nfc.encode('utf-8'))
        except ConnectionRefusedError:
            log.debug('udp send: connection refused')


def run(args):
    uinput = None

    if args.fake_keypress:
        evdev = libevdev.Device()
        evdev.name = "quicktill-nfc-bridge fake keyboard"
        evdev.enable(libevdev.EV_KEY.KEY_LEFTCTRL)

        uinput = evdev.create_uinput_device()

    ctx = PCSCContext()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((args.host, args.port))
    mon = ReaderMonitor(ctx, s, args.beep, uinput)

    if args.setuser:
        try:
            pwdb = pwd.getpwnam(args.setuser)
        except KeyError:
            log.fatal("Specified user does not exist for --setuid")
            sys.exit(1)
        os.setgid(pwdb.pw_gid)
        os.setuid(pwdb.pw_uid)

    if args.notify_startup:
        log.debug("notifying startup complete to systemd")
        sdnotify.SystemdNotifier().notify("READY=1")

    while True:
        mon.await_changes(timeout=INFINITE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read NFC card UIDs")
    parser.add_argument('--beep', default=False, action="store_true",
                        help="Configure readers to beep on card detection")
    parser.add_argument('--host', default="127.0.0.1",
                        help="Host to deliver packets to")
    parser.add_argument('--port', default=8455, type=int,
                        help="Port to deliver packets to")
    parser.add_argument('--verbose', '-v', default=False, action="store_true",
                        help="Print details as cards and readers are detected")
    parser.add_argument('--debug', default=False, action="store_true",
                        help="Enable debug output")
    parser.add_argument('--fake-keypress', default=False, action="store_true",
                        help="Fake a keypress when a card is detected")
    parser.add_argument('--notify-startup', default=False, action="store_true",
                        help="Notify systemd when startup is complete")
    parser.add_argument('--setuser', type=str, default=None,
                        help="setuid to specified user after initialisation")
    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
    run(args)
