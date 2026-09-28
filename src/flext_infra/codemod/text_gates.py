"""Declarative sed-by-list text rules for the ``make mod`` cascade.

Capability imported from the flext-infra ``0.20.0-dev`` line and namespaced
into this makemod cascade beside the ast-grep fixed point: every rule is one
list entry in ``text_rules.yml``, one rewrite is a list-driven regex
replacement with an exact expected-count receipt, and the phase reaches a
verified rewrite fixed point before the canonical validate gate runs.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import functools
import re
from bisect import bisect_right
from fnmatch import fnmatch
from pathlib import Path

from flext_core import r

from .. import c, m, p, t, u
from ..codegen import FlextInfraCodegenMiseArtifacts, FlextInfraCodegenTransaction


class FlextInfraModTextGateEngine:
    """Scan, apply, and prove the declarative sed-by-list rule cascade."""

    @classmethod
    def load_rules(cls, root: Path) -> p.Result[t.VariadicTuple[m.Infra.ModTextRule]]:
        """Load package and workspace text rules into one validated tuple."""
        snapshot = u.Cli.atomic_read_binary_file_state(
            root / c.Infra.CODEMOD_TEXT_RULES_RELPATH, required=False
        )
        if snapshot.failure:
            return r[t.VariadicTuple[m.Infra.ModTextRule]].from_failure(snapshot)
        return cls._rules_from_state(snapshot.value)

    @classmethod
    def _rules_from_state(
        cls, snapshot: m.Cli.AtomicFileState
    ) -> p.Result[t.VariadicTuple[m.Infra.ModTextRule]]:
        """Parse only the exact authenticated catalogue bytes used by the plan."""
        if snapshot.content is None:
            return r[t.VariadicTuple[m.Infra.ModTextRule]].ok(())
        source = snapshot.path
        rules: list[m.Infra.ModTextRule] = []
        seen: set[str] = set()
        parsed = u.Cli.yaml_parse(snapshot.content.decode(c.Cli.ENCODING_DEFAULT))
        if parsed.failure:
            return r[t.VariadicTuple[m.Infra.ModTextRule]].from_failure(parsed)
        listing = parsed.value.get(c.Infra.CODEMOD_TEXT_RULES_KEY)
        if not isinstance(listing, list):
            return r[t.VariadicTuple[m.Infra.ModTextRule]].fail(
                f"text rule file declares no rules list: {source}"
            )
        for raw in listing:
            rule = cls._build_rule(raw, source)
            if rule.failure:
                return r[t.VariadicTuple[m.Infra.ModTextRule]].from_failure(rule)
            if rule.value.rule_id in seen:
                return r[t.VariadicTuple[m.Infra.ModTextRule]].fail(
                    f"duplicate text rule id {rule.value.rule_id} in {source}"
                )
            seen.add(rule.value.rule_id)
            rules.append(rule.value)
        return r[t.VariadicTuple[m.Infra.ModTextRule]].ok(tuple(rules))

    @staticmethod
    def _build_rule(
        raw: p.AttributeProbe, source: Path
    ) -> p.Result[m.Infra.ModTextRule]:
        """Validate one raw list entry into a frozen text rule."""
        if not isinstance(raw, dict):
            return r[m.Infra.ModTextRule].fail(
                f"text rule entry must be a mapping in {source}: {raw!r}"
            )
        unknown = set(raw).difference((
            c.Infra.CODEMOD_TEXT_KEY_ID,
            c.Infra.CODEMOD_TEXT_KEY_DESCRIPTION,
            c.Infra.CODEMOD_TEXT_KEY_INCLUDE,
            c.Infra.CODEMOD_TEXT_KEY_EXCLUDE,
            c.Infra.CODEMOD_TEXT_KEY_FIND,
            c.Infra.CODEMOD_TEXT_KEY_REPLACE,
            c.Infra.CODEMOD_TEXT_KEY_FLAGS,
            c.Infra.CODEMOD_TEXT_KEY_EXPECTED,
        ))
        if unknown:
            return r[m.Infra.ModTextRule].fail(
                f"unknown text rule keys {sorted(unknown)} in {source}"
            )
        flag_names = tuple(
            str(flag) for flag in raw.get(c.Infra.CODEMOD_TEXT_KEY_FLAGS, ())
        )
        unknown_flags = set(flag_names).difference(c.Infra.CODEMOD_TEXT_FLAG_NAMES)
        if unknown_flags:
            return r[m.Infra.ModTextRule].fail(
                f"unknown regex flag names {sorted(unknown_flags)} in {source}"
            )
        find = raw.get(c.Infra.CODEMOD_TEXT_KEY_FIND)
        if not isinstance(find, str) or not find:
            return r[m.Infra.ModTextRule].fail(
                f"text rule requires a non-empty find regex in {source}"
            )
        expected = raw.get(c.Infra.CODEMOD_TEXT_KEY_EXPECTED)
        if expected is not None and (
            not isinstance(expected, int) or isinstance(expected, bool) or expected < 0
        ):
            return r[m.Infra.ModTextRule].fail(
                f"text rule expected receipt must be a non-negative integer in {source}"
            )
        try:
            re.compile(find)
        except re.error as error:
            return r[m.Infra.ModTextRule].fail(
                f"invalid find regex in {source}: {error}"
            )
        rule = m.Infra.ModTextRule(
            rule_id=str(raw.get(c.Infra.CODEMOD_TEXT_KEY_ID, "")),
            description=str(raw.get(c.Infra.CODEMOD_TEXT_KEY_DESCRIPTION, "")),
            include=tuple(
                str(glob) for glob in raw.get(c.Infra.CODEMOD_TEXT_KEY_INCLUDE, ())
            ),
            exclude=tuple(
                str(glob) for glob in raw.get(c.Infra.CODEMOD_TEXT_KEY_EXCLUDE, ())
            ),
            find=find,
            replace=str(raw.get(c.Infra.CODEMOD_TEXT_KEY_REPLACE, "")),
            flags=flag_names,
            expected=expected,
        )
        if not rule.rule_id:
            return r[m.Infra.ModTextRule].fail(
                f"text rule requires a non-empty id in {source}"
            )
        return r[m.Infra.ModTextRule].ok(rule)

    @classmethod
    def scan(
        cls, root: Path, *, fix: bool, validate_receipts: bool = False
    ) -> p.Result[m.Infra.ModTextReport]:
        """Scan the governed surface or apply every rule rewrite in place."""
        root = root.absolute()
        catalogue_result = u.Cli.atomic_read_binary_file_state(
            root / c.Infra.CODEMOD_TEXT_RULES_RELPATH, required=False
        )
        if catalogue_result.failure:
            return r[m.Infra.ModTextReport].from_failure(catalogue_result)
        catalogue = catalogue_result.value
        loaded = cls._rules_from_state(catalogue)
        if loaded.failure:
            return r[m.Infra.ModTextReport].from_failure(loaded)
        rules = loaded.value
        targets = u.Infra.ast_grep_scan_targets(root)
        entries: list[m.Infra.ModTextFinding] = []
        files: set[Path] = set()
        actionable = 0
        inputs = [catalogue]
        plans: list[m.Infra.CodegenFilePlan] = []
        inventoried: set[Path] = set()
        for target in targets:
            candidate = root / target
            paths = (
                tuple(sorted(candidate.rglob(f"*{c.Infra.EXT_PYTHON}")))
                if candidate.is_dir()
                else (candidate,)
            )
            for path in paths:
                if path in inventoried:
                    continue
                inventoried.add(path)
                relative = path.relative_to(root).as_posix()
                captured = u.Cli.atomic_read_binary_file_state(path, required=True)
                if captured.failure:
                    return r[m.Infra.ModTextReport].from_failure(captured)
                before = captured.value
                if before.content is None:
                    return r[m.Infra.ModTextReport].fail(
                        f"text source disappeared during inventory: {path}"
                    )
                inputs.append(before)
                source = before.content.decode(c.Cli.ENCODING_DEFAULT)
                updated, target_entries, target_actionable = cls._rewrite_source(
                    source, relative, rules
                )
                entries.extend(target_entries)
                actionable += target_actionable
                if target_entries:
                    files.add(Path(relative))
                if fix and updated != source:
                    if source.startswith(c.Infra.AUTOGEN_HEADERS):
                        return r[m.Infra.ModTextReport].fail(
                            f"generated findings require canonical generator repair: {path}"
                        )
                    plans.append(
                        m.Infra.CodegenFilePlan(
                            project=root,
                            path=path,
                            before=before,
                            desired_content=updated.encode(c.Cli.ENCODING_DEFAULT),
                            desired_mode=before.mode,
                            source_states=(catalogue, before),
                            owner="mod-text",
                        )
                    )
        report = m.Infra.ModTextReport(
            findings=len(entries),
            actionable=actionable,
            files=frozenset(files),
            entries=tuple(entries),
        )
        if validate_receipts:
            cls._validate_expected_receipts(rules, report)
        if fix and plans:
            published = cls._publish(root, tuple(plans), tuple(inputs))
            if published.failure:
                return r[m.Infra.ModTextReport].from_failure(published)
        return r[m.Infra.ModTextReport].ok(report)

    @staticmethod
    def _publish(
        root: Path,
        plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
        inputs: t.VariadicTuple[m.Cli.AtomicFileState],
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Publish the complete authenticated batch through the shared journal."""
        transaction = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root)
        )
        roots = {"@mod-text": root}
        analysis = m.Infra.CodegenPhaseAnalysis(
            phase="mod-text", files=plans, inputs=inputs
        )

        def validate_inventory() -> p.Result[bool]:
            expected = {
                state.path
                for state in inputs
                if state.path != root / c.Infra.CODEMOD_TEXT_RULES_RELPATH
            }
            observed: set[Path] = set()
            for target in u.Infra.ast_grep_scan_targets(root):
                candidate = root / target
                observed.update(
                    candidate.rglob(f"*{c.Infra.EXT_PYTHON}")
                    if candidate.is_dir()
                    else (candidate,)
                )
            if observed != expected:
                return r[bool].fail("text source inventory changed before publication")
            return r[bool].ok(True)

        def validate_published() -> p.Result[bool]:
            inventory = validate_inventory()
            if inventory.failure:
                return inventory
            return transaction.validate_phase_analysis_locked(analysis)

        def publish(scope_root: Path) -> p.Result[t.VariadicTuple[Path]]:
            inventory = validate_inventory()
            if inventory.failure:
                return r[t.VariadicTuple[Path]].from_failure(inventory)
            started = transaction.begin_files_locked(scope_root, roots, inputs)
            if started.failure:
                return r[t.VariadicTuple[Path]].from_failure(started)

            def apply(
                session: m.Infra.CodegenTransactionSession,
            ) -> p.Result[t.VariadicTuple[Path]]:
                published = transaction.append_phase_locked(
                    session, analysis.phase, plans
                )
                if published.failure:
                    return r[t.VariadicTuple[Path]].from_failure(published)
                return transaction.commit_locked(published.value, validate_published)

            return transaction.publish_prepared_locked(started.value, apply)

        return transaction.run_files_locked(roots, publish)

    @staticmethod
    def _validate_expected_receipts(
        rules: t.VariadicTuple[m.Infra.ModTextRule], report: m.Infra.ModTextReport
    ) -> None:
        """Require exact migration preconditions, including zero-match mismatches.

        A positive expected count is a one-invocation precondition, not an
        idempotence promise after that migration has consumed its matches.
        """
        counts: dict[str, int] = {}
        for entry in report.entries:
            counts[entry.rule_id] = counts.get(entry.rule_id, 0) + 1
        for rule in rules:
            if rule.expected is not None and counts.get(rule.rule_id, 0) != (
                rule.expected
            ):
                msg = (
                    f"text rule {rule.rule_id} expected {rule.expected} finding(s), "
                    f"scan produced {counts.get(rule.rule_id, 0)}"
                )
                raise RuntimeError(msg)

    @classmethod
    def _rewrite_source(
        cls, source: str, target: str, rules: t.VariadicTuple[m.Infra.ModTextRule]
    ) -> t.Triple[str, list[m.Infra.ModTextFinding], int]:
        """Rewrite one source text through every elected rule entry."""
        updated = source
        entries: list[m.Infra.ModTextFinding] = []
        actionable = 0
        for rule in rules:
            if not cls._rule_elects(rule, target):
                continue
            line_starts = [0]
            for line in updated.splitlines(keepends=True):
                line_starts.append(line_starts[-1] + len(line))
            found: list[m.Infra.ModTextFinding] = []
            pattern = cls._compiled(rule)
            expand = functools.partial(
                cls._expand_match, rule, target, line_starts, found
            )
            candidate = pattern.sub(expand, updated)
            if found:
                updated = candidate
                actionable += sum(
                    1 for entry in found if entry.text != entry.replacement
                )
                entries.extend(found)
        return (updated, entries, actionable)

    @staticmethod
    def _expand_match(
        rule: m.Infra.ModTextRule,
        target: str,
        line_starts: t.SequenceOf[int],
        found: list[m.Infra.ModTextFinding],
        match: re.Match[str],
    ) -> str:
        """Record and expand one match, binding every loop value explicitly."""
        replacement = match.expand(rule.replace)
        line_index = bisect_right(line_starts, match.start()) - 1
        found.append(
            m.Infra.ModTextFinding(
                rule_id=rule.rule_id,
                file=Path(target),
                line=line_index + 1,
                text=match.group(0),
                replacement=replacement,
            )
        )
        return replacement

    @staticmethod
    def _rule_elects(rule: m.Infra.ModTextRule, target: str) -> bool:
        """Return whether one target path is elected by the rule globs."""
        if rule.exclude and any(fnmatch(target, glob) for glob in rule.exclude):
            return False
        return not (
            rule.include and not any(fnmatch(target, glob) for glob in rule.include)
        )

    @staticmethod
    def _compiled(rule: m.Infra.ModTextRule) -> re.Pattern[str]:
        """Compile one rule pattern with its declared SSOT flag names."""
        flags = 0
        for name in rule.flags:
            flags |= c.Infra.CODEMOD_TEXT_FLAG_NAMES[name]
        return re.compile(rule.find, flags)


__all__: list[str] = ["FlextInfraModTextGateEngine"]
