"""Publish validated assets from a tested main tag, keeping incomplete releases private."""

import argparse
import ast
import hashlib
import json
import os
import re
import tomllib
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def release_notes(version, root=ROOT):
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    section = re.search(
        r"(?ms)^## \[" + re.escape(version) + r"\][^\n]*\n(.*?)(?=^## |\Z)", changelog
    )
    if section is None:
        raise ValueError("Version missing from CHANGELOG.md")
    return section.group(1).strip()


def version_metadata(tag, manifest_version, project_version, internal_version):
    match = re.fullmatch(r"v(\d+\.\d+\.\d+)(?:-(alpha|beta|rc)\.([1-9]\d*))?", tag)
    if match is None:
        raise ValueError("Unsupported release tag")
    base, stage, sequence = match.groups()
    normalized = base + ({"alpha": "a", "beta": "b", "rc": "rc"}[stage] + sequence if stage else "")
    if (
        manifest_version != tag[1:]
        or internal_version != manifest_version
        or project_version != normalized
    ):
        raise ValueError("Tag, manifest, PEP 440 project and internal versions do not match")
    return {"version": manifest_version, "prerelease": stage is not None}


def release_plan(tag, root=ROOT, dist=None):
    component = root / "custom_components/melcloud_diagnostics"
    manifest = json.loads((component / "manifest.json").read_text(encoding="utf-8"))
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    constants = ast.parse((component / "const.py").read_text(encoding="utf-8"))
    internal = next(
        ast.literal_eval(n.value)
        for n in constants.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in n.targets)
    )
    metadata = version_metadata(tag, manifest["version"], project["project"]["version"], internal)
    version = metadata["version"]
    dist = dist if dist is not None else root / "dist"
    assets = [
        dist / f"melcloud-diagnostics-{version}.zip",
        dist / "melcloud_diagnostics.zip",
        dist / "SHA256SUMS",
    ]
    checksums = {}
    for line in assets[2].read_text(encoding="utf-8").splitlines():
        digest, name = line.split()
        if name in checksums:
            raise ValueError("Duplicate checksum record")
        checksums[name] = digest
    if set(checksums) != {p.name for p in assets[:2]}:
        raise ValueError("Unexpected checksum inventory")
    for path in assets[:2]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != checksums[path.name]:
            raise ValueError("Package checksum mismatch")
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None or len(archive.namelist()) != len(
                set(archive.namelist())
            ):
                raise ValueError("Corrupt or duplicate ZIP entries")
            prefix = (
                ""
                if path.name == "melcloud_diagnostics.zip"
                else "custom_components/melcloud_diagnostics/"
            )
            if json.loads(archive.read(prefix + "manifest.json")) != manifest:
                raise ValueError("Packaged manifest mismatch")
            component_files = {
                p.relative_to(component).as_posix()
                for p in component.rglob("*")
                if p.is_file()
                and "__pycache__" not in p.parts
                and p.suffix in (".py", ".json", ".png", ".svg")
            }
            expected = {prefix + p for p in component_files} | {"LICENSE"}
            if prefix:
                expected |= {"README.md"} | {
                    p.relative_to(root).as_posix()
                    for p in (root / "docs").rglob("*")
                    if p.is_file() and p.suffix in (".md", ".png")
                }
            if set(archive.namelist()) != expected:
                raise ValueError("Unexpected package inventory")
    hacs = json.loads((root / "hacs.json").read_text(encoding="utf-8"))
    if hacs.get("zip_release") is not True or hacs.get("filename") != "melcloud_diagnostics.zip":
        raise ValueError("HACS asset configuration mismatch")
    return metadata, assets, release_notes(version, root)


def publish(tag, repository, expected_sha, request, *, root=ROOT, dist=None):
    metadata, assets, notes = release_plan(tag, root, dist)
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository) or not re.fullmatch(
        r"[0-9a-f]{40}", expected_sha
    ):
        raise ValueError("Invalid repository or expected commit")
    base = f"https://api.github.com/repos/{repository}"
    existing = request("GET", f"{base}/releases/tags/{quote(tag, safe='')}", allow_missing=True)
    if existing is not None:
        raise ValueError("Release already exists; inspect it manually, never overwrite")
    ref = request("GET", f"{base}/git/ref/tags/{quote(tag, safe='')}")
    main = request("GET", f"{base}/branches/main")
    if ref["object"].get("type") != "commit" or ref["object"].get("sha") != expected_sha:
        raise ValueError("Release tag does not identify the expected commit")
    if main["commit"]["sha"] != expected_sha:
        raise ValueError("Release tag must match current main")
    attributes = {
        "tag_name": tag,
        "name": f"MELCloud Diagnostics {metadata['version']}",
        "body": notes,
        "draft": True,
        "prerelease": metadata["prerelease"],
        "make_latest": "false" if metadata["prerelease"] else "true",
    }
    release = request("POST", f"{base}/releases", attributes)
    release_url = f"{base}/releases/{release['id']}"
    upload = release["upload_url"].split("{", 1)[0]
    if not upload.startswith(f"https://uploads.github.com/repos/{repository}/releases/"):
        raise ValueError("Unexpected GitHub upload endpoint; release remains draft")
    expected = {}
    for path in assets:
        data = path.read_bytes()
        expected[path.name] = (len(data), "sha256:" + hashlib.sha256(data).hexdigest())
        request("POST", upload + "?" + urlencode({"name": path.name}, quote_via=quote), data)
    staged = request("GET", release_url)
    actual = {
        a["name"]: (a["size"], a.get("digest"))
        for a in staged["assets"]
        if a["state"] == "uploaded"
    }
    if (
        actual != expected
        or staged["draft"] is not True
        or staged["prerelease"] != metadata["prerelease"]
    ):
        raise ValueError("Uploaded assets or release state differ; release remains draft")
    request(
        "PATCH",
        release_url,
        {
            "draft": False,
            "prerelease": metadata["prerelease"],
            "make_latest": attributes["make_latest"],
        },
    )
    published = request("GET", release_url)
    if (
        published["draft"]
        or published["prerelease"] != metadata["prerelease"]
        or published["tag_name"] != tag
    ):
        raise ValueError("Final release state could not be verified")
    print(f"Published {published['html_url']}")
    return published


def main(tag):
    token = os.environ["GITHUB_TOKEN"]  # Workflow token only; never printed or persisted.

    def request(method, url, payload=None, *, allow_missing=False):
        binary = isinstance(payload, bytes)
        req = Request(
            url,
            data=payload
            if binary
            else json.dumps(payload).encode()
            if payload is not None
            else None,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "MelCloudHA-release",
                "Content-Type": "application/octet-stream" if binary else "application/json",
            },
        )
        try:
            with urlopen(req, timeout=120) as response:
                return json.load(response)
        except HTTPError as error:
            if allow_missing and error.code == 404:
                return None
            raise RuntimeError(f"GitHub release request failed (HTTP {error.code})") from None

    publish(tag, os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_SHA"], request)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    main(parser.parse_args().tag)
