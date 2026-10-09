"""Gate measurement and ast-grep batch execution for the mod safety circuit.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import shutil
import stat
import sys
import tempfile
from collections.abc import Mapping, MutableMapping
from pathlib import Path

from flext_infra import c, m, p, r, settings, t, u
from flext_infra.codemod import FlextInfraCodemodSnapshotReconciler


class FlextInfraModGateEngine:
    """Execute ast-grep rewrites and measure the catalog findings they leave."""

    @classmethod
    def validate_rule_fixtures(
        cls,
        root: Path,
        rules: t.SequenceOf[Path],
    ) -> p.Result[bool]:
        """Verify every fixture against its committed snapshots; never rewrite them.

        A drifted or missing snapshot fails ``ast-grep test``; a snapshot of a
        removed rule or deleted test case fails the owned-inventory check. The
        change they record is made explicit by ``make mod-snapshots`` and lands
        as a reviewed commit, so ``make mod`` cannot accept rewritten output.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for config_root, owner_rules, owner_is_governed in cls._fixture_owners(
            root,
            rules,
        ):
            if owner_is_governed:
                active_rule_ids: set[str] = set()
                for rule in owner_rules:
                    rule_ids, _fixable_ids = u.Infra.ast_grep_rule_contract(rule)
                    active_rule_ids.update(rule_ids)
                stale = FlextInfraCodemodSnapshotReconciler.stale_snapshots(
                    config_root,
                    frozenset(active_rule_ids),
                )
                if stale:
                    return r[bool].fail(
                        "ast-grep snapshots record no current rule test:\n"
                        + "\n".join(stale)
                        + f"\n{c.Infra.CODEMOD_SNAPSHOT_REFRESH_HINT}",
                    )
            with tempfile.TemporaryDirectory(
                prefix="mod-rule-fixtures-",
                dir=settings.work_dir,
            ) as temp_dir:
                temp_root = Path(temp_dir) / config_root.name
                cls.stage_rule_fixture_root(
                    config_root=config_root,
                    temp_root=temp_root,
                )
                cls._materialize_split_rule_files(
                    config_root=config_root,
                    temp_root=temp_root,
                    owner_rules=owner_rules,
                )
                tested = cls._run_tool(temp_root, (c.Infra.SG, c.Infra.TEST))
                if tested.failure:
                    remedy = (
                        c.Infra.CODEMOD_SNAPSHOT_REFRESH_HINT
                        if owner_is_governed
                        else (
                            f"inherited rule provider {config_root} ships these "
                            "fixtures; repair them in its owner repository"
                        )
                    )
                    return r[bool].fail(f"{tested.error}\n{remedy}")
        return r.ok(value=True)

    @classmethod
    def refresh_rule_snapshots(
        cls,
        root: Path,
        rules: t.SequenceOf[Path],
        *,
        apply: bool,
    ) -> p.Result[t.StrSequence]:
        """Regenerate every governed owner's snapshots from its rule tests.

        The explicit counterpart of the verifying ``validate_rule_fixtures``:
        snapshots are projections of the declared test cases, rebuilt from
        scratch so removed rules and deleted cases leave no residue. The
        returned changes are the reviewed diff; inherited providers keep the
        snapshots their owner ships.

        Returns:
            The resulting ``p.Result[t.StrSequence]``.

        """
        changes: list[str] = []
        for config_root, owner_rules, owner_is_governed in cls._fixture_owners(
            root,
            rules,
        ):
            if not owner_is_governed:
                continue
            with tempfile.TemporaryDirectory(
                prefix="mod-rule-snapshots-",
                dir=settings.work_dir,
            ) as temp_dir:
                temp_root = Path(temp_dir) / config_root.name
                cls.stage_rule_fixture_root(
                    config_root=config_root,
                    temp_root=temp_root,
                    regenerate_snapshots=True,
                )
                cls._materialize_split_rule_files(
                    config_root=config_root,
                    temp_root=temp_root,
                    owner_rules=owner_rules,
                )
                cls._run_tool(
                    temp_root,
                    (c.Infra.SG, c.Infra.TEST, c.Infra.SG_UPDATE_ALL),
                ).unwrap()
                cls._run_tool(temp_root, (c.Infra.SG, c.Infra.TEST)).unwrap()
                changes.extend(
                    cls._publish_regenerated_snapshots(
                        config_root=config_root,
                        temp_root=temp_root,
                        apply=apply,
                    ),
                )
        return r[t.StrSequence].ok(tuple(changes))

    @staticmethod
    def _governs(governed_root: Path, config_root: Path) -> bool:
        """Whether the governed repository itself tracks this rule provider.

        Git owns the answer: an installed provider (``site-packages``) or a
        member checkout lies outside, or untracked by, the governed repository,
        while the repository's own catalog is tracked wherever it lives.

        Returns:
            The resulting ``bool``.

        """
        provider = (config_root / c.Infra.CODEMOD_CONFIG_FILENAME).resolve()
        if not provider.is_relative_to(governed_root):
            return False
        return (
            u.Infra
            .git_is_tracked(
                m.Infra.GitRelativePathRequest(
                    repo_root=governed_root,
                    relative_path=provider.relative_to(governed_root).as_posix(),
                ),
            )
            .unwrap()
            .value
        )

    @classmethod
    def _fixture_owners(
        cls,
        root: Path,
        rules: t.SequenceOf[Path],
    ) -> t.SequenceOf[t.Triple[Path, t.SequenceOf[Path], bool]]:
        """Group rules by fixture owner and mark the owners this root governs.

        Returns:
            The resulting ``t.SequenceOf[t.Triple[Path, t.SequenceOf[Path], bool]]``.

        Raises:
            ValueError: If discovered ast-grep rules have no fixture owner; or if rule
                fixture scratch must be outside its source root.

        """
        governed_roots = tuple(
            project.resolve() for project in u.Infra.governed_project_roots(root)
        )
        rules_by_owner: MutableMapping[Path, list[Path]] = {}
        for rule in rules:
            owner = FlextInfraCodemodSnapshotReconciler.config_root(rule)
            rules_by_owner.setdefault(owner, []).append(rule)
        if not rules_by_owner:
            msg = "discovered ast-grep rules have no fixture owner"
            raise ValueError(msg)
        scratch = settings.work_dir
        owners: list[t.Triple[Path, t.SequenceOf[Path], bool]] = []
        for config_root, owner_rules in sorted(rules_by_owner.items()):
            if scratch.resolve().is_relative_to(config_root.resolve()):
                msg = "rule fixture scratch must be outside its source root"
                raise ValueError(msg)
            owners.append((
                config_root,
                tuple(owner_rules),
                any(
                    cls._governs(governed_root, config_root)
                    for governed_root in governed_roots
                ),
            ))
        scratch.mkdir(parents=True, exist_ok=True)
        return tuple(owners)

    @staticmethod
    def stage_rule_fixture_root(
        *,
        config_root: Path,
        temp_root: Path,
        regenerate_snapshots: bool = False,
    ) -> None:
        """Copy declared ast-grep inputs only, rejecting links and special files.

        Raises:
            ValueError: If ast-grep fixture must be a regular file or directory.

        """
        directories = FlextInfraCodemodSnapshotReconciler.fixture_directories(
            config_root,
        )
        snapshot_roots = {
            directory / c.Infra.CODEMOD_SNAPSHOT_DIRNAME
            for directory in directories.test_dirs
        }
        pending = [config_root / c.Infra.CODEMOD_CONFIG_FILENAME]
        pending.extend((
            *directories.rule_dirs,
            *directories.util_dirs,
            *directories.test_dirs,
        ))
        files: set[Path] = set()
        folders: set[Path] = set()
        while pending:
            path = pending.pop()
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode):
                if path in folders:
                    continue
                folders.add(path)
                pending.extend(path.iterdir())
            elif stat.S_ISREG(mode):
                files.add(path)
            else:
                msg = f"ast-grep fixture must be a regular file or directory: {path}"
                raise ValueError(msg)
        temp_root.mkdir()
        for directory in sorted(folders):
            (temp_root / directory.relative_to(config_root)).mkdir(
                parents=True,
                exist_ok=True,
            )
        for source in sorted(files):
            if (
                regenerate_snapshots
                and source.parent in snapshot_roots
                and source.name.endswith(c.Infra.CODEMOD_SNAPSHOT_SUFFIX)
            ):
                # Owned projections are regenerated from all declared test cases.
                # Foreign providers retain their snapshots for verification.
                continue
            shutil.copy2(
                source,
                temp_root / source.relative_to(config_root),
                follow_symlinks=False,
            )

    @staticmethod
    def _rule_documents(rule: Path) -> t.VariadicTuple[str]:
        """Return every non-empty YAML document in one rule file.

        Returns:
            Every non-empty YAML document in one rule file.

        """
        documents = tuple(rule.read_text(encoding="utf-8").split("\n---"))
        return tuple(
            document.strip("\n")
            for document in documents
            if any(
                line.strip() and not line.lstrip().startswith("#")
                for line in document.splitlines()
            )
        )

    @classmethod
    def _materialize_split_rule_files(
        cls,
        *,
        config_root: Path,
        temp_root: Path,
        owner_rules: t.SequenceOf[Path],
    ) -> None:
        """Replace multi-document rule files with single-document temp copies.

        Raises:
            RuntimeError: If ``parsed.failure``; or if ast-grep rule document missing
                required id.

        """
        source_rules = set(owner_rules)
        directories = FlextInfraCodemodSnapshotReconciler.fixture_directories(
            config_root,
        )
        for directory in (*directories.rule_dirs, *directories.util_dirs):
            source_rules.update(directory.rglob(f"*{c.Infra.CODEMOD_RULE_SUFFIX}"))
        for rule in sorted(source_rules):
            documents = cls._rule_documents(rule)
            if len(documents) <= 1:
                continue
            temp_rule = temp_root / rule.relative_to(config_root)
            temp_rule.unlink()
            for document in documents:
                parsed = u.Cli.yaml_parse(document)
                if parsed.failure:
                    raise RuntimeError(parsed.error or str(rule))
                rule_id = parsed.value.get("id")
                if not isinstance(rule_id, str) or not rule_id:
                    msg = f"ast-grep rule document missing required id: {rule}"
                    raise RuntimeError(msg)
                temp_rule.with_name(f"{rule_id}.yml").write_text(
                    document,
                    encoding="utf-8",
                )

    @staticmethod
    def _publish_regenerated_snapshots(
        *,
        config_root: Path,
        temp_root: Path,
        apply: bool,
    ) -> t.StrSequence:
        """Mirror only regenerated snapshot files back to source; report each change.

        Rules, utilities and tests are inputs of the regeneration and are never
        written back. A committed snapshot the regeneration did not produce
        belongs to a removed rule or test and is removed with the rest.

        Returns:
            The resulting ``t.StrSequence``.

        """
        pattern = f"*{c.Infra.CODEMOD_SNAPSHOT_SUFFIX}"
        changes: list[str] = []
        for test_dir in FlextInfraCodemodSnapshotReconciler.fixture_directories(
            config_root,
        ).test_dirs:
            source_dir = test_dir / c.Infra.CODEMOD_SNAPSHOT_DIRNAME
            regenerated_dir = temp_root / source_dir.relative_to(config_root)
            regenerated = {path.name: path for path in regenerated_dir.glob(pattern)}
            committed = {path.name: path for path in source_dir.glob(pattern)}
            for name in sorted(regenerated.keys() | committed.keys()):
                target = source_dir / name
                produced = regenerated.get(name)
                if produced is None:
                    changes.append(f"removed {target}")
                    if apply:
                        target.unlink()
                    continue
                content = produced.read_text(encoding=c.Cli.ENCODING_DEFAULT)
                current = committed.get(name)
                if current is not None and (
                    current.read_text(encoding=c.Cli.ENCODING_DEFAULT) == content
                ):
                    continue
                changes.append(
                    f"{'created' if current is None else 'updated'} {target}",
                )
                if apply:
                    u.Cli.atomic_write_text_file(target, content).unwrap()
        return tuple(changes)

    @staticmethod
    def _run_tool(
        root: Path,
        command: t.StrSequence,
        *,
        finding_exit_code: int | None = None,
    ) -> p.Result[p.Cli.CommandOutput]:
        """Run one AST tool and preserve its documented finding status.

        Returns:
            The resulting ``p.Result[p.Cli.CommandOutput]``.

        """
        sys.stderr.write(
            f"mod: start {' '.join(command[:2])} args={max(0, len(command) - 2)}\n",
        )
        sys.stderr.flush()
        run = u.Cli.run_raw(command, cwd=root, timeout=c.Infra.TIMEOUT_SHORT)
        if run.failure:
            return r[p.Cli.CommandOutput].from_failure(run)
        output = run.value
        sys.stderr.write(
            f"mod: finish {command[0]} exit={output.outcome.raw_return_code} "
            f"duration={output.duration:.2f}s\n",
        )
        sys.stderr.flush()
        if output.outcome.raw_return_code != 0:
            if (
                output.outcome.raw_return_code == finding_exit_code
                and output.stdout.strip()
            ):
                return r[p.Cli.CommandOutput].ok(output)
            detail = "\n".join(
                stream.strip()
                for stream in (output.stdout, output.stderr)
                if stream.strip()
            )
            return r[p.Cli.CommandOutput].fail(
                f"{command[0]} exited with code "
                f"{output.outcome.raw_return_code}: {detail}",
            )
        stderr = output.stderr.strip()
        if stderr:
            return r[p.Cli.CommandOutput].fail(stderr)
        return r[p.Cli.CommandOutput].ok(output)

    @staticmethod
    def _path_depth(path: Path) -> int:
        """Return path depth for deterministic deepest-owner selection.

        Returns:
            Path depth for deterministic deepest-owner selection.

        """
        return len(path.parts)

    @staticmethod
    def _validate_finding_receipt(stderr: str, errors: int) -> p.Result[bool]:
        """Authenticate ast-grep's exact error-finding stderr receipt.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        expected = "\n".join((
            c.Infra.AST_GREP_ERROR_FINDING_RECEIPT.format(count=errors),
            c.Infra.AST_GREP_ERROR_FINDING_HELP,
        ))
        if stderr.strip() != expected:
            return r[bool].fail(
                f"ast-grep finding receipt mismatch: parsed_errors={errors} "
                f"expected={expected!r} actual={stderr.strip()!r}",
            )
        return r[bool].ok(value=True)

    @staticmethod
    def _admitted(
        root: Path,
        report: m.Infra.ModScanReport,
        rules_by_id: t.MappingKV[str, m.Infra.CodemodRule],
    ) -> m.Infra.ModScanReport:
        """Keep the findings whose rule's project context holds, recounted.

        A rule's ``metadata.context`` binds captured metavariables to project
        predicates ast-grep cannot see (standard library, own package, runtime
        closure, the file's declared facade family); the syntactic match is a
        finding only when every condition holds.

        Returns:
            The resulting ``m.Infra.ModScanReport``.

        """
        facts = u.Infra.codemod_project_facts(
            root,
            tuple(rules_by_id[entry.rule_id] for entry in report.entries),
        )
        entries = tuple(
            entry
            for entry in report.entries
            if u.Infra.codemod_context_admits(
                m.Infra.CodemodAdmission(
                    root=root,
                    rule=rules_by_id[entry.rule_id],
                    file_path=entry.file,
                    captures=FlextInfraModGateEngine._captures(entry.payload),
                    facts=facts,
                    snapshot=snapshot,
                ),
            )
        )
        if len(entries) == len(report.entries):
            return report
        return FlextInfraModGateEngine.recounted(entries)

    @staticmethod
    def recounted(
        entries: t.VariadicTuple[m.Infra.ModScanFinding],
    ) -> m.Infra.ModScanReport:
        """Return the scan report of exactly these findings, classes recounted.

        Returns:
            The scan report of exactly these findings, classes recounted.

        """
        classes = [entry.classification for entry in entries]
        return m.Infra.ModScanReport(
            findings=len(entries),
            actionable=classes.count(c.Infra.ModScanFindingClass.ACTIONABLE),
            detection_only=classes.count(c.Infra.ModScanFindingClass.DETECTION_ONLY),
            non_actionable_with_fix=classes.count(
                c.Infra.ModScanFindingClass.NON_ACTIONABLE_WITH_FIX,
            ),
            files=frozenset(entry.file for entry in entries),
            entries=entries,
        )

    @classmethod
    def authored(cls, report: m.Infra.ModScanReport) -> m.Infra.ModScanReport:
        """Return the findings mod may rewrite: a generated source is never one.

        A generator finding stays blocking evidence for its generator; it never
        holds back the rewrites of the authored sources.

        Returns:
            The findings mod may rewrite: a generated source is never one.

        """
        return cls.recounted(
            tuple(
                entry for entry in report.entries if entry.source_owner != "generator"
            ),
        )

    @staticmethod
    def _captures(payload: t.JsonMapping) -> t.JsonMapping:
        """Return one finding's single and transformed metavariables.

        Returns:
            One finding's single and transformed metavariables.

        """
        meta = payload.get("metaVariables")
        captures: t.MutableMappingKV[str, t.JsonValue] = {}
        if isinstance(meta, Mapping):
            for group in ("single", "transformed"):
                values = meta.get(group)
                if isinstance(values, Mapping):
                    captures.update(values)
        return captures

    @staticmethod
    def _validate_expected_receipts(
        rules: t.SequenceOf[m.Infra.CodemodRule],
        report: m.Infra.ModScanReport,
    ) -> p.Result[bool]:
        """Require every declared finding-count receipt to match exactly.

        Same contract the sed-by-list phase owns for text rules: a rule that
        declares how many findings it must produce turns silent drift into a
        loud failure. A guard that stops matching, or a pattern that starts
        over-matching after an unrelated edit, is otherwise invisible — the
        cascade simply rewrites more or less than its author proved. Rules
        that declare no receipt are unconstrained.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        counts: MutableMapping[str, int] = {}
        for entry in report.entries:
            counts[entry.rule_id] = counts.get(entry.rule_id, 0) + 1
        for rule in rules:
            if rule.expected is None:
                continue
            observed = counts.get(rule.id, 0)
            if observed != rule.expected:
                return r[bool].fail(
                    f"ast-grep rule {rule.id} declares {rule.expected} "
                    f"finding(s), scan produced {observed}",
                )
        return r[bool].ok(value=True)

    @staticmethod
    def _parse_findings(
        stdout: str,
        root: Path,
        rule_files_by_id: Mapping[str, Path],
        fixable_ids: frozenset[str],
        source_states: Mapping[Path, m.Cli.AtomicFileState],
    ) -> p.Result[m.Infra.ModScanReport]:
        """Validate every JSONL finding without dropping malformed output.

        Returns:
            The resulting ``p.Result[m.Infra.ModScanReport]``.

        """
        findings = 0
        actionable_findings = 0
        detection_only_findings = 0
        non_actionable_with_fix_findings = 0
        files: set[Path] = set()
        entries: list[m.Infra.ModScanFinding] = []
        repository_roots = tuple(
            sorted(
                u.Infra.governed_project_roots(root),
                key=FlextInfraModGateEngine._path_depth,
                reverse=True,
            ),
        )
        for raw_line in stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parsed = u.Cli.json_parse(line)
            if parsed.failure:
                return r.from_failure(parsed)
            if not isinstance(parsed.value, Mapping):
                return r[m.Infra.ModScanReport].fail(
                    f"ast-grep JSONL finding is not an object: {line}",
                )
            finding = parsed.value
            rule_id = finding.get("ruleId")
            text = finding.get("text")
            file = finding.get("file")
            source_range = finding.get("range")
            raw_replacement = finding.get("replacement")
            severity = finding.get("severity")
            if not isinstance(rule_id, str) or rule_id not in rule_files_by_id:
                return r[m.Infra.ModScanReport].fail(
                    f"invalid ast-grep finding contract: {line}",
                )
            if not isinstance(text, str) or not isinstance(file, str):
                return r[m.Infra.ModScanReport].fail(
                    f"invalid ast-grep finding contract: {line}",
                )
            if not isinstance(source_range, Mapping):
                return r[m.Infra.ModScanReport].fail(
                    f"invalid ast-grep finding contract: {line}",
                )
            if raw_replacement is not None and not isinstance(raw_replacement, str):
                return r[m.Infra.ModScanReport].fail(
                    f"invalid ast-grep finding contract: {line}",
                )
            if severity not in {"error", "warning", "info", "hint"}:
                return r[m.Infra.ModScanReport].fail(
                    f"invalid ast-grep finding severity: {line}",
                )
            file_path = Path(file)
            resolved_file = (root / file_path).resolve()
            snapshot = source_states.get(resolved_file)
            if snapshot is None or snapshot.content is None:
                return r[m.Infra.ModScanReport].fail(
                    f"finding has no authenticated source snapshot: {resolved_file}",
                )
            observed = u.Cli.atomic_read_binary_file_state(resolved_file, required=True)
            if observed.failure:
                return r[m.Infra.ModScanReport].from_failure(observed)
            if observed.value != snapshot:
                return r[m.Infra.ModScanReport].fail(
                    f"finding source changed during scanning: {resolved_file}",
                )
            source = snapshot.content.decode(c.Cli.ENCODING_DEFAULT)
            files.add(file_path)
            replacement = raw_replacement if isinstance(raw_replacement, str) else None
            actionable = False
            if rule_id in fixable_ids:
                if not isinstance(replacement, str):
                    return r[m.Infra.ModScanReport].fail(
                        f"fixable ast-grep finding lacks replacement: {line}",
                    )
                actionable = text != replacement
                if actionable:
                    actionable_findings += 1
                    classification = c.Infra.ModScanFindingClass.ACTIONABLE
                else:
                    non_actionable_with_fix_findings += 1
                    classification = c.Infra.ModScanFindingClass.NON_ACTIONABLE_WITH_FIX
            else:
                if replacement is not None:
                    return r[m.Infra.ModScanReport].fail(
                        f"detection-only ast-grep finding has replacement: {line}",
                    )
                detection_only_findings += 1
                classification = c.Infra.ModScanFindingClass.DETECTION_ONLY
            repository = next(
                (
                    candidate.name
                    for candidate in repository_roots
                    if resolved_file.is_relative_to(candidate)
                ),
                root.resolve().name,
            )
            entries.append(
                m.Infra.ModScanFinding(
                    rule_file=str(rule_files_by_id[rule_id].resolve()),
                    rule_id=rule_id,
                    repository=repository,
                    file=file_path,
                    source_owner="generator"
                    if source.startswith(c.Infra.AUTOGEN_HEADERS)
                    else "authored",
                    source_state=snapshot,
                    range=t.Cli.JSON_MAPPING_ADAPTER.validate_python(source_range),
                    text=text,
                    replacement=replacement,
                    actionable=actionable,
                    classification=classification,
                    payload=t.Cli.JSON_MAPPING_ADAPTER.validate_python(finding),
                ),
            )
            findings += 1
        return r.ok(
            m.Infra.ModScanReport(
                findings=findings,
                actionable=actionable_findings,
                detection_only=detection_only_findings,
                non_actionable_with_fix=non_actionable_with_fix_findings,
                files=frozenset(files),
                entries=tuple(entries),
            ),
        )

    @staticmethod
    def _report_evidence(receipt: m.Infra.ModScanEvidenceReceipt) -> None:
        """Print bounded totals and the authenticated full-evidence identity."""
        evidence = receipt.evidence
        sys.stderr.write(
            "mod: findings "
            f"total={evidence.findings} actionable={evidence.actionable} "
            f"detection_only={evidence.detection_only} "
            f"non_actionable_with_fix={evidence.non_actionable_with_fix}\n",
        )
        for finding_class, count in evidence.totals_by_class.items():
            sys.stderr.write(
                f"mod: findings class={finding_class.value} count={count}\n",
            )
        for repository, count in evidence.totals_by_repository.items():
            sys.stderr.write(f"mod: findings repository={repository} count={count}\n")
        for rule_id, count in evidence.totals_by_rule.items():
            sys.stderr.write(f"mod: findings rule={rule_id} count={count}\n")
        sys.stderr.write(
            f"mod: findings report={receipt.path} sha256={receipt.sha256}\n",
        )
        sys.stderr.flush()

    @classmethod
    def scan(cls, root: Path, *, fix: bool) -> p.Result[m.Infra.ModScanReport]:
        """Scan or apply every ruleset elected by the composed rule-plan SSOT.

        Returns:
            The resulting ``p.Result[m.Infra.ModScanReport]``.

        """
        planned = u.Infra.codemod_rule_plan(root)
        if planned.failure:
            return r[m.Infra.ModScanReport].from_failure(planned)
        plan = planned.value
        findings = 0
        actionable_findings = 0
        detection_only_findings = 0
        non_actionable_with_fix_findings = 0
        files: set[Path] = set()
        entries: list[m.Infra.ModScanFinding] = []
        rule_files_by_id = {rule.id: rule.resource for rule in plan.rules}
        rules_by_id = {rule.id: rule for rule in plan.rules}
        targets = u.Infra.ast_grep_scan_targets(root)
        sys.stderr.write(
            f"mod: ast-grep {'apply' if fix else 'scan'} "
            f"providers={len(plan.rulesets)} rules={len(plan.rules)}\n",
        )
        sys.stderr.flush()
        for ruleset in plan.rulesets:
            source_paths: set[Path] = set()
            for target in targets:
                path = root / target
                if path.is_dir():
                    source_paths.update(u.Infra.iter_directory_python_files(path))
                else:
                    source_paths.add(path)
            source_states = {
                path.resolve(): u.Cli.atomic_read_binary_file_state(
                    path,
                    required=True,
                ).unwrap()
                for path in sorted(source_paths)
            }
            ruleset_files = {
                rule_id: rule_files_by_id[rule_id] for rule_id in ruleset.rule_ids
            }
            scan_command = u.Infra.ast_grep_scan_command(
                ruleset.config,
                rule_ids=ruleset.rule_ids,
                targets=targets,
                json_stream=True,
            )
            run = cls._run_tool(root, scan_command, finding_exit_code=1)
            if run.failure:
                return r[m.Infra.ModScanReport].from_failure(run)
            report = cls._parse_findings(
                run.value.stdout,
                root,
                ruleset_files,
                frozenset(ruleset.fixable_rule_ids),
                source_states,
            ).unwrap()
            if run.value.outcome.raw_return_code != 0:
                error_findings = sum(
                    entry.payload.get("severity") == "error" for entry in report.entries
                )
                cls._validate_finding_receipt(run.value.stderr, error_findings).unwrap()
            report = cls._admitted(root, report, rules_by_id)
            findings += report.findings
            actionable_findings += report.actionable
            detection_only_findings += report.detection_only
            non_actionable_with_fix_findings += report.non_actionable_with_fix
            files.update(report.files)
            entries.extend(report.entries)
        complete_report = m.Infra.ModScanReport(
            findings=findings,
            actionable=actionable_findings,
            detection_only=detection_only_findings,
            non_actionable_with_fix=non_actionable_with_fix_findings,
            files=frozenset(files),
            entries=tuple(entries),
        )
        declared = cls._validate_expected_receipts(plan.rules, complete_report)
        if declared.failure:
            return r[m.Infra.ModScanReport].from_failure(declared)
        receipt = u.Infra.publish_mod_scan_evidence(
            root,
            complete_report,
            command=(
                c.Infra.ModScanCommand.APPLY if fix else c.Infra.ModScanCommand.SCAN
            ),
            scope=targets,
        )
        if receipt.failure:
            return r[m.Infra.ModScanReport].from_failure(receipt)
        cls._report_evidence(receipt.value)
        if fix:
            from flext_infra.codemod.batch_replacements import FlextInfraModReplacements

            published = FlextInfraModReplacements.publish(root, complete_report)
            if published.failure:
                return r[m.Infra.ModScanReport].from_failure(published)
        return r[m.Infra.ModScanReport].ok(complete_report)


__all__: list[str] = ["FlextInfraModGateEngine"]
