"""Build an installable source ZIP without APKs, credentials or analysis artifacts."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output-dir", type=Path, default=root / "dist")
args = parser.parse_args()


def add_file(archive, path, name):
    """Stable timestamps, permissions and text newlines on Windows and Linux."""
    data = path.read_bytes()
    if path.suffix in (".py", ".json", ".md", ".svg") or path.name == "LICENSE":
        data = data.replace(b"\r\n", b"\n")
    info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    # Assets are small; storing avoids platform/zlib-dependent checksum differences.
    archive.writestr(info, data)


component = root / "custom_components" / "melcloud_diagnostics"
version = json.loads((component / "manifest.json").read_text(encoding="utf-8"))["version"]
output = args.output_dir / f"melcloud-diagnostics-{version}.zip"
output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(component.rglob("*"), key=lambda path: path.as_posix()):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix in (".py", ".json", ".png", ".svg")
        ):
            add_file(archive, path, path.relative_to(root).as_posix())
    add_file(archive, root / "README.md", "README.md")
    add_file(archive, root / "LICENSE", "LICENSE")
    for path in sorted((root / "docs").rglob("*"), key=lambda path: path.as_posix()):
        if path.is_file() and path.suffix in (".md", ".png"):
            add_file(archive, path, path.relative_to(root).as_posix())
with output.open("rb") as source:
    digest = hashlib.file_digest(source, "sha256").hexdigest()
output.with_suffix(".sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8", newline="\n")
print(f"{output}\nSHA256 {digest}")

# HACS extracts this archive directly into custom_components/<domain>.
# It must NOT contain the custom_components/domain prefix.
hacs_output = output.parent / "melcloud_diagnostics.zip"
with zipfile.ZipFile(hacs_output, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(component.rglob("*"), key=lambda path: path.as_posix()):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix in (".py", ".json", ".png", ".svg")
        ):
            add_file(archive, path, path.relative_to(component).as_posix())
    add_file(archive, root / "LICENSE", "LICENSE")
with hacs_output.open("rb") as source:
    hacs_digest = hashlib.file_digest(source, "sha256").hexdigest()
(output.parent / "SHA256SUMS").write_text(
    f"{digest}  {output.name}\n{hacs_digest}  {hacs_output.name}\n", encoding="utf-8", newline="\n"
)
print(f"HACS: {hacs_output}")
