"""Experimental, imported TIM carrier overlay; no signature bypass."""
import copy
import hashlib
import json
import plistlib
import re
from dataclasses import dataclass
from pathlib import Path

OVERLAY_DIR = "/var/mobile/Library/Carrier Bundles/Overlay/"


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

    @classmethod
    def prepare(cls, source, target, udid, backup_root):
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
            "identity": "User confirmed; not automatically verified on device",
        }, indent=2))
        return cls(raw, patched, target, udid, directory)

    @classmethod
    def load_backup(cls, manifest):
        manifest = Path(manifest)
        data = json.loads(manifest.read_text())
        raw = (manifest.parent / "original.plist").read_bytes()
        if hashlib.sha256(raw).hexdigest() != data["sha256"]:
            raise ValueError("Original backup checksum mismatch.")
        return cls.prepare(manifest.parent / "original.plist", data["target"],
                           data["udid"], manifest.parent.parent.parent)

    def validate_device(self, udid, version):
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
