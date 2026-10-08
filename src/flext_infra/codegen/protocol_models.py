"""Assemble member structural protocols from validated models on demand.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from importlib import import_module
from pathlib import Path
from types import UnionType
from typing import TypeAliasType, get_args, override

from flext_cli import cli

from flext_infra import m, p, r, t, u
from flext_infra.base import FlextInfraServiceBase
from flext_infra.codegen._protocol_model_annotations import (
    FlextInfraCodegenProtocolModelAnnotations,
)
from flext_infra.codegen._protocol_model_render import (
    FlextInfraCodegenProtocolModelRender,
)


class FlextInfraCodegenProtocolModels(FlextInfraServiceBase[t.Cli.ResultValue]):
    """Assemble the member's generated ``p`` layer from validated models."""

    @override
    def execute(self) -> p.Result[t.Cli.ResultValue]:
        """Assemble generated protocol modules for the member repository.

        Returns:
            The resulting ``p.Result[t.Cli.ResultValue]``.

        """
        targeted = self._resolve_target(self.repository_root)
        if targeted.failure:
            return r[t.Cli.ResultValue].from_failure(targeted)
        target = targeted.value
        resolved = self._resolve_models(self.repository_root, target)
        if resolved.failure:
            return r[t.Cli.ResultValue].from_failure(resolved)
        if not resolved.value:
            cli.display_text(
                "protocol-models: no referenced model protocols to assemble",
            )
            return r[t.Cli.ResultValue].ok(value=True)
        modules = FlextInfraCodegenProtocolModelRender.render_member_modules(
            resolved.value,
            target,
        )
        return self._settle(self.repository_root, modules, dry=self.effective_dry_run)

    @classmethod
    def _resolve_target(
        cls,
        root: Path,
    ) -> p.Result[FlextInfraCodegenProtocolModelAnnotations.ProtocolModelTarget]:
        """Derive the member target from its declared pyproject name.

        Returns:
            The resulting
                ``p.Result[FlextInfraCodegenProtocolModelAnnotations.ProtocolModelTarget]``.

        """
        manifest = root / "pyproject.toml"
        if not manifest.is_file():
            return r[
                FlextInfraCodegenProtocolModelAnnotations.ProtocolModelTarget
            ].fail(f"no pyproject manifest at {manifest}")
        declared = u.Cli.toml_read_json(manifest)
        if declared.failure:
            return r[
                FlextInfraCodegenProtocolModelAnnotations.ProtocolModelTarget
            ].from_failure(declared)
        name = u.Cli.json_pick_str(
            u.Cli.json_deep_mapping(declared.value, "project"),
            "name",
        )
        if not name:
            return r[
                FlextInfraCodegenProtocolModelAnnotations.ProtocolModelTarget
            ].fail(f"pyproject manifest declares no project name: {manifest}")
        package = name.replace("-", "_")
        container = "".join(part.capitalize() for part in package.split("_"))
        return r[FlextInfraCodegenProtocolModelAnnotations.ProtocolModelTarget].ok(
            FlextInfraCodegenProtocolModelAnnotations.ProtocolModelTarget(
                package_name=package,
                facade_container=container,
                package_module_prefix=f"{package}.",
                protocol_ref_prefix=f"p.{container}",
                models_facade_name="m",
                facade_probes=(
                    ("m", f"{package}.models.{container}Models"),
                    ("p", f"{package}.protocols.{container}Protocols"),
                    ("c", f"{package}.constants.{container}Constants"),
                    ("t", f"{package}.typings.{container}Types"),
                ),
            ),
        )

    @classmethod
    def _resolve_models(
        cls,
        root: Path,
        target: FlextInfraCodegenProtocolModelAnnotations.ProtocolModelTarget,
    ) -> p.Result[t.SequenceOf[type[m.BaseModel]]]:
        """Resolve every referenced protocol name against the models facade.

        Returns:
            The resulting ``p.Result[t.SequenceOf[type[m.BaseModel]]]``.

        """
        referenced = cls._referenced_names(root, target)
        manual = cls._manual_protocol_names(root, target)
        wanted = sorted(referenced - manual)
        if not wanted:
            return r[t.SequenceOf[type[m.BaseModel]]].ok(())
        try:
            facade = import_module(f"{target.package_name}.models")
        except ImportError as exc:
            return r[t.SequenceOf[type[m.BaseModel]]].fail(
                f"member models facade not importable: {exc}",
                exception=exc,
            )
        container = getattr(facade, f"{target.facade_container}Models", None)
        if container is None:
            return r[t.SequenceOf[type[m.BaseModel]]].fail(
                f"models facade declares no {target.facade_container}Models container",
            )
        models: list[type[m.BaseModel]] = []
        for name in wanted:
            candidate = getattr(container, name, None)
            if candidate is None:
                return r[t.SequenceOf[type[m.BaseModel]]].fail(
                    f"referenced protocol {target.protocol_ref_prefix}.{name} "
                    f"resolves to no model on {target.facade_container}Models",
                )
            models.extend(cls._model_leaves(candidate))
        return r[t.SequenceOf[type[m.BaseModel]]].ok(tuple(models))

    @classmethod
    def _model_leaves(
        cls,
        candidate: p.AttributeProbe,
    ) -> t.VariadicTuple[type[m.BaseModel]]:
        """Expand discriminated-union aliases into their leaf models.

        Returns:
            The resulting ``t.VariadicTuple[type[m.BaseModel]]``.

        """
        if isinstance(candidate, TypeAliasType):
            value = candidate.__value__
            if isinstance(value, UnionType):
                return tuple(
                    leaf
                    for leaf in get_args(value)
                    if isinstance(leaf, type) and issubclass(leaf, m.BaseModel)
                )
            candidate = value
        if isinstance(candidate, type) and issubclass(candidate, m.BaseModel):
            return (candidate,)
        return ()

    @classmethod
    def _referenced_names(
        cls,
        root: Path,
        target: FlextInfraCodegenProtocolModelAnnotations.ProtocolModelTarget,
    ) -> set[str]:
        """Scan member sources for ``<protocols_ref>.<Name>`` references.

        Returns:
            The resulting ``set[str]``.

        """
        pattern = re.compile(
            rf"\b{re.escape(target.protocol_ref_prefix)}\.([A-Z]\w*)\b",
        )
        found: set[str] = set()
        source = root / "src" / target.package_name
        for path in sorted(source.rglob("*.py")):
            if "_protocols" in path.parts:
                continue
            found.update(pattern.findall(path.read_text(encoding="utf-8")))
        return found

    @classmethod
    def _manual_protocol_names(
        cls,
        root: Path,
        target: FlextInfraCodegenProtocolModelAnnotations.ProtocolModelTarget,
    ) -> set[str]:
        """Collect protocol class names already hand-declared by the member.

        Returns:
            The resulting ``set[str]``.

        """
        pattern = re.compile(r"^class ([A-Z]\w*)\b", re.MULTILINE)
        found: set[str] = set()
        protocols = root / "src" / target.package_name / "_protocols"
        for path in sorted(protocols.glob("*.py")):
            if path.name.startswith("generated_models"):
                continue
            found.update(pattern.findall(path.read_text(encoding="utf-8")))
        return found

    @classmethod
    def _settle(
        cls,
        root: Path,
        modules: t.MappingKV[str, str],
        *,
        dry: bool,
    ) -> p.Result[t.Cli.ResultValue]:
        """Compare or write generated modules under the member protocols dir.

        Returns:
            The resulting ``p.Result[t.Cli.ResultValue]``.

        """
        changed: list[str] = []
        for relative, content in sorted(modules.items()):
            destination = root / relative
            if (
                destination.is_file()
                and destination.read_text(encoding="utf-8") == content
            ):
                continue
            changed.append(relative)
            if not dry:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(content, encoding="utf-8")
        if changed and dry:
            return r[t.Cli.ResultValue].fail(
                f"{len(changed)} generated protocol module(s) drifted: "
                f"{', '.join(changed)}",
            )
        verb = "checked" if dry else "assembled"
        cli.display_text(
            f"protocol-models: {verb} {len(modules)} module(s), {len(changed)} updated",
        )
        return r[t.Cli.ResultValue].ok(value=True)


__all__: list[str] = ["FlextInfraCodegenProtocolModels"]
