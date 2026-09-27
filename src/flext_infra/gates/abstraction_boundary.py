"""Abstraction-boundary quality gate (AGENTS.md §2.7).

Single SSOT replacing the two standalone scripts ``audit_banned_cli_libs.py``
and ``audit_flext_cli_concrete_imports.py``. All detection data (banned libs,
regex catalog, exemptions) lives in ``c.Infra.BOUNDARY_*`` (CONSTANTS-FIRST);
this class is the thin, data-driven scanner. For every project except
``flext-cli``/``flext-core`` it flags CLI-domain lib imports (``click`` exempt
in Singer-SDK boundary files), ``subprocess``, ``tomllib``/``tomlkit`` outside
``flext-infra``, direct ``json.``/``yaml.``/``csv.`` use, top-level ``u.Cli.print(``/
``sys.exit(``, and concrete ``FlextCli<X>`` imports outside src extension files.
"""

from __future__ import annotations

import ast
import time
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m, u

from .base_gate import FlextInfraGate

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import t


class FlextInfraAbstractionBoundaryGate(FlextInfraGate):
    """Block CLI-domain library leakage and concrete FlextCli imports in consumers."""

    gate_id: ClassVar[str] = "boundary"
    gate_name: ClassVar[str] = "Abstraction Boundary"
    can_fix: ClassVar[bool] = False

    @override
    def check(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> m.Infra.GateExecution:
        """Scan one project's Python sources for abstraction-boundary breaches."""
        started = time.monotonic()
        if project_dir.name in c.Infra.BOUNDARY_SKIP_PROJECTS:
            # A declared boundary owner is exempt by design: an intentional
            # skip passes, never a non-acceptance for missing targets.
            return self._neutral_skip_result(
                project_dir,
                started,
                message=f"{self.gate_id}: {project_dir.name} is a declared boundary owner",
            )
        files_result = u.Infra.iter_python_files(
            m.Infra.SourceScanRequest(project_roots=(project_dir,))
        )
        if files_result.failure:
            issue = m.Infra.Issue(
                file=project_dir.name,
                line=1,
                column=1,
                code=self.gate_id,
                message=files_result.error or "abstraction-boundary scan failed",
            )
            return self._build_check_gate_execution(
                project_dir,
                passed=False,
                issues=[issue],
                raw_output=issue.formatted,
                started=started,
            )
        issues = [
            issue
            for file_path in files_result.value
            for issue in self._scan_file(file_path, project_dir.name)
        ]
        return self._detected_gate_execution(
            project_dir, ctx, issues=issues, started=started
        )

    def _scan_file(self, path: Path, project: str) -> t.SequenceOf[m.Infra.Issue]:
        """Return boundary violations for a single file via the c.Infra catalog."""
        read = u.Cli.files_read_text(path)
        if read.failure:
            return [self._issue(path, read.error or "unreadable source file")]
        text = read.value
        posix = str(path).replace("\\", "/")
        if any(frag in posix for frag in c.Infra.BOUNDARY_SELF_FILES):
            return []
        if any(frag in posix for frag in c.Infra.BOUNDARY_SKIP_PATH_FRAGMENTS):
            return []
        issues: t.MutableSequenceOf[m.Infra.Issue] = []
        click_ok = any(frag in posix for frag in c.Infra.BOUNDARY_CLICK_FILES)
        for lib, regex, replacement in c.Infra.BOUNDARY_BANNED_RULES:
            if lib == "click" and click_ok:
                continue
            if regex.search(text):
                issues.append(self._issue(path, f"imports `{lib}` — use {replacement}"))
        for regex, message in c.Infra.BOUNDARY_SIMPLE_RULES:
            if regex.search(text):
                issues.append(self._issue(path, message))
        if (
            c.Infra.BOUNDARY_TOML_RE.search(text)
            and project not in c.Infra.BOUNDARY_TOML_ALLOWED
        ):
            issues.append(
                self._issue(path, "imports tomllib/tomlkit — use u.Cli.toml_read_json")
            )
        issues.extend(self._ast_boundary_issues(path, text, posix))
        return issues

    def _ast_boundary_issues(
        self, path: Path, text: str, posix: str
    ) -> t.SequenceOf[m.Infra.Issue]:
        """Flag live json/yaml/csv calls and concrete FlextCli imports via AST."""
        tree = ast.parse(text, filename=str(path))
        issues: t.MutableSequenceOf[m.Infra.Issue] = []
        attr_seen: set[str] = set()
        for statement in ast.walk(tree):
            if (
                isinstance(statement, ast.Call)
                and isinstance(statement.func, ast.Name)
                and statement.func.id == "print"
            ):
                issues.append(self._issue(path, "uses print() — use cli.print"))
            if isinstance(statement, ast.Attribute) and isinstance(
                statement.value, ast.Name
            ):
                owner = statement.value.id
                for module_name, attrs, message in c.Infra.BOUNDARY_ATTR_RULES:
                    if owner != module_name or statement.attr not in attrs:
                        continue
                    if message in attr_seen:
                        continue
                    attr_seen.add(message)
                    issues.append(self._issue(path, message))
            if "/src/" in posix and path.name in c.Infra.BOUNDARY_EXTENSION_FILES:
                continue
            if not (
                isinstance(statement, ast.ImportFrom)
                and statement.module == "flext_cli"
            ):
                continue
            for imported in statement.names:
                name = imported.name
                if c.Infra.BOUNDARY_FLEXT_CLI_CONCRETE_RE.fullmatch(name) is None:
                    continue
                issues.append(
                    self._issue(
                        path, f"imports concrete `{name}` (use cli/c/m/p/t/u/s)"
                    )
                )
        return issues

    def _issue(self, path: Path, message: str) -> m.Infra.Issue:
        """Build a boundary Issue anchored at the file head."""
        return m.Infra.Issue(
            file=str(path),
            line=1,
            column=1,
            code=self.gate_id,
            message=message,
            severity="ERROR",
        )


__all__: list[str] = ["FlextInfraAbstractionBoundaryGate"]
