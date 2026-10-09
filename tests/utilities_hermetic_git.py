"""Hermetic Git provider: local bare mirrors that keep fixture sources real.

Governed fixtures declare their internal dependencies with direct Git sources
(a source-less internal dependency fails loudly), so ``uv lock`` inside a
fixture resolves those sources. These helpers serve the exact locked revisions
from local bare mirrors built out of objects this checkout already holds, and
the environment they return makes any network transport fail instead of
silently reaching a remote.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from flext_tests import tm

from flext_infra import config, u
from tests import c, t
from tests.utilities_fixture_project import TestsFlextInfraUtilitiesProjectFixtureMixin
from tests.utilities_toml import TestsFlextInfraUtilitiesTomlMixin


class TestsFlextInfraUtilitiesHermeticGitMixin:
    """Build and route the fixture provider through local Git mirrors."""

    @staticmethod
    def locked_git_sources(
        project_root: Path,
    ) -> t.VariadicTuple[t.Triple[str, str, str]]:
        """Return every ``(url, rev, sha)`` Git source the checkout lock pins.

        The checkout itself is not in its lock; it joins as the infrastructure
        repository the fixture provider serves, at the checked-out commit.

        Returns:
            Every ``(url, rev, sha)`` Git source the checkout lock pins.

        """
        toml = TestsFlextInfraUtilitiesTomlMixin
        lock = (project_root / c.Infra.UV_LOCK_FILENAME).read_text(encoding="utf-8")
        sources: t.MutableMappingKV[str, t.Triple[str, str, str]] = {}
        for package in toml.toml_tables_at(lock, "package"):
            source = toml.toml_mapping(package.get("source"))
            locator = source.get("git")
            if not isinstance(locator, str):
                continue
            parts = urlsplit(locator)
            url = f"{parts.scheme}://{parts.netloc}{parts.path}"
            (rev,) = parse_qs(parts.query)["rev"]
            sources[url] = (url, unquote(rev), parts.fragment)
        fixture = TestsFlextInfraUtilitiesProjectFixtureMixin
        infra = fixture.repository_ref(
            config.Infra.codegen.infra_repository.distribution,
        ).url
        head = tm.ok(
            u.Cli.capture(
                [c.Infra.GIT, "rev-parse", c.Infra.GIT_HEAD],
                cwd=project_root,
            ),
        ).strip()
        sources[infra] = (infra, fixture.provider_branch(), head)
        return tuple(sources.values())

    @staticmethod
    def build_git_mirrors(project_root: Path, mirrors: Path) -> t.StrSequence:
        """Mirror each locked source's exact commit under its host and path.

        Objects come from this checkout or from the Git databases ``make setup``
        and ``make upg`` fetched into the native uv cache selected by the
        activated environment. Query uv itself so the fixture follows the same
        cache configuration as provisioning. No source is fetched from its remote;
        a commit found nowhere locally fails loudly: ``make setup`` provisions it.
        Each mirror borrows the origin database through ``objects/info/alternates``
        and pins only the branch ref: full history at zero copy cost (git
        refuses to update shallow roots, so a shallow mirror cannot serve a
        client whose uv cache lacks the history).

        Returns:
            The resulting ``t.StrSequence``.

        Raises:
            FileNotFoundError: If locked Git source is not held locally.

        """
        cache = Path(
            tm.ok(
                u.Cli.capture([c.Infra.UV, "cache", "dir"], cwd=project_root),
            ).strip(),
        )
        databases = (project_root, *sorted(cache.glob("git-v*/db/*")))
        mirrored: list[str] = []
        for (
            url,
            rev,
            sha,
        ) in TestsFlextInfraUtilitiesHermeticGitMixin.locked_git_sources(project_root):
            origin = next(
                (
                    database
                    for database in databases
                    if u.Cli.process_succeeded(
                        tm.ok(
                            u.Cli.run_raw(
                                [c.Infra.GIT, "cat-file", "-e", f"{sha}^{{commit}}"],
                                cwd=database,
                            ),
                        ).outcome,
                    )
                ),
                None,
            )
            if origin is None:
                msg = f"locked Git source is not held locally: {url}@{sha}"
                raise FileNotFoundError(msg)
            parts = urlsplit(url)
            mirror = mirrors / parts.netloc / parts.path.lstrip("/")
            tm.ok(
                u.Cli.run_checked([
                    c.Infra.GIT,
                    "init",
                    "--quiet",
                    "--bare",
                    str(mirror),
                ]),
            )
            common = tm.ok(
                u.Cli.capture(
                    [
                        c.Infra.GIT,
                        "rev-parse",
                        "--path-format=absolute",
                        "--git-common-dir",
                    ],
                    cwd=origin,
                ),
            ).strip()
            tm.ok(
                u.Cli.atomic_write_text_file(
                    mirror / "objects" / "info" / "alternates",
                    f"{Path(common) / 'objects'}\n",
                ),
            )
            tm.ok(
                u.Cli.run_checked(
                    [c.Infra.GIT, "update-ref", f"refs/heads/{rev}", sha],
                    cwd=mirror,
                ),
            )
            mirrored.append(f"{url}@{rev}#{sha}")
        return tuple(mirrored)

    @staticmethod
    def hermetic_git_environment(mirrors: Path) -> t.StrMapping:
        """Route every mirrored host to its mirror and refuse any other transport.

        Git may speak only the ``file`` protocol, uv makes no network request
        and skips its GitHub API shortcut, so a fixture that still reaches a
        remote fails instead of passing on a live network.

        Returns:
            The resulting ``t.StrMapping``.

        """
        count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
        hosts = sorted(path.name for path in mirrors.iterdir() if path.is_dir())
        environment = {
            "GIT_CONFIG_COUNT": str(count + len(hosts)),
            "GIT_ALLOW_PROTOCOL": "file",
            "UV_OFFLINE": "1",
            "UV_NO_GITHUB_FAST_PATH": "1",
        }
        for index, host in enumerate(hosts, start=count):
            environment[f"GIT_CONFIG_KEY_{index}"] = (
                f"url.{(mirrors / host).as_uri()}/.insteadOf"
            )
            environment[f"GIT_CONFIG_VALUE_{index}"] = f"https://{host}/"
        return environment
