"""Extract XABA v2/v3 assembly stores from MAUI split APKs; never load app code.

Format reference: dotnet/android Documentation/project-docs/AssemblyStores.md.
"""

import argparse
import io
import json
import struct
import zipfile
from pathlib import Path


def lz4_block(data, expected):
    result = bytearray()
    pos = 0

    def read_length(initial):
        nonlocal pos
        value = initial
        if initial == 15:
            while True:
                extra = data[pos]
                pos += 1
                value += extra
                if extra != 255:
                    break
        return value

    while pos < len(data):
        token = data[pos]
        pos += 1
        size = read_length(token >> 4)
        result.extend(data[pos : pos + size])
        pos += size
        if pos == len(data):
            break
        distance = struct.unpack_from("<H", data, pos)[0]
        pos += 2
        size = read_length(token & 15) + 4
        if not 0 < distance <= len(result):
            raise ValueError("Invalid LZ4 distance")
        for _ in range(size):
            result.append(result[-distance])
        if len(result) > expected:
            raise ValueError("LZ4 output exceeds declared size")
    if len(result) != expected:
        raise ValueError("LZ4 output size mismatch")
    return bytes(result)


def extract(xapk, output):
    with zipfile.ZipFile(xapk) as archive:
        with zipfile.ZipFile(io.BytesIO(archive.read("config.arm64_v8a.apk"))) as split:
            elf = split.read("lib/arm64-v8a/libassembly-store.so")
    if elf[:6] != b"\x7fELF\x02\x01":
        raise ValueError("Expected little-endian ELF64")
    section_table = struct.unpack_from("<Q", elf, 40)[0]
    stride, count, names_index = struct.unpack_from("<HHH", elf, 58)
    sections = [
        struct.unpack_from("<IIQQQQIIQQ", elf, section_table + i * stride) for i in range(count)
    ]
    names_section = sections[names_index]
    names = elf[names_section[4] : names_section[4] + names_section[5]]
    payload = None
    for section in sections:
        name = names[section[0] :].split(b"\0", 1)[0]
        if name == b"payload":
            payload = elf[section[4] : section[4] + section[5]]
    if payload is None:
        raise ValueError("No ELF payload section")
    magic, version, count, _, index_size = struct.unpack_from("<5I", payload)
    if magic != 0x41424158 or (version & 0xFFFF) not in (2, 3):
        raise ValueError(f"Unsupported XABA header: {magic:x}, version {version:x}")
    descriptor_start = 20 + index_size
    name_pos = descriptor_start + count * 28
    output.mkdir(parents=True, exist_ok=True)
    inventory = []
    for index in range(count):
        _, offset, size, *_ = struct.unpack_from("<7I", payload, descriptor_start + index * 28)
        name_size = struct.unpack_from("<I", payload, name_pos)[0]
        name_pos += 4
        name = payload[name_pos : name_pos + name_size].decode("utf-8")
        name_pos += name_size
        blob = payload[offset : offset + size]
        if blob[:4] == b"XALZ":
            expected = struct.unpack_from("<I", blob, 8)[0]
            blob = lz4_block(blob[12:], expected)
        if blob[:2] != b"MZ":
            raise ValueError(f"Not a PE assembly: {name}")
        target = output / (name if name.endswith(".dll") else name + ".dll")
        if not target.resolve().is_relative_to(output.resolve()):
            raise ValueError("Unsafe assembly filename")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        inventory.append({"name": name, "stored_bytes": size, "pe_bytes": len(blob)})
    (output / "inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    print(f"Extracted {count} assemblies, all with valid MZ headers, into {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xapk", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    extract(args.xapk, args.output)
