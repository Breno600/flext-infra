"""VS Code settings codegen owner — the single canonical merge instrumentation.

This is the only place that knows how ``.vscode/settings.json`` is produced.
It parses that explicitly JSONC document through the canonical string-aware
normalizer, validates the resulting mapping, merges the config-driven canonical
keys from ``config.Infra.codegen.vscode`` plus the artifact-derived exclude maps,
and serializes the result with ``u.Cli.json_dumps``. Rendering is deliberately
independent of repository topology so opening a root or declared_repository produces the
same document. Planning, atomic writes, and fixed-point verification stay owned
by ``FlextInfraCodegenConform``.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, config, t, u

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraCodegenVscodeMixin:
    """Produce the canonical ``.vscode/settings.json`` document for one root."""

    @classmethod
    def render_vscode_settings(cls, repository_root: Path) -> p.Result[str]:
        """Return the canonical-merged ``settings.json`` document for one root."""
        settings_path = (
            repository_root / c.Infra.VSCODE_DIRNAME / c.Infra.VSCODE_SETTINGS_FILENAME
        )
        read_result = cls._read_existing_settings(settings_path)
        if read_result.failure:
            return r[str].from_failure(read_result)
        settings: t.MutableJsonMapping = {
            key: u.normalize_to_json_value(value)
            for key, value in read_result.value.items()
        }
        applied = cls._apply_canonical_settings(settings, repository_root)
        if applied.failure:
            return r[str].from_failure(applied)
        serialized = u.Cli.json_dumps(dict(settings), indent=2)
        if serialized.failure:
            return r[str].from_failure(serialized)
        return r[str].ok(serialized.value + "\n")

    @classmethod
    def _read_existing_settings(cls, settings_path: Path) -> p.Result[t.JsonMapping]:
        """Read one VS Code JSONC document into a validated JSON mapping."""
        if not settings_path.exists():
            empty_settings: t.JsonMapping = {}
            return r[t.JsonMapping].ok(empty_settings)
        read_result = u.Cli.files_read_text(settings_path)
        if read_result.failure:
            return r[t.JsonMapping].from_failure(read_result)
        parsed = u.Cli.json_parse(cls._normalize_jsonc(read_result.value))
        if parsed.failure:
            return r[t.JsonMapping].from_failure(parsed)
        if not isinstance(parsed.value, Mapping):
            return r[t.JsonMapping].fail("VS Code settings root must be an object")
        return r[t.JsonMapping].ok(
            t.Cli.JSON_MAPPING_ADAPTER.validate_python(parsed.value)
        )

    @classmethod
    def _normalize_jsonc(cls, content: str) -> str:
        """Return strict JSON text from VS Code JSONC content."""
        return cls._remove_trailing_commas(cls._remove_jsonc_comments(content))

    @staticmethod
    def _copy_string_literal(content: str, index: int, output: list[str]) -> int:
        """Copy one complete JSON string literal to ``output``.

        ``index`` points at the opening quote; the returned index is the first
        character after the literal, so structural scanners never re-enter a
        string and never interpret its contents.
        """
        output.append(content[index])
        index += 1
        escaped = False
        while index < len(content):
            char = content[index]
            output.append(char)
            index += 1
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                break
        return index

    @staticmethod
    def _remove_jsonc_comments(content: str) -> str:
        """Remove JSONC comments while preserving comment markers in strings."""
        output: list[str] = []
        in_line_comment = False
        in_block_comment = False
        index = 0
        while index < len(content):
            char = content[index]
            next_char = content[index + 1] if index + 1 < len(content) else ""
            if in_line_comment:
                if char in "\r\n":
                    in_line_comment = False
                    output.append(char)
                index += 1
                continue
            if in_block_comment:
                if char == "*" and next_char == "/":
                    in_block_comment = False
                    index += 2
                    continue
                index += 1
                continue
            if char == '"':
                index = FlextInfraCodegenVscodeMixin._copy_string_literal(
                    content, index, output
                )
                continue
            if char == "/" and next_char == "/":
                in_line_comment = True
                index += 2
                continue
            if char == "/" and next_char == "*":
                in_block_comment = True
                index += 2
                continue
            output.append(char)
            index += 1
        return "".join(output)

    @staticmethod
    def _remove_trailing_commas(content: str) -> str:
        """Remove commas before object or array closers outside strings."""
        output: list[str] = []
        index = 0
        while index < len(content):
            char = content[index]
            if char == '"':
                index = FlextInfraCodegenVscodeMixin._copy_string_literal(
                    content, index, output
                )
                continue
            if char == ",":
                next_index = index + 1
                while next_index < len(content) and content[next_index].isspace():
                    next_index += 1
                if next_index < len(content) and content[next_index] in "}]":
                    index += 1
                    continue
            output.append(char)
            index += 1
        return "".join(output)

    @classmethod
    def _apply_canonical_settings(
        cls, settings: t.MutableJsonMapping, repository_root: Path
    ) -> p.Result[bool]:
        """Merge canonical codegen VS Code settings into one settings mapping."""
        spec = config.Infra.codegen.vscode
        changed = cls._apply_enforced_settings(
            settings,
            scalar_settings=spec.scalar_settings,
            list_settings=spec.list_settings,
            repository_root=repository_root,
        )
        if changed.failure:
            return r[bool].from_failure(changed)
        # The three exclude maps are complete projections of the artifact SSOT.
        # Replacing them removes retired artifacts instead of preserving stale
        # generated keys forever. Only explicitly declared non-artifact maps use
        # merge semantics.
        codegen = config.Infra.codegen
        artifact_maps: MutableMapping[str, Mapping[str, str | bool]] = {
            "files.exclude": dict(codegen.vscode_files_exclude_map),
            "files.watcherExclude": dict(codegen.vscode_watcher_exclude_map),
            "search.exclude": dict(codegen.vscode_search_exclude_map),
        }
        artifacts_changed = False
        for key, canonical_map in artifact_maps.items():
            canonical = {
                name: u.normalize_to_json_value(value)
                for name, value in canonical_map.items()
            }
            if settings.get(key) == canonical:
                continue
            settings[key] = canonical
            artifacts_changed = True
        # Stripped keys are owned canonically by pyproject.toml [tool.pyright];
        # keeping them in settings.json makes Pylance emit settingsNotOverridable
        # warnings. Actively delete every retired key so existing files converge
        # to a warning-free projection.
        stripped_changed = cls._strip_retired_keys(settings, spec.stripped_keys)
        return r[bool].ok(
            cls._apply_union_settings(settings, spec.map_union_settings)
            or artifacts_changed
            or stripped_changed
            or changed.value
        )

    @staticmethod
    def _strip_retired_keys(
        settings: t.MutableJsonMapping, stripped_keys: t.StrSequence
    ) -> bool:
        """Delete every key listed in ``stripped_keys`` from the settings mapping."""
        changed = False
        for key in stripped_keys:
            if key in settings:
                del settings[key]
                changed = True
        return changed

    @classmethod
    def _apply_enforced_settings(
        cls,
        settings: t.MutableJsonMapping,
        *,
        scalar_settings: Mapping[str, str | bool | int],
        list_settings: Mapping[str, t.VariadicTuple[str]],
        repository_root: Path,
    ) -> p.Result[bool]:
        """Enforce exact scalar and list VS Code keys from the codegen config."""
        changed = False
        for key, value in scalar_settings.items():
            normalized = u.normalize_to_json_value(value)
            if settings.get(key) == normalized:
                continue
            settings[key] = normalized
            changed = True
        for key, list_value in list_settings.items():
            entries = cls._resolve_list_setting(
                key, list_value, repository_root=repository_root
            )
            if entries.failure:
                return r[bool].from_failure(entries)
            canonical: list[t.JsonValue] = [
                u.normalize_to_json_value(entry) for entry in entries.value
            ]
            if settings.get(key) == canonical:
                continue
            settings[key] = canonical
            changed = True
        return r[bool].ok(changed)

    @staticmethod
    def _apply_union_settings(
        settings: t.MutableJsonMapping,
        map_union_settings: Mapping[str, Mapping[str, str | bool | int]],
    ) -> bool:
        """Union-merge canonical map keys over existing project entries."""
        changed = False
        for key, canonical_map in map_union_settings.items():
            current = settings.get(key)
            existing: t.MutableJsonMapping = (
                {
                    name: u.normalize_to_json_value(value)
                    for name, value in current.items()
                }
                if isinstance(current, Mapping)
                else {}
            )
            merged = {
                **dict(existing),
                **{
                    name: u.normalize_to_json_value(value)
                    for name, value in canonical_map.items()
                },
            }
            if settings.get(key) == merged:
                continue
            settings[key] = merged
            changed = True
        return changed

    @staticmethod
    def _apply_exact_map_settings(
        settings: t.MutableJsonMapping,
        exact_maps: Mapping[str, Mapping[str, str | bool | int]],
    ) -> bool:
        """Replace generated maps so removed SSOT entries leave no residue."""
        changed = False
        for key, canonical_map in exact_maps.items():
            exact = {
                name: u.normalize_to_json_value(value)
                for name, value in canonical_map.items()
            }
            if settings.get(key) == exact:
                continue
            settings[key] = exact
            changed = True
        return changed

    @staticmethod
    def _resolve_list_setting(
        key: str, base_entries: t.VariadicTuple[str], *, repository_root: Path
    ) -> p.Result[t.VariadicTuple[str]]:
        """Return one canonical list without consulting repository topology."""
        del key, repository_root
        return r[t.VariadicTuple[str]].ok(base_entries)


__all__: list[str] = ["FlextInfraCodegenVscodeMixin"]
