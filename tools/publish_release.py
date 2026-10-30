"""Publish a tested tag using GitHub Actions' ephemeral token; never print secrets."""

import argparse
import json
import os
import re
import tomllib
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def release_notes(version):
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    section = re.search(
        r"(?ms)^## \[" + re.escape(version) + r"\][^\n]*\n(.*?)(?=^## |\Z)", changelog
    )
    if section is None:
        raise ValueError("Version missing from CHANGELOG.md")
    return section.group(1).strip()


def main(tag):
    manifest = json.loads(
        (ROOT / "custom_components/melcloud_diagnostics/manifest.json").read_text(encoding="utf-8")
    )
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = manifest["version"]
    if tag != f"v{version}" or project["project"]["version"] != version:
        raise ValueError("Tag, manifest and project versions must match")
    token = os.environ["GITHUB_TOKEN"]
    repository = os.environ["GITHUB_REPOSITORY"]
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
        raise ValueError("Invalid GitHub repository")

    def request(url, payload, content_type="application/json"):
        req = Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": content_type,
                "User-Agent": "MelCloudHA-release",
            },
        )
        try:
            with urlopen(req, timeout=120) as response:
                return json.load(response)
        except HTTPError as error:
            raise RuntimeError(f"GitHub release request failed (HTTP {error.code})") from None

    assets = [
        ROOT / "dist" / f"melcloud-diagnostics-{version}.zip",
        ROOT / "dist/melcloud_diagnostics.zip",
        ROOT / "dist/SHA256SUMS",
    ]
    if not all(path.is_file() for path in assets):
        raise ValueError("Build the release packages first")
    release = request(
        f"https://api.github.com/repos/{repository}/releases",
        json.dumps(
            {
                "tag_name": tag,
                "name": f"MELCloud Diagnostics {version}",
                "body": release_notes(version),
                "draft": False,
                "prerelease": False,
            }
        ).encode(),
    )
    upload = release["upload_url"].split("{", 1)[0]
    if not upload.startswith(f"https://uploads.github.com/repos/{repository}/releases/"):
        raise ValueError("Unexpected GitHub upload endpoint")
    for path in assets:
        request(
            upload + "?" + urlencode({"name": path.name}, quote_via=quote),
            path.read_bytes(),
            "application/zip" if path.suffix == ".zip" else "text/plain",
        )
        print(f"Uploaded {path.name}")
    print(f"Published {release['html_url']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    main(parser.parse_args().tag)
