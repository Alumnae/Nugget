"""Experimental, imported TIM carrier overlay; no signature bypass."""
import copy
import hashlib
import json
import plistlib
import re
from dataclasses import dataclass
from pathlib import Path

OVERLAY_DIR = "/var/mobile/Library/Carrier Bundles/Overlay/"


# Grouped exactly as supplied by the user; these are bundle override files,
# not the runtime Overlay/device-*.plist filenames.
BOARD_CONFIGS = (
    ("Air", "iPhone Air", "overrides_D23.plist", ("iPhone18,4",)),
    ("17", "iPhone 17 / 17 Pro / 17 Pro Max", "overrides_V53_V54_V57.plist", ("iPhone18,1", "iPhone18,2", "iPhone18,3")),
    ("16e", "iPhone 16e", "overrides_V59.plist", ("iPhone17,5",)),
    ("16", "iPhone 16 / 16 Plus / 16 Pro / 16 Pro Max", "overrides_D93_D94_D47_D48.plist", tuple(f"iPhone17,{n}" for n in (1, 2, 3, 4))),
    ("15", "iPhone 15 / 15 Plus / 15 Pro / 15 Pro Max", "overrides_D83_D84_D37_D38.plist", ("iPhone15,4", "iPhone15,5", "iPhone16,1", "iPhone16,2")),
    ("14", "iPhone 14 / 14 Plus / 14 Pro / 14 Pro Max", "overrides_D73_D74_D27_D28.plist", ("iPhone14,7", "iPhone14,8", "iPhone15,2", "iPhone15,3")),
    ("SE 3", "iPhone SE (2022 / 3rd generation)", "overrides_D49.plist", ("iPhone14,6",)),
    ("13", "iPhone 13 Pro / 13 Pro Max / 13 mini / 13", "overrides_D63_D64_D16_D17.plist", tuple(f"iPhone14,{n}" for n in (2, 3, 4, 5))),
    ("12", "iPhone 12 mini / 12 / 12 Pro / 12 Pro Max", "overrides_D52g_D53g_D53p_D54p.plist", tuple(f"iPhone13,{n}" for n in (1, 2, 3, 4))),
    ("11", "iPhone 11 / 11 Pro / 11 Pro Max", "overrides_D421_D431_N104.plist", ("iPhone12,1", "iPhone12,3", "iPhone12,5")),
)


def board_config(series):
    for entry in BOARD_CONFIGS:
        if entry[0] == series:
            return entry
    raise ValueError("Unknown iPhone series in the BoardConfig table.")


def patch_overlay(raw: bytes) -> bytes:
    original = plistlib.loads(raw)
    if not isinstance(original, dict):
        raise ValueError("Overlay must be a plist dictionary.")
    patched = copy.deepcopy(original)
    settings = patched.get("RemoteCardProvisioningSettings")
    if not isinstance(settings, dict):
        raise ValueError("Missing RemoteCardProvisioningSettings; not a supported overlay.")
    skus = settings.get("SupportedSKUs")
    if not isinstance(skus, list) or not skus or not all(isinstance(s, str) for s in skus):
        raise ValueError("SupportedSKUs must be a nonempty array of strings.")
    if "SKU_EU" not in skus:
        raise ValueError("Expected SKU_EU in the original TIM overlay.")
    if "SKU_CU" not in skus:
        skus.append("SKU_CU")
    fmt = plistlib.FMT_BINARY if raw.startswith(b"bplist00") else plistlib.FMT_XML
    return plistlib.dumps(patched, fmt=fmt, sort_keys=False)


@dataclass(frozen=True)
class OverlayJob:
    original: bytes
    patched: bytes
    target: str
    udid: str
    backup_dir: Path
    series: str = None

    @classmethod
    def prepare(cls, source, target, udid, backup_root, series=None):
        selected = board_config(series) if series is not None else None
        if not re.fullmatch(re.escape(OVERLAY_DIR) + r"device-[A-Za-z0-9_-]+\.plist", target):
            raise ValueError("Use the resolved Overlay/device-*.plist path, not a symlink or bundle path.")
        if not re.fullmatch(r"[A-Za-z0-9-]{8,64}", udid):
            raise ValueError("Enter the connected iPhone UDID.")
        raw = Path(source).read_bytes()
        patched = patch_overlay(raw)
        digest = hashlib.sha256(raw).hexdigest()
        directory = Path(backup_root) / udid / digest
        directory.mkdir(parents=True, exist_ok=True)
        original_path = directory / "original.plist"
        if original_path.exists() and original_path.read_bytes() != raw:
            raise ValueError("Backup mismatch; refusing to overwrite it.")
        if not original_path.exists():
            with original_path.open("xb") as stream:
                stream.write(raw)
        (directory / "patched.plist").write_bytes(patched)
        (directory / "manifest.json").write_text(json.dumps({
            "target": target, "udid": udid, "carrier": "TIM_Italy.bundle",
            "mccmnc": "22201", "sha256": digest,
            "series": series, "boardconfig": selected[2] if selected else None,
            "identifiers": selected[3] if selected else [],
            "identity": "User confirmed; not automatically verified on device",
        }, indent=2))
        return cls(raw, patched, target, udid, directory, series)

    @classmethod
    def load_backup(cls, manifest):
        manifest = Path(manifest)
        data = json.loads(manifest.read_text())
        raw = (manifest.parent / "original.plist").read_bytes()
        if hashlib.sha256(raw).hexdigest() != data["sha256"]:
            raise ValueError("Original backup checksum mismatch.")
        return cls.prepare(manifest.parent / "original.plist", data["target"],
                           data["udid"], manifest.parent.parent.parent, data.get("series"))

    def validate_device(self, udid, version, identifier=None):
        if self.series is not None and identifier not in board_config(self.series)[3]:
            raise ValueError("Connected iPhone identifier does not match the selected BoardConfig series.")
        if udid != self.udid:
            raise ValueError("TIM overlay belongs to a different iPhone UDID.")
        if version != "26.1":
            raise ValueError("This experiment is restricted to iOS 26.1.")


class OverlayState:
    job = None
    mode = None

    @classmethod
    def clear(cls):
        cls.job = None
        cls.mode = None
