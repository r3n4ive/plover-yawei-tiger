from plover_yawei_tiger.machine import YaweiV3


def report(*fields):
    """Build the compact eight-byte report emitted by YW-V-3."""

    return bytes([0x1B, 0]) + bytes(fields) + bytes([0, 0])


def test_decode_empty_and_invalid_reports():
    assert YaweiV3._decode([]) == ()
    assert YaweiV3._decode(bytes([0x00] * 8)) == ()
    assert YaweiV3._decode(report(0x01, 0x41, 0x81, 0xC1)) == (
        "O-", "W-", "-O", "-W"
    )


def test_decode_multiple_keys_in_each_field():
    # Low six bits are a bitset; upper two bits are positional tags.
    assert YaweiV3._decode(report(0x21, 0x52, 0xA4, 0xC9)) == (
        "O-", "I-", "G-", "B-", "-E", "-I", "-W", "-D"
    )


def test_decode_rejects_wrong_field_tags():
    assert YaweiV3._decode(report(0x41, 0x41, 0x81, 0xC1)) == ()


def test_connect_device_retries_hid_enumeration(monkeypatch):
    import plover_yawei_tiger.machine as machine

    calls = []

    class Device:
        def __init__(self):
            self.opened_path = None

        def open_path(self, path):
            self.opened_path = path

    device = Device()

    def enumerate_devices(vendor_id, product_id):
        calls.append((vendor_id, product_id))
        if len(calls) < 3:
            return []
        return [
            {"path": b"other-hid", "product_string": "USB Keyboard", "usage_page": 0xFF00, "usage": 1},
            {"path": b"yawei-path", "product_string": "YW-V-3", "usage_page": 0xFF00, "usage": 1},
        ]

    monkeypatch.setattr(machine.hid, "enumerate", enumerate_devices)
    monkeypatch.setattr(machine.hid, "device", lambda: device)
    monkeypatch.setattr(machine.time, "sleep", lambda _: None)

    assert YaweiV3._connect_device() is device
    assert device.opened_path == b"yawei-path"
    assert len(calls) == 3
