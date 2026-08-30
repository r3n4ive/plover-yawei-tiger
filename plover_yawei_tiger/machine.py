"""Plover machine driver for the third-generation Yawei YW-V-3.

The device exposes a vendor-defined HID interface and sends an 8-byte input
report.  The first byte identifies a stroke report (0x1B, or 0x8B for the
alternate report type); bytes 2..5 contain four six-bit key fields.  The
upper two bits identify the field and are not part of the stroke.
"""

from __future__ import annotations

import hid

from plover import log
from plover.machine.base import ThreadedStenotypeBase


VENDOR_ID = 0x0000
PRODUCT_ID = 0x0000
USAGE_PAGE = 0xFF00
USAGE = 0x0001
REPORT_MARKERS = (0x1B, 0x8B)

# The four six-bit fields are ordered as observed on YW-V-3.  The final two
# positions in fields 1 and 3 are the thumb keys; their names follow the
# left-to-right order in the supplied Yawei layout.
_FIELD_KEYS = (
    ((0x01, "O-"), (0x02, "A-"), (0x04, "E-"), (0x08, "N-"), (0x10, "U-"), (0x20, "I-")),
    ((0x01, "W-"), (0x02, "G-"), (0x04, "Z-"), (0x08, "D-"), (0x10, "B-"), (0x20, "X-")),
    # The right half uses the same bit order as the left half.  It is
    # physically mirrored, but the HID report is not mirrored: bytes 4 and 5
    # retain the logical order O/A/E/N/U/I and W/G/Z/D/B/X.
    ((0x01, "-O"), (0x02, "-A"), (0x04, "-E"), (0x08, "-N"), (0x10, "-U"), (0x20, "-I")),
    ((0x01, "-W"), (0x02, "-G"), (0x04, "-Z"), (0x08, "-D"), (0x10, "-B"), (0x20, "-X")),
)


class YaweiV3(ThreadedStenotypeBase):
    """Read Yawei V3 reports and emit one Plover stroke per non-empty frame."""

    KEYS_LAYOUT = """
        # X- B- D- Z- G- W- I- U- N- E- A- O-
        * -X -B -D -Z -G -W -I -U -N -E -A -O
    """

    def __init__(self, params):
        super().__init__()
        self._device = None
        self._params = params

    @staticmethod
    def _decode(report):
        """Return machine key names from one raw HID report."""
        if len(report) >= 8 and report[0] in REPORT_MARKERS:
            # hidapi 0.11 on Windows returns the compact 8-byte form.
            fields = report[2:6]
        elif len(report) >= 9 and report[1] in REPORT_MARKERS:
            # Some Windows HID paths retain the leading report byte.
            fields = report[3:7]
        else:
            return ()
        # Each field has a positional two-bit tag: 00, 01, 10, 11.
        if any((value >> 6) != index for index, value in enumerate(fields)):
            return ()
        keys = []
        for value, field_keys in zip(fields, _FIELD_KEYS):
            low_bits = value & 0x3F
            keys.extend(key for bit, key in field_keys if low_bits & bit)
        return tuple(keys)

    @classmethod
    def get_option_info(cls):
        return {}

    def start_capture(self):
        self.stop_capture()
        self._initializing()
        devices = [
            item
            for item in hid.enumerate(VENDOR_ID, PRODUCT_ID)
            if item.get("usage_page") == USAGE_PAGE and item.get("usage") == USAGE
        ]
        if not devices:
            log.warning("No Yawei YW-V-3 HID device found")
            self._error()
            return
        try:
            self._device = hid.device()
            self._device.open_path(devices[0]["path"])
        except (IOError, OSError):
            log.warning("Unable to open Yawei YW-V-3 HID device", exc_info=True)
            self._device = None
            self._error()
            return
        ThreadedStenotypeBase.start_capture(self)

    def run(self):
        self._ready()
        while not self.finished.isSet():
            try:
                report = self._device.read(8, 100)
            except (IOError, OSError):
                log.warning("Yawei YW-V-3 disconnected", exc_info=True)
                self._error()
                return
            if not report:
                continue
            keys = self._decode(report)
            if keys:
                self._notify_keys(keys)

    def stop_capture(self):
        device = self._device
        self._device = None
        if device is not None:
            try:
                device.close()
            except (IOError, OSError):
                pass
        ThreadedStenotypeBase.stop_capture(self)
