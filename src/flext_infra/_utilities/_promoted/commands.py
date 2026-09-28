"""Promoted-command header ingress: ``cosmos-command`` TOML into commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c

from .workspace import FlextInfraUtilitiesPromotedWorkspace

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraUtilitiesPromotedCommands(FlextInfraUtilitiesPromotedWorkspace):
    """Parse each verb-directory header once into canonical command models."""

    @staticmethod
    def promoted_command_headers(
        verb_dir: Path,
    ) -> t.MappingKV[Path, t.JsonMapping | c.Infra.PromotedRegistryError]:
        """Parse every candidate header of one verb directory."""
        from flext_infra import u

        header = c.Infra.PromotedHeader
        headers: t.MutableMappingKV[
            Path, t.JsonMapping | c.Infra.PromotedRegistryError
        ] = {}
        for path in verb_dir.iterdir():
            if (
                not path.is_file()
                or path.suffix not in c.Infra.PROMOTED_COMMAND_SUFFIXES
                or path.name in c.Infra.PROMOTED_NON_COMMAND_NAMES
            ):
                continue
            lines = path.read_text(encoding=c.Infra.ENCODING_DEFAULT).splitlines()
            in_header = False
            payload: list[str] = []
            for raw in lines[: c.Infra.PROMOTED_HEADER_SCAN_LINES]:
                content = raw.strip().removeprefix(header.COMMENT).strip()
                if content == header.START:
                    in_header = True
                elif in_header and content == header.END:
                    break
                elif in_header:
                    payload.append(content)
            if not payload:
                headers[path] = c.Infra.PromotedMissingHeaderError(
                    c.Infra.PromotedMessage.MISSING_HEADER.format(path=path)
                )
                continue
            parsed = u.Cli.toml_mapping_from_text(
                c.Infra.PromotedJoin.LINES.join(payload)
            )
            headers[path] = (
                parsed
                if parsed is not None
                else c.Infra.PromotedRegistryError(
                    c.Infra.PromotedMessage.INVALID_HEADER_TOML.format(path=path)
                )
            )
        return headers

    @classmethod
    def promoted_load_command(
        cls, path: Path, expected_verb: str, data: t.JsonMapping
    ) -> p.Infra.PromotedCommand:
        """Validate one header against its directory and file, once at ingress."""
        from flext_infra import m

        key = c.Infra.PromotedHeader
        message = c.Infra.PromotedMessage
        verb = cls._promoted_text(data, key.VERB, path)
        what = cls._promoted_text(data, key.WHAT, path)
        for actual, expected, mismatch in (
            (verb, expected_verb, message.VERB_MISMATCH),
            (what, path.stem, message.WHAT_MISMATCH),
        ):
            if actual != expected:
                cls.promoted_fail(
                    mismatch, path=path, verb=verb, what=what, expected=expected
                )
        params_raw = data.get(key.PARAMS, [])
        if not isinstance(params_raw, list):
            cls.promoted_fail(message.PARAMS_NOT_LIST, path=path)
        params = []
        for item in params_raw:
            if not isinstance(item, dict):
                cls.promoted_fail(message.PARAMS_NOT_TABLE, path=path)
            required = item.get(key.REQUIRED, False)
            default = item.get(key.DEFAULT, "")
            if not isinstance(required, bool):
                cls.promoted_fail(message.PARAMS_REQUIRED_TYPE, path=path)
            if not isinstance(default, str):
                cls.promoted_fail(message.PARAMS_DEFAULT_TYPE, path=path)
            params.append(
                m.Infra.PromotedParam(
                    name=cls._promoted_text(item, key.NAME, path),
                    help=cls._promoted_text(item, key.HELP, path),
                    required=required,
                    default=default,
                    choices=cls._promoted_texts(
                        item.get(key.CHOICES, []), key.PARAMS_CHOICES, path
                    ),
                )
            )
        domain = cls._promoted_text(data, key.DOMAIN, path)
        summary = cls._promoted_text(data, key.SUMMARY, path)
        description = cls._promoted_text(data, key.DESCRIPTION, path)
        example = cls._promoted_text(data, key.EXAMPLE, path)
        mutates = data.get(key.MUTATES)
        if not isinstance(mutates, bool):
            cls.promoted_fail(message.REQUIRED_BOOL, path=path, key=key.MUTATES)
        return m.Infra.PromotedCommand(
            verb=verb,
            what=what,
            domain=domain,
            summary=summary,
            description=description,
            example=example,
            path=path,
            mutates=mutates,
            aliases=cls._promoted_texts(data.get(key.ALIASES, []), key.ALIASES, path),
            params=tuple(params),
            rules=cls._promoted_texts(data.get(key.RULES, []), key.RULES, path),
        )

    @classmethod
    def _promoted_text(
        cls, data: t.MappingKV[str, t.JsonValue], key: str, path: Path
    ) -> str:
        """Return one required non-blank stripped header string."""
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            cls.promoted_fail(
                c.Infra.PromotedMessage.REQUIRED_STRING, path=path, key=key
            )
        return value.strip()

    @classmethod
    def _promoted_texts(
        cls, values: t.JsonValue, key: str, path: Path
    ) -> t.VariadicTuple[str]:
        """Return one optional header list of non-blank stripped strings."""
        if not isinstance(values, list):
            cls.promoted_fail(
                c.Infra.PromotedMessage.STRING_LIST_TYPE, path=path, key=key
            )
        texts: list[str] = []
        for item in values:
            if not isinstance(item, str) or not item.strip():
                cls.promoted_fail(
                    c.Infra.PromotedMessage.STRING_LIST_ITEM, path=path, key=key
                )
            texts.append(item.strip())
        return tuple(texts)


__all__: list[str] = ["FlextInfraUtilitiesPromotedCommands"]
