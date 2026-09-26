"""Centralized constants for the release subpackage.

The release protocol derives every version bump from the Conventional Commits
subject that a merged pull request leaves on its merge commit, writes the
version only through the protocol, and identifies a release by one tag shape.
These are external contracts (Conventional Commits, PEP 440, Git), so they are
constants rather than configuration.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsRelease:
    """Release infrastructure constants."""

    VERSION_RELEASE_SEGMENTS: ClassVar[int] = 3

    class ReleasePhase(StrEnum):
        """Canonical release phases; each one is one Make ``WHAT`` selector."""

        PLAN = "plan"
        VERSION = "version"
        TAG = "tag"
        BUILD = "build"
        PUBLISH = "publish"

    class VersionBump(StrEnum):
        """Canonical semantic-version bump kinds, ordered by significance."""

        NONE = "none"
        PATCH = "patch"
        MINOR = "minor"
        MAJOR = "major"

    VERSION_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^version\s*=\s*['\"](.+?)['\"]", re.MULTILINE
    )
    CONVENTIONAL_SUBJECT_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(?P<type>[a-z]+)(?:\([^)]+\))?(?P<breaking>!)?: \S"
    )
    "Conventional Commits subject: ``type(scope)!: description``."
    PULL_REQUEST_MERGE_SUBJECT_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^Merge pull request #\d+\b"
    )
    "GitHub's default merge subject, which carries no release information."
    TAG_FORMAT: ClassVar[str] = "v{version}"
    RELEASE_BRANCH: ClassVar[str] = "release/next"
    "One bot-owned lane per repository; the open release pull request lives here."
    RELEASE_COMMIT_SUBJECT: ClassVar[str] = "chore(release): v{version}"
    RELEASE_COMMIT_SUBJECT_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^chore\(release\): v(?P<version>\S+?)(?: \(#\d+\))?$"
    )
    "The release commit as Git carries it: GitHub appends ` (#N)` when merging."
    RELEASE_PLAN_FILENAME: ClassVar[str] = "plan.json"
    RELEASE_NOTES_FILENAME: ClassVar[str] = "RELEASE_NOTES.md"
    RELEASE_REPORT_FILENAME: ClassVar[str] = "build-report.json"
    PYPI_UPLOAD_URL: ClassVar[str] = "https://upload.pypi.org/legacy/"
    "Canonical verified-artifact upload endpoint."
    GH: ClassVar[str] = "gh"
    RELEASE_LICENSE_NAMES: ClassVar[frozenset[str]] = frozenset({
        "copying",
        "copying.md",
        "copying.txt",
        "license",
        "license.md",
        "license.txt",
    })
    "Casefolded basenames a release accepts as the project's single license."
    RELEASE_OPERATIONAL_ROOTS: ClassVar[frozenset[str]] = frozenset({
        ".git",
        ".github",
        ".reports",
    })
    "Repository-operational trees rejected at an archive's content root."
    RELEASE_SENSITIVE_PARTS: ClassVar[frozenset[str]] = frozenset({
        ".env",
        ".secrets.baseline",
        "__pycache__",
    })
    RELEASE_SENSITIVE_PREFIXES: ClassVar[tuple[str, ...]] = (".env.", ".gitleaks")
    RELEASE_SENSITIVE_SUFFIXES: ClassVar[tuple[str, ...]] = (
        ".jks",
        ".key",
        ".keystore",
        ".p12",
        ".pem",
        ".pfx",
    )
    "Path parts that never ship, at any depth, unless codegen owns the file."
    RELEASE_SDIST_ROOT_DIRS: ClassVar[frozenset[str]] = frozenset({"config", "src"})
    RELEASE_SDIST_ROOT_FILES: ClassVar[frozenset[str]] = frozenset({
        ".gitignore",
        "pkg-info",
        "pyproject.toml",
    })
    "The public sdist boundary besides the license and README files."


__all__: list[str] = ["FlextInfraConstantsRelease"]
