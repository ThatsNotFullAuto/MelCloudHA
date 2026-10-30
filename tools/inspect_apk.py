"""Inspect APK identity without installing or executing it (Python stdlib only)."""

import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path


def manifest_identity(data: bytes) -> dict:
    """Read manifest/application attributes from Android binary XML."""
    if struct.unpack_from("<H", data)[0] != 0x0003:
        raise ValueError("Expected Android binary XML")
    strings = []
    result = {}
    offset = struct.unpack_from("<H", data, 2)[0]
    while offset < len(data):
        kind, header_size, size = struct.unpack_from("<HHI", data, offset)
        if size < header_size or size == 0 or offset + size > len(data):
            raise ValueError("Invalid binary XML chunk")
        if kind == 0x0001:  # String pool
            count, _, flags, start, _ = struct.unpack_from("<IIIII", data, offset + 8)

            def length(pos, utf8):
                if utf8:
                    value = data[pos]
                    if value & 0x80:
                        return ((value & 0x7F) << 8) | data[pos + 1], pos + 2
                    return value, pos + 1
                value = struct.unpack_from("<H", data, pos)[0]
                if value & 0x8000:
                    return ((value & 0x7FFF) << 16) | struct.unpack_from("<H", data, pos + 2)[
                        0
                    ], pos + 4
                return value, pos + 2

            for index in range(count):
                relative = struct.unpack_from("<I", data, offset + header_size + index * 4)[0]
                pos = offset + start + relative
                if flags & 0x100:
                    _, pos = length(pos, True)
                    length_bytes, pos = length(pos, True)
                    strings.append(data[pos : pos + length_bytes].decode("utf-8", "replace"))
                else:
                    length_chars, pos = length(pos, False)
                    strings.append(data[pos : pos + length_chars * 2].decode("utf-16le", "replace"))
        elif kind == 0x0102:  # Start element; attributes are relative to attr extension
            extension = offset + header_size
            _, name, attr_start, attr_size, attr_count = struct.unpack_from(
                "<IIHHH", data, extension
            )
            tag = strings[name]
            if tag in ("manifest", "application", "uses-sdk"):
                attrs = {}
                for index in range(attr_count):
                    pos = extension + attr_start + index * attr_size
                    _, attr_name, raw, _, _, value_type, value = struct.unpack_from(
                        "<IIIHBBI", data, pos
                    )
                    if raw != 0xFFFFFFFF:
                        decoded = strings[raw]
                    elif value_type == 3:
                        decoded = strings[value]
                    elif value_type == 0x12:
                        decoded = bool(value)
                    elif value_type in (0x10, 0x11):
                        decoded = value
                    else:
                        decoded = {"type": value_type, "value": value}
                    attrs[strings[attr_name]] = decoded
                result[tag] = attrs
        offset += size
    return result


def inspect(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        identity = manifest_identity(archive.read("AndroidManifest.xml"))
        dex = [item.filename for item in archive.infolist() if item.filename.endswith(".dex")]
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    return {
        "file": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": digest,
        "identity": identity,
        "dex_files": dex,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(inspect(args.apk), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
    print(report)
