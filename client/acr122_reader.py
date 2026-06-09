from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime


SCARD_SCOPE_USER = 0
SCARD_SHARE_SHARED = 2
SCARD_PROTOCOL_T0 = 1
SCARD_PROTOCOL_T1 = 2
SCARD_LEAVE_CARD = 0

SCARD_S_SUCCESS = 0
SCARD_E_NO_SMARTCARD = 0x8010000C
SCARD_E_NO_READERS_AVAILABLE = 0x8010002E
SCARD_E_READER_UNAVAILABLE = 0x80100017
SCARD_W_REMOVED_CARD = 0x80100069
SCARD_W_UNPOWERED_CARD = 0x80100067


class SCARD_IO_REQUEST(ctypes.Structure):
    _fields_ = [
        ("dwProtocol", wintypes.DWORD),
        ("cbPciLength", wintypes.DWORD),
    ]


@dataclass
class CardEvent:
    sequence: int
    reader: str
    uid_hex: str
    uid_decimal: str
    at: str


class ACR122Reader:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._winscard = ctypes.WinDLL("winscard")
        self._configure_api()
        self.readers: list[str] = []
        self.last_card: CardEvent | None = None
        self.error = ""
        self.sequence = 0

    def _configure_api(self) -> None:
        self._winscard.SCardEstablishContext.argtypes = [
            wintypes.DWORD,
            wintypes.LPCVOID,
            wintypes.LPCVOID,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self._winscard.SCardEstablishContext.restype = wintypes.LONG
        self._winscard.SCardListReadersW.argtypes = [
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._winscard.SCardListReadersW.restype = wintypes.LONG
        self._winscard.SCardConnectW.argtypes = [
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._winscard.SCardConnectW.restype = wintypes.LONG
        self._winscard.SCardTransmit.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(SCARD_IO_REQUEST),
            ctypes.POINTER(ctypes.c_ubyte),
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._winscard.SCardTransmit.restype = wintypes.LONG
        self._winscard.SCardDisconnect.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        self._winscard.SCardDisconnect.restype = wintypes.LONG
        self._winscard.SCardReleaseContext.argtypes = [ctypes.c_void_p]
        self._winscard.SCardReleaseContext.restype = wintypes.LONG

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "readers": self.readers,
                "last_card": self.last_card.__dict__ if self.last_card else None,
                "error": self.error,
                "sequence": self.sequence,
            }

    def _set_error(self, message: str) -> None:
        with self._lock:
            self.error = message

    def _set_readers(self, readers: list[str]) -> None:
        with self._lock:
            self.readers = readers
            if readers:
                self.error = ""

    def _set_card(self, reader: str, uid_hex: str) -> None:
        uid_decimal = decimal_split_uid(uid_hex)
        if not uid_decimal:
            return
        with self._lock:
            self.sequence += 1
            self.last_card = CardEvent(
                sequence=self.sequence,
                reader=reader,
                uid_hex=uid_hex,
                uid_decimal=uid_decimal,
                at=datetime.now().isoformat(timespec="seconds"),
            )
            self.error = ""

    def _run(self) -> None:
        try:
            context = self._establish_context()
        except Exception as exc:
            self._set_error(str(exc))
            return

        active_cards: dict[str, str] = {}
        try:
            while not self._stop.is_set():
                try:
                    readers = self._list_readers(context)
                    self._set_readers(readers)
                    for reader in readers:
                        uid_hex = self._read_uid(context, reader)
                        if uid_hex and active_cards.get(reader) != uid_hex:
                            active_cards[reader] = uid_hex
                            self._set_card(reader, uid_hex)
                        elif not uid_hex and reader in active_cards:
                            active_cards.pop(reader, None)
                except Exception as exc:
                    self._set_error(str(exc))
                time.sleep(0.35)
        finally:
            self._winscard.SCardReleaseContext(context)

    def _establish_context(self) -> ctypes.c_void_p:
        context = ctypes.c_void_p()
        result = self._winscard.SCardEstablishContext(SCARD_SCOPE_USER, None, None, ctypes.byref(context))
        if result != SCARD_S_SUCCESS:
            raise RuntimeError(f"SCardEstablishContext failed: {hex_error(result)}")
        return context

    def _list_readers(self, context: ctypes.c_void_p) -> list[str]:
        size = wintypes.DWORD(0)
        result = self._winscard.SCardListReadersW(context, None, None, ctypes.byref(size))
        if status_code(result) == SCARD_E_NO_READERS_AVAILABLE:
            return []
        if result != SCARD_S_SUCCESS:
            raise RuntimeError(f"SCardListReaders failed: {hex_error(result)}")

        buffer = ctypes.create_unicode_buffer(size.value)
        result = self._winscard.SCardListReadersW(context, None, buffer, ctypes.byref(size))
        if result != SCARD_S_SUCCESS:
            raise RuntimeError(f"SCardListReaders failed: {hex_error(result)}")
        return [reader for reader in buffer.value.split("\0") if reader]

    def _read_uid(self, context: ctypes.c_void_p, reader: str) -> str | None:
        card = ctypes.c_void_p()
        protocol = wintypes.DWORD(0)
        result = self._winscard.SCardConnectW(
            context,
            reader,
            SCARD_SHARE_SHARED,
            SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1,
            ctypes.byref(card),
            ctypes.byref(protocol),
        )
        if status_code(result) in (
            SCARD_E_NO_SMARTCARD,
            SCARD_W_REMOVED_CARD,
            SCARD_W_UNPOWERED_CARD,
            SCARD_E_READER_UNAVAILABLE,
        ):
            return None
        if result != SCARD_S_SUCCESS:
            raise RuntimeError(f"SCardConnect failed: {hex_error(result)}")

        try:
            command = (ctypes.c_ubyte * 5)(0xFF, 0xCA, 0x00, 0x00, 0x00)
            response = (ctypes.c_ubyte * 40)()
            response_len = wintypes.DWORD(len(response))
            send_pci = SCARD_IO_REQUEST(protocol.value, ctypes.sizeof(SCARD_IO_REQUEST))
            result = self._winscard.SCardTransmit(
                card,
                ctypes.byref(send_pci),
                command,
                len(command),
                None,
                response,
                ctypes.byref(response_len),
            )
            if result != SCARD_S_SUCCESS:
                raise RuntimeError(f"SCardTransmit failed: {hex_error(result)}")

            data = bytes(response[: response_len.value])
            if len(data) >= 2:
                status = data[-2:]
                data = data[:-2]
                if status != b"\x90\x00":
                    return None
            if not data:
                return None
            return data.hex().upper()
        finally:
            self._winscard.SCardDisconnect(card, SCARD_LEAVE_CARD)


def status_code(code: int) -> int:
    return ctypes.c_ulong(code).value


def hex_error(code: int) -> str:
    return f"0x{status_code(code):08X}"


def decimal_split_uid(uid_hex: str) -> str:
    clean = "".join(ch for ch in uid_hex.upper() if ch in "0123456789ABCDEF")
    if len(clean) < 8:
        return ""
    four_bytes = clean[:8]
    high = int(four_bytes[:4], 16)
    low = int(four_bytes[4:8], 16)
    return f"{high:05d}:{low:05d}"
