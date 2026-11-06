"""Version-lockstep test — every version surface must agree on the shipped version.

Surfaces covered: the ``VERSION`` file, ``pyproject.toml`` [project].version,
``abldrift.__version__`` (which feeds ``abldrift --version`` via
click.version_option), the README badge line in both locales, ``web/site.json``
(it has no top-level content_version — only ``meta.content_version`` and
``footer.tag``), and the newest ``CHANGELOG.md`` heading. The doc surfaces are
included because they are the ones that historically lagged a release.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from click.testing import CliRunner

from abldrift import __version__
from abldrift.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED = "0.4.0"


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_dunder_version_is_lockstep():
    assert __version__ == EXPECTED


def test_version_file_matches():
    assert (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip() == EXPECTED


def test_pyproject_version_matches():
    pyproject = tomllib.loads(_read("pyproject.toml"))
    assert pyproject["project"]["version"] == EXPECTED


def test_cli_version_flag_prints_lockstep_version():
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert f"abldrift, version {EXPECTED}" in result.output


def test_readme_badges_match_both_locales():
    for name in ("README.md", "README.en.md"):
        assert f"`v{EXPECTED}`" in _read(name), f"{name} badge line is stale"


def test_site_json_version_keys_match():
    site = json.loads(_read("web/site.json"))
    assert site["meta"]["content_version"] == f"v{EXPECTED}"
    # The footer tag carries the bare version, not the v-prefixed one.
    assert site["footer"]["tag"].startswith(f"{EXPECTED} ")


def test_changelog_newest_heading_is_the_shipped_version():
    headings = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", _read("CHANGELOG.md"), re.MULTILINE)
    assert headings, "CHANGELOG has no version headings"
    assert headings[0] == EXPECTED
