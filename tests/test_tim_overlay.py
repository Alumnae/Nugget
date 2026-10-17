import copy
import json
import plistlib
import tempfile
import unittest
from pathlib import Path
from src.tweaks.tim_overlay import OverlayJob, OVERLAY_DIR, patch_overlay


class TimOverlayTests(unittest.TestCase):
    def setUp(self):
        self.original = {"RemoteCardProvisioningSettings": {
            "SupportedSKUs": ["SKU_EU"], "ServerURL": "https://example.invalid/tim"},
            "Unrelated": {"payload": b"keep", "enabled": True}}

    def test_only_skus_change_and_format_is_preserved(self):
        expected = copy.deepcopy(self.original)
        expected["RemoteCardProvisioningSettings"]["SupportedSKUs"].append("SKU_CU")
        for fmt in (plistlib.FMT_BINARY, plistlib.FMT_XML):
            raw = plistlib.dumps(self.original, fmt=fmt)
            result = patch_overlay(raw)
            self.assertEqual(plistlib.loads(result), expected)
            self.assertEqual(result.startswith(b"bplist00"), fmt == plistlib.FMT_BINARY)
            self.assertEqual(patch_overlay(result), result)

    def test_reject_unexpected_plists(self):
        for value in ([], {}, {"RemoteCardProvisioningSettings": {"SupportedSKUs": "SKU_EU"}},
                      {"RemoteCardProvisioningSettings": {"SupportedSKUs": ["SKU_NA"]}}):
            with self.assertRaises(ValueError):
                patch_overlay(plistlib.dumps(value))

    def test_backup_identity_and_restore_integrity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = plistlib.dumps(self.original, fmt=plistlib.FMT_BINARY)
            source = root / "device-original.plist"
            source.write_bytes(raw)
            job = OverlayJob.prepare(source, OVERLAY_DIR + "device-test.plist", "12345678", root / "backups")
            self.assertEqual((job.backup_dir / "original.plist").read_bytes(), raw)
            restored = OverlayJob.load_backup(job.backup_dir / "manifest.json")
            self.assertEqual(restored.original, raw)
            job.validate_device("12345678", "26.1")
            for udid, version in (("87654321", "26.1"), ("12345678", "26.2")):
                with self.assertRaises(ValueError):
                    job.validate_device(udid, version)
            for target in (OVERLAY_DIR + "../device-test.plist", "/System/Library/Carrier Bundles/iPhone/TIM_Italy.bundle/carrier.plist", OVERLAY_DIR + "com.apple.carrier_1.plist"):
                with self.assertRaises(ValueError):
                    OverlayJob.prepare(source, target, "12345678", root / "backups")
            (job.backup_dir / "original.plist").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                OverlayJob.load_backup(job.backup_dir / "manifest.json")


if __name__ == "__main__":
    unittest.main()
