import copy
import json
import plistlib
import tempfile
import unittest
from pathlib import Path
from src.tweaks.tim_overlay import OverlayJob, OVERLAY_DIR, patch_overlay, BOARD_CONFIGS, board_config, overlay_target, overlay_board


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

    def test_boardconfig_table_and_device_matching(self):
        self.assertEqual(len(BOARD_CONFIGS), 10)
        identifiers = [identifier for entry in BOARD_CONFIGS for identifier in entry[3]]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual(board_config("12")[2], "overrides_D52g_D53g_D53p_D54p.plist")
        self.assertEqual(board_config("Air")[3], ("iPhone18,4",))
        with self.assertRaises(ValueError):
            board_config("unknown")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "device-original.plist"
            source.write_bytes(plistlib.dumps(self.original))
            for series, label, filename, supported in BOARD_CONFIGS:
                job = OverlayJob.prepare(source, OVERLAY_DIR + "device-test.plist", "12345678", root / "backups", series=series)
                for identifier in supported:
                    job.validate_device("12345678", "26.1", identifier)
                with self.assertRaises(ValueError):
                    job.validate_device("12345678", "26.1", "iPhone99,99")
                manifest = job.backup_dir / "manifest.json"
                self.assertEqual(json.loads(manifest.read_text())["boardconfig"], filename)
                self.assertEqual(OverlayJob.load_backup(manifest).series, series)

    def test_named_overlay_version_and_backup(self):
        expected = OVERLAY_DIR + "device+carrier+22201+V59+66.0.plist"
        self.assertEqual(overlay_target("16e", "V59", "66.0"), expected)
        for version in ("", "66", "66/0", "../66.0", "66.0.plist", "66.0+evil", "66..0"):
            with self.assertRaises(ValueError):
                overlay_target("16e", "V59", version)
        with self.assertRaises(ValueError):
            overlay_target("16e", "D23", "66.0")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "device+carrier+22201+V59+66.0.plist"
            source.write_bytes(plistlib.dumps(self.original))
            job = OverlayJob.prepare(source, expected, "12345678", root / "backups", "16e", "V59", "66.0")
            loaded = OverlayJob.load_backup(job.backup_dir / "manifest.json")
            self.assertEqual((loaded.target, loaded.board, loaded.carrier_version), (expected, "V59", "66.0"))
            other = OverlayJob.prepare(source, overlay_target("16e", "V59", "67.0"), "12345678", root / "backups", "16e", "V59", "67.0")
            self.assertNotEqual(job.backup_dir, other.backup_dir)
            self.assertEqual(OverlayJob.load_backup(job.backup_dir / "manifest.json").target, expected)
            with self.assertRaises(ValueError):
                OverlayJob.prepare(source, expected, "12345678", root / "backups", "16e", "V59", "67.0")
            with self.assertRaises(ValueError):
                OverlayJob.prepare(source, expected.replace("22201", "22210"), "12345678", root / "backups", "16e", "V59", "66.0")

    def test_grouped_board_filenames(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "original.plist"
            source.write_bytes(plistlib.dumps(self.original))
            for series, label, filename, identifiers in BOARD_CONFIGS:
                group = filename.removeprefix("overrides_").removesuffix(".plist")
                self.assertEqual(overlay_board(series), group)
                target = overlay_target(series, group, "66.0")
                self.assertEqual(target, OVERLAY_DIR + f"device+carrier+22201+{group}+66.0.plist")
                job = OverlayJob.prepare(source, target, "12345678", root / "backups", series, group, "66.0")
                self.assertEqual(OverlayJob.load_backup(job.backup_dir / "manifest.json").board, group)
                if "_" in group:
                    with self.assertRaises(ValueError):
                        overlay_target(series, group.split("_")[0], "66.0")
        self.assertEqual(overlay_target("17", overlay_board("17"), "66.0"),
                         OVERLAY_DIR + "device+carrier+22201+V53_V54_V57+66.0.plist")

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
