"""Offline release gate tests. All GitHub traffic is simulated, no credentials required."""

import hashlib
import json
import shutil
import subprocess
import sys
import tomllib
import zipfile
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from awesomeversion import AwesomeVersion
from packaging.version import Version

from tools.publish_release import publish, release_plan, version_metadata

TAG = "v0.3.0"
SHA = "a" * 40
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def packages(tmp_path_factory):
    folder = tmp_path_factory.mktemp("release")
    subprocess.run(
        [sys.executable, "tools/build_release.py", "--output-dir", str(folder)],
        check=True,
        capture_output=True,
    )
    return folder


class GitHub:
    def __init__(self, *, exists=False, corrupt=False, fail_upload=False, sha=SHA):
        self.calls = []
        self.release = None
        self.exists, self.corrupt, self.fail_upload, self.sha = exists, corrupt, fail_upload, sha

    def __call__(self, method, url, payload=None, **kwargs):
        self.calls.append((method, url, deepcopy(payload)))
        if "/releases/tags/" in url:
            return {"id": 1} if self.exists else None
        if "/git/ref/tags/" in url:
            return {"object": {"type": "commit", "sha": self.sha}}
        if url.endswith("/branches/main"):
            return {"commit": {"sha": self.sha}}
        if method == "POST" and url.endswith("/releases"):
            self.release = deepcopy(payload) | {
                "id": 7,
                "assets": [],
                "upload_url": "https://uploads.github.com/repos/synthetic/repository/releases/7/assets{?name}",
                "html_url": "https://github.com/synthetic/repository/releases/tag/" + TAG,
            }
        elif method == "POST":
            if self.fail_upload:
                raise RuntimeError("synthetic upload failure")
            name = parse_qs(urlparse(url).query)["name"][0]
            self.release["assets"].append(
                {
                    "name": name,
                    "state": "uploaded",
                    "size": len(payload),
                    "digest": "sha256:"
                    + ("0" * 64 if self.corrupt else hashlib.sha256(payload).hexdigest()),
                }
            )
        elif method == "PATCH":
            self.release.update(payload)
        return deepcopy(self.release)


def test_version_is_equivalent_for_python_homeassistant_and_tag(packages):
    manifest = json.loads(
        (ROOT / "custom_components/melcloud_diagnostics/manifest.json").read_text()
    )
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert manifest["version"] == "0.3.0"
    assert project["project"]["version"] == "0.3.0"
    assert Version(manifest["version"]) == Version(project["project"]["version"])
    assert AwesomeVersion(manifest["version"]).valid and not AwesomeVersion(manifest["version"]).beta
    assert AwesomeVersion("0.2.1") < AwesomeVersion(manifest["version"]) == AwesomeVersion("0.3.0")
    metadata, assets, notes = release_plan(TAG, dist=packages)
    assert metadata["prerelease"] is False and "Nessun collaudo" in notes and len(assets) == 3


@pytest.mark.parametrize(
    "tag,python,prerelease",
    [
        ("v0.2.1", "0.2.1", False),
        ("v0.3.0-beta.1", "0.3.0b1", True),
        ("v0.3.0-rc.2", "0.3.0rc2", True),
        ("v0.3.0", "0.3.0", False),
    ],
)
def test_stable_and_prerelease_are_explicitly_distinguished(tag, python, prerelease):
    assert version_metadata(tag, tag[1:], python, tag[1:])["prerelease"] is prerelease


@pytest.mark.parametrize(
    "values",
    [
        (TAG, "0.3.0", "0.3.0b1", "0.3.0-beta.1"),
        (TAG, "0.3.0-beta.1", "0.3.0", "0.3.0-beta.1"),
        (TAG, "0.3.0-beta.1", "0.3.0b1", "0.2.1"),
        ("v0.3.0-nightly", "0.3.0-nightly", "0.3.0.dev1", "0.3.0-nightly"),
    ],
)
def test_inconsistent_or_unrecognized_versions_block_publication(values):
    with pytest.raises(ValueError):
        version_metadata(*values)


def test_stable_release_is_draft_until_assets_are_verified_then_becomes_latest(packages):
    api = GitHub()
    result = publish(TAG, "synthetic/repository", SHA, api, dist=packages)
    create = next(
        payload
        for method, url, payload in api.calls
        if method == "POST" and url.endswith("/releases")
    )
    assert create["draft"] is True and create["prerelease"] is False
    assert create["make_latest"] == "true"
    assert result["prerelease"] is False and result["draft"] is False
    assert {a["name"] for a in result["assets"]} == {
        "melcloud-diagnostics-0.3.0.zip",
        "melcloud_diagnostics.zip",
        "SHA256SUMS",
    }
    assert [method for method, _, _ in api.calls].count("PATCH") == 1


@pytest.mark.parametrize("flags", [{"corrupt": True}, {"fail_upload": True}])
def test_upload_or_digest_failure_never_publishes_draft(packages, flags):
    api = GitHub(**flags)
    with pytest.raises((ValueError, RuntimeError)):
        publish(TAG, "synthetic/repository", SHA, api, dist=packages)
    assert api.release["draft"] is True
    assert not any(method == "PATCH" for method, _, _ in api.calls)


@pytest.mark.parametrize("flags", [{"exists": True}, {"sha": "b" * 40}])
def test_existing_release_or_wrong_commit_is_never_modified(packages, flags):
    api = GitHub(**flags)
    with pytest.raises(ValueError):
        publish(TAG, "synthetic/repository", SHA, api, dist=packages)
    assert all(method == "GET" for method, _, _ in api.calls)


def test_bad_checksum_blocks_before_any_remote_action(packages, tmp_path):
    for path in packages.iterdir():
        shutil.copy2(path, tmp_path / path.name)
    (tmp_path / "melcloud_diagnostics.zip").write_bytes(b"synthetic corruption")
    api = GitHub()
    with pytest.raises(ValueError):
        publish(TAG, "synthetic/repository", SHA, api, dist=tmp_path)
    assert api.calls == []


def test_packages_are_reproducible_and_contain_no_local_paths(packages, tmp_path):
    subprocess.run(
        [sys.executable, "tools/build_release.py", "--output-dir", str(tmp_path)],
        check=True,
        capture_output=True,
    )
    for name in ("melcloud_diagnostics.zip", "melcloud-diagnostics-0.3.0.zip", "SHA256SUMS"):
        assert (packages / name).read_bytes() == (tmp_path / name).read_bytes()
    with zipfile.ZipFile(packages / "melcloud_diagnostics.zip") as archive:
        assert archive.testzip() is None
        assert not any(
            "codex.txt" in name or "private-captures" in name or name.startswith("dist/")
            for name in archive.namelist()
        )
