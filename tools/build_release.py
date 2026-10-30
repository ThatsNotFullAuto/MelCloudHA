"""Build an installable source ZIP without APKs, credentials or analysis artifacts."""

import hashlib
import json
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
component = root / "custom_components" / "melcloud_diagnostics"
version = json.loads((component / "manifest.json").read_text(encoding="utf-8"))["version"]
output = root / "dist" / f"melcloud-diagnostics-{version}.zip"
output.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(component.rglob("*")):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix in (".py", ".json", ".png", ".svg")
        ):
            archive.write(path, path.relative_to(root).as_posix())
    archive.write(root / "README.md", "README.md")
    archive.write(root / "LICENSE", "LICENSE")
    for path in sorted((root / "docs").rglob("*.md")):
        archive.write(path, path.relative_to(root).as_posix())
with output.open("rb") as source:
    digest = hashlib.file_digest(source, "sha256").hexdigest()
output.with_suffix(".sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
print(f"{output}\nSHA256 {digest}")

# HACS extracts this archive directly into custom_components/<domain>.
# It must NOT contain the custom_components/domain prefix.
hacs_output = output.parent / "melcloud_diagnostics.zip"
with zipfile.ZipFile(hacs_output, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(component.rglob("*")):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix in (".py", ".json", ".png", ".svg")
        ):
            archive.write(path, path.relative_to(component).as_posix())
    archive.write(root / "LICENSE", "LICENSE")
with hacs_output.open("rb") as source:
    hacs_digest = hashlib.file_digest(source, "sha256").hexdigest()
(output.parent / "SHA256SUMS").write_text(
    f"{digest}  {output.name}\n{hacs_digest}  {hacs_output.name}\n", encoding="utf-8"
)
print(f"HACS: {hacs_output}")
