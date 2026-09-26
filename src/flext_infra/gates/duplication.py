"""Fail-closed jscpd duplicate-code detector (R2 consumer+family scope)."""

from __future__ import annotations

import ast
import shutil
import time
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_core import r
from flext_infra import c, m, t, u

from .base_gate import FlextInfraGate

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraDuplicationGate(FlextInfraGate):
    """Report every clone owned by one project from a fresh workspace scan.

    R2 extension: consumer+family scope via [tool.flext.project] config keys;
    thresholds in config SSOT. Structural ban forms only for mechanisms with
    a published canonical owner (derived from primitives set) — never per-site lists.
    """

    gate_id: ClassVar[str] = "duplication"
    gate_name: ClassVar[str] = "Code Duplication"
    can_fix: ClassVar[bool] = False
    scanner_binary: ClassVar[str] = c.Infra.JSCPD_BINARY

    # flext-pulj: process results stay structural outside the Pydantic boundary.
    _scan_cache: ClassVar[MutableMapping[str, p.Cli.CommandOutput]] = {}
    _python_behavior_cache: ClassVar[
        MutableMapping[t.Triple[str, int, int], t.VariadicTuple[t.Pair[int, int]]]
    ] = {}

    @override
    def check(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> m.Infra.GateExecution:
        """Run and validate jscpd, then expose every owned clone as an error."""
        _ = ctx
        started = time.monotonic()
        scan = self._scan_workspace(project_dir)
        parsed = self._issues_from_report(scan, project_dir)
        issues = (
            parsed.value if parsed.success else (self._failure_issue(parsed.error),)
        )
        if not issues and scan.outcome.raw_return_code not in {0, 1}:
            issues = (self._tool_failure_issue(scan),)
        return self._build_check_gate_execution(
            project_dir,
            passed=not issues,
            issues=issues,
            raw_output="\n".join(part for part in (scan.stdout, scan.stderr) if part),
            started=started,
        )

    def _scan_workspace(self, project_dir: Path) -> p.Cli.CommandOutput:
        """Create one fresh report; tool, scope, and report failures escape."""
        binary = shutil.which(c.Infra.JSCPD_BINARY)
        if binary is None:
            return m.Cli.CommandOutput(
                stdout="",
                stderr=(
                    f"{c.Infra.JSCPD_BINARY} not found on PATH; `make setup` "
                    "provisions it from codegen.toolchain.jscpd_version"
                ),
                # jscpd itself exits 1 when it finds clones, so an absent binary
                # must not borrow that code or the gate would read it as a scan.
                outcome=m.Cli.ProcessOutcome(
                    raw_return_code=c.Infra.PROCESS_COMMAND_NOT_FOUND_EXIT_CODE,
                    timed_out=False,
                    forwarded_signal=None,
                ),
            )
        scope = self._render_scope_dirs(project_dir)
        if scope.failure:
            return m.Cli.CommandOutput(
                stdout="",
                stderr=scope.error or "workspace scope resolution failed",
                outcome=m.Cli.ProcessOutcome(
                    raw_return_code=1, timed_out=False, forwarded_signal=None
                ),
            )
        if not scope.value:
            return m.Cli.CommandOutput(
                stdout="",
                stderr="jscpd scope resolved no source or test directories",
                outcome=m.Cli.ProcessOutcome(
                    raw_return_code=1, timed_out=False, forwarded_signal=None
                ),
            )
        rendered_config = self._render_config(project_dir)
        if rendered_config.failure:
            return m.Cli.CommandOutput(
                stdout="",
                stderr=rendered_config.error or "project duplication config invalid",
                outcome=m.Cli.ProcessOutcome(
                    raw_return_code=1, timed_out=False, forwarded_signal=None
                ),
            )
        config_path = rendered_config.value
        report_dir = self._repository_root / c.Infra.JSCPD_REPORT_DIRNAME
        report_path = report_dir / c.Infra.JSCPD_REPORT_FILENAME
        if report_path.is_symlink() or (
            report_path.exists() and not report_path.is_file()
        ):
            msg = f"jscpd report target is not a physical file: {report_path}"
            raise ValueError(msg)
        if report_path.is_file():
            report_path.unlink()
        cmd = (
            binary,
            "--config",
            str(config_path),
            "--reporters",
            "json",
            "--output",
            str(report_dir),
            *scope.value,
        )
        result = self._run(cmd, self._repository_root, timeout=c.Infra.TIMEOUT_LONG)
        return self._load_report(report_dir, result)

    def _render_scope_dirs(self, project_dir: Path) -> p.Result[t.StrSequence]:
        """Every discovered project's canonical scope plus declared extra trees.

        R2: Extended to consumer+family scope via [tool.flext.project] config keys.
        Reuses the same workspace-topology discovery every other check-scoping
        path uses (``u.Infra.resolve_projects``) — never a second hardcoded
        project list. A project's manifest may declare additional
        ``repository.duplication_trees`` (e.g. Helm charts); those declared
        trees join the scan when they exist on disk.
        """
        # Read project-specific config from [tool.flext.project]
        project_config = self._read_project_config(project_dir)
        if project_config.failure:
            return r[t.StrSequence].from_failure(project_config)
        scope_dirnames = project_config.value.scope

        discovered = u.Infra.resolve_projects(self._repository_root, ())
        if discovered.failure:
            return r[t.StrSequence].from_failure(discovered)
        declared_trees = self._declared_duplication_trees()
        if declared_trees.failure:
            return r[t.StrSequence].from_failure(declared_trees)
        return r[t.StrSequence].ok(
            tuple(
                str(project.path / candidate)
                for project in discovered.value
                for candidate in (
                    *self._existing_check_dirs(project.path),
                    *(
                        tree
                        for tree in declared_trees.value
                        if (project.path / tree).is_dir()
                    ),
                    *(
                        dirname
                        for dirname in scope_dirnames
                        if (project.path / dirname).is_dir()
                    ),
                )
            )
        )

    def _read_project_config(
        self, project_dir: Path
    ) -> p.Result[m.Infra.ProjectDuplicationOverrides]:
        """Read ``[tool.flext.project.duplication]`` from pyproject.toml.

        Why: a malformed manifest is a declared error, never an empty config —
        silently returning the default model for a broken manifest would
        disable the operator's overrides without a trace (silent-failure law).
        An absent manifest or absent ``duplication`` table is not malformed;
        it legitimately yields the default overrides.
        """
        pyproject_path = project_dir / "pyproject.toml"
        if not pyproject_path.is_file():
            return r[m.Infra.ProjectDuplicationOverrides].ok(
                m.Infra.ProjectDuplicationOverrides()
            )
        loaded = u.Cli.config_load(pyproject_path, expand_env=False)
        if loaded.failure:
            return r[m.Infra.ProjectDuplicationOverrides].fail(
                f"invalid project manifest ({pyproject_path}): {loaded.error}"
            )
        tool = u.Cli.json_as_mapping(loaded.value.data).get("tool", {})
        flext = u.Cli.json_as_mapping(tool).get("flext", {})
        project = u.Cli.json_as_mapping(flext).get("project", {})
        duplication = u.Cli.json_as_mapping(project).get("duplication", {})
        validated: p.Result[m.Infra.ProjectDuplicationOverrides] = u.validate_value(
            m.Infra.ProjectDuplicationOverrides, u.Cli.json_as_mapping(duplication)
        )
        if validated.failure:
            return r[m.Infra.ProjectDuplicationOverrides].fail_op(
                f"[tool.flext.project.duplication] validation ({pyproject_path})",
                validated.error,
            )
        return r[m.Infra.ProjectDuplicationOverrides].ok(validated.value)

    def _declared_duplication_trees(self) -> p.Result[t.StrSequence]:
        """Read ``repository.duplication_trees`` from the governed manifest."""
        manifest_path = u.Infra.workspace_manifest_path(self._repository_root)
        if not manifest_path.is_file():
            return r[t.StrSequence].ok(())
        loaded = u.Cli.config_load(manifest_path, expand_env=False)
        if loaded.failure:
            return r[t.StrSequence].fail(
                f"invalid workspace manifest ({manifest_path}): {loaded.error}"
            )
        validated: p.Result[m.Infra.WorkspaceManifestSpec] = u.validate_value(
            m.Infra.WorkspaceManifestSpec, loaded.value.data
        )
        if validated.failure:
            return r[t.StrSequence].fail_op(
                f"workspace manifest model validation ({manifest_path})",
                validated.error,
            )
        return r[t.StrSequence].ok(tuple(validated.value.repository.duplication_trees))

    def _scope_paths(self) -> t.StrSequence:
        """Resolve canonical source, test, config, and template roots once."""
        projects = u.Infra.resolve_projects(self._repository_root, ()).unwrap()
        scope = tuple(
            str(path)
            for project in projects
            for dirname in c.Infra.JSCPD_SCOPE_DIRNAMES
            if (path := project.path / dirname).is_dir()
        )
        if not scope:
            msg = f"jscpd found no canonical scope under {self._repository_root}"
            raise ValueError(msg)
        return scope

    def _render_config(self, project_dir: Path) -> p.Result[Path]:
        """Materialize the jscpd config from this gate's typed SSOT.

        R2: Reads thresholds from [tool.flext.project] config SSOT.
        A generated-at-scan-time projection, never a second hand-edited
        source; regenerating with unchanged constants produces byte-identical
        content (idempotent).
        """
        project_config = self._read_project_config(project_dir)
        if project_config.failure:
            return r[Path].from_failure(project_config)
        overrides = project_config.value

        config = m.Infra.JscpdConfig(
            absolute=True,
            formatsExts={
                name: tuple(extensions)
                for name, extensions in c.Infra.JSCPD_FORMAT_EXTENSIONS.items()
            },
            ignore=tuple(c.Infra.JSCPD_IGNORE_PATTERNS),
            minLines=overrides.min_lines,
            minTokens=overrides.min_tokens,
            mode=overrides.mode,
            noColors=True,
            noTips=True,
            reporters=(c.Infra.OUTPUT_JSON,),
            threshold=overrides.threshold_percent,
        )
        config_path = (
            self._repository_root
            / c.Infra.JSCPD_REPORT_DIRNAME
            / c.Infra.JSCPD_CONFIG_FILENAME
        )
        u.Cli.ensure_dir(config_path.parent).unwrap()
        rendered = config.model_dump_json(by_alias=True)
        u.Cli.atomic_write_text_file(config_path, rendered).unwrap()
        return r[Path].ok(config_path)

    @staticmethod
    def _load_report(
        report_dir: Path, result: p.Cli.CommandOutput
    ) -> p.Cli.CommandOutput:
        """Load the JSON report jscpd writes to disk; stdout carries console noise only."""
        report_path = report_dir / c.Infra.JSCPD_REPORT_FILENAME
        if not report_path.is_file():
            return result
        return m.Cli.CommandOutput(
            stdout=report_path.read_text(encoding="utf-8"),
            stderr=result.stderr,
            outcome=m.Cli.ProcessOutcome(
                raw_return_code=result.outcome.raw_return_code,
                timed_out=result.outcome.timed_out,
                forwarded_signal=result.outcome.forwarded_signal,
            ),
        )

    @staticmethod
    def _failure_issue(message: str | None) -> m.Infra.Issue:
        """Represent malformed or absent jscpd output as a blocking issue."""
        return m.Infra.Issue(
            file=c.PYPROJECT_FILENAME,
            line=1,
            column=0,
            code=FlextInfraDuplicationGate.gate_id,
            message=message or "jscpd returned no parseable report",
            severity=str(c.Infra.GateSeverity.ERROR.value),
        )

    @classmethod
    def _issues_from_report(
        cls, scan: p.Cli.CommandOutput, project_dir: Path
    ) -> p.Result[t.VariadicTuple[m.Infra.Issue]]:
        """Extract one Issue per clone side that falls inside ``project_dir``."""
        if not scan.stdout.strip():
            # jscpd succeeded and reported nothing, which means it was handed a
            # scope with no comparable source. Naming the tool hid the project
            # whose scope is empty, which is the fact the operator needs.
            return r[tuple[m.Infra.Issue, ...]].fail(
                f"duplication scan produced no report for project "
                f"{project_dir.name}: the scanned scope is empty"
            )
        parsed = u.Cli.json_parse(scan.stdout)
        if parsed.failure:
            return r[tuple[m.Infra.Issue, ...]].from_failure(parsed)
        data = u.Cli.json_as_mapping(parsed.value)
        issues: list[m.Infra.Issue] = []
        for duplicate in u.Cli.json_deep_mapping_list(data, "duplicates"):
            first = u.Cli.json_deep_mapping(duplicate, "firstFile")
            second = u.Cli.json_deep_mapping(duplicate, "secondFile")
            first_name = u.Cli.json_pick_str(first, "name")
            second_name = u.Cli.json_pick_str(second, "name")
            if not cls._is_semantic_clone(duplicate, first, second):
                continue
            # Ownership is path containment, never a string prefix: a sibling
            # project whose directory name extends this one (``flext-x`` vs
            # ``flext-x-extra``) shares the prefix but owns its own clones.
            # ``startswith`` claimed those siblings and then raised ValueError
            # from ``relative_to``, turning a real cross-project clone into a
            # crashed gate.
            if (
                Path(first_name).is_relative_to(project_dir)
                and first_name != second_name
            ):
                issues.append(
                    cls._issue_from_duplicate(
                        duplicate, first, first_name, second_name, project_dir
                    )
                )
            elif (
                Path(second_name).is_relative_to(project_dir)
                and second_name != first_name
            ):
                issues.append(
                    cls._issue_from_duplicate(
                        duplicate, second, second_name, first_name, project_dir
                    )
                )
        return r[tuple[m.Infra.Issue, ...]].ok(tuple(issues))

    @classmethod
    def _issue_from_duplicate(
        cls,
        duplicate: t.JsonMapping,
        own_side: t.JsonMapping,
        own_name: str,
        other_name: str,
        root: Path,
    ) -> m.Infra.Issue:
        """Map one clone side inside ``root`` to a strict error."""
        return m.Infra.Issue(
            file=str(Path(own_name).relative_to(root)),
            line=u.Cli.json_nested_int(own_side, "startLoc", "line", default=1),
            column=u.Cli.json_nested_int(own_side, "startLoc", "column", default=0),
            code=cls.gate_id,
            message=(
                f"{u.Cli.json_pick_int(duplicate, 'lines', default=0)}-line "
                f"({u.Cli.json_pick_int(duplicate, 'tokens', default=0)}-token) "
                f"clone of {other_name} "
                f"— extend one owner, rewire consumers, delete the duplicate"
            ),
            severity=str(c.Infra.GateSeverity.ERROR.value),
        )

    @classmethod
    def _is_semantic_clone(
        cls, duplicate: t.JsonMapping, first: t.JsonMapping, second: t.JsonMapping
    ) -> bool:
        """Require executable Python behavior on both sides of a clone.

        jscpd is the candidate detector, not the semantic authority. Python
        module licenses, docstrings, imports, ``TYPE_CHECKING`` blocks, class
        shells, function signatures, and declaration-only assignments are
        intentionally repeated language structure rather than competing
        implementations. A candidate remains blocking when both source ranges
        contain an executable statement. Unreadable or unparsable input stays
        blocking because absence of semantic proof can never produce green.
        Non-Python formats likewise remain blocking until their own semantic
        classifier exists.
        """
        if u.Cli.json_pick_str(duplicate, "format") != "python":
            return True
        return cls._range_has_python_behavior(first) and cls._range_has_python_behavior(
            second
        )

    @classmethod
    def _range_has_python_behavior(cls, side: t.JsonMapping) -> bool:
        """Return whether one jscpd source range encloses executable behavior."""
        file_name = u.Cli.json_pick_str(side, "name")
        path = Path(file_name)
        try:
            identity = path.stat()
        except OSError:
            return True
        key = (file_name, identity.st_mtime_ns, identity.st_size)
        ranges = cls._python_behavior_cache.get(key)
        if ranges is None:
            ranges = cls._python_behavior_ranges(path)
            cls._python_behavior_cache[key] = ranges
        start = u.Cli.json_nested_int(side, "startLoc", "line", default=1)
        end = u.Cli.json_nested_int(side, "endLoc", "line", default=start)
        return any(
            start <= node_start and node_end <= end for node_start, node_end in ranges
        )

    @staticmethod
    def _python_behavior_ranges(path: Path) -> t.VariadicTuple[t.Pair[int, int]]:
        """Parse one module into ranges for statements with runtime behavior."""
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }

        def inside_function(node: ast.AST) -> bool:
            parent = parents.get(node)
            while parent is not None:
                if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    return True
                parent = parents.get(parent)
            return False

        def is_declaration(node: ast.stmt) -> bool:
            if isinstance(
                node,
                (
                    ast.ClassDef,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.Import,
                    ast.ImportFrom,
                    ast.Pass,
                    ast.Global,
                    ast.Nonlocal,
                ),
            ):
                return True
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                return True
            if (
                isinstance(node, ast.If)
                and isinstance(node.test, ast.Name)
                and node.test.id == "TYPE_CHECKING"
            ):
                return True
            return isinstance(
                node, (ast.Assign, ast.AnnAssign)
            ) and not inside_function(node)

        return tuple(
            (node.lineno, node.end_lineno)
            for node in ast.walk(tree)
            if isinstance(node, ast.stmt)
            and node.end_lineno is not None
            and not is_declaration(node)
        )


__all__: list[str] = ["FlextInfraDuplicationGate"]
