"""Version-lockstep test — every version surface must agree on the shipped version.

Surfaces covered (see the version-bump milestone): the ``VERSION`` file,
``pyproject.toml`` [project].version, ``abldrift.__version__`` (which feeds
``abldrift --version`` via click.version_option). The CHANGELOG entry and
web/site.json meta.content_version are repo surfaces checked by grep in the
release process.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from click.testing import CliRunner

from abldrift import __version__
from abldrift.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED = "0.2.1"


def test_dunder_version_is_lockstep():
    assert __version__ == EXPECTED


def test_version_file_matches():
    assert (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip() == EXPECTED


def test_pyproject_version_matches():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == EXPECTED


def test_cli_version_flag_prints_lockstep_version():
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert f"abldrift, version {EXPECTED}" in result.output
