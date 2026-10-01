"""Compose inherited ast-grep rules from FLEXT distribution metadata."""

from __future__ import annotations

import re
import sys
from collections.abc import Mapping, MutableMapping, Sequence
from functools import lru_cache
from importlib.metadata import Distribution, distributions, packages_distributions
from importlib.util import find_spec
from pathlib import Path

from flext_cli import u
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from .. import c, config, m, p, r, t
from ._rope_analysis.exports import FlextInfraUtilitiesRopeAnalysisExports
from .dependencies import FlextInfraUtilitiesDependencies
from .pyproject import FlextInfraUtilitiesPyproject


class FlextInfraUtilitiesCodemodRules:
    """Resolve universal, runtime-transitive, and local ast-grep rule layers."""

    @classmethod
    @lru_cache(maxsize=1)
    def codemod_rule_plan(cls, root: Path) -> p.Result[m.Infra.CodemodRulePlan]:
        """Build the sole executable rule plan for check and mutation.

        Cached per resolved root for the lifetime of one process: the composed
        provider/rule catalog is invariant across the many ``scan()`` calls a
        single ``mod`` invocation issues while converging to a fixed point, and
        a fresh process (a new ``make mod`` run) always recomputes it from disk.
        """
        project = cls._project(root)
        if project.failure:
            return r[m.Infra.CodemodRulePlan].from_failure(project)
        root_name, direct_runtime = project.value
        indexed = cls._distributions()
        runtime_closure = cls._runtime_closure(direct_runtime, indexed)
        universal = cls._providers(
            indexed,
            scope=c.Infra.CODEMOD_SCOPE_UNIVERSAL,
            selected=frozenset(indexed).difference({root_name}),
        )
        runtime = cls._providers(
            indexed,
            scope=c.Infra.CODEMOD_SCOPE_RUNTIME,
            selected=runtime_closure.difference({root_name}),
        )
        universal_order = cls._provider_order(universal, indexed)
        if universal_order.failure:
            return r[m.Infra.CodemodRulePlan].from_failure(universal_order)
        runtime_order = cls._provider_order(runtime, indexed)
        if runtime_order.failure:
            return r[m.Infra.CodemodRulePlan].from_failure(runtime_order)
        providers: list[t.Pair[str, Path]] = []
        for name in (*universal_order.value, *runtime_order.value):
            config = universal.get(name) or runtime.get(name)
            if config is None:
                return r[m.Infra.CodemodRulePlan].fail(
                    f"codemod provider disappeared from resolved graph: {name}",
                )
            providers.append((name, config))
        local_config = root / c.Infra.CODEMOD_CONFIG_RELPATH
        if local_config.is_file():
            providers.append((f"{root_name}:local", local_config))
        return cls._compose(tuple(providers), root_name, runtime_closure)

    @staticmethod
    def codemod_rule_filter(rule_ids: t.StrSequence) -> str:
        """Return one exact ast-grep rule-ID filter for an elected ruleset."""
        if not rule_ids:
            msg = "codemod rule filter requires at least one rule ID"
            raise ValueError(msg)
        return "^(?:" + "|".join(re.escape(rule_id) for rule_id in rule_ids) + ")$"

    @staticmethod
    def _project(root: Path) -> p.Result[t.Pair[str, t.StrSequence]]:
        pyproject = root / c.PYPROJECT_FILENAME
        document = u.Cli.toml_read_document(pyproject)
        if document.failure:
            return r[t.Pair[str, t.StrSequence]].from_failure(document)
        payload = u.Cli.toml_as_mapping(document.value)
        project = payload.get(c.Infra.PROJECT) if payload else None
        if not isinstance(project, Mapping):
            return r[t.Pair[str, t.StrSequence]].fail(
                f"missing [project] table: {pyproject}",
            )
        raw_name = project.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            return r[t.Pair[str, t.StrSequence]].fail(
                f"missing project.name: {pyproject}",
            )
        raw_dependencies = project.get(c.Infra.DEPENDENCIES)
        if not isinstance(raw_dependencies, Sequence) or isinstance(
            raw_dependencies,
            str,
        ):
            return r[t.Pair[str, t.StrSequence]].fail(
                f"project.dependencies must be a sequence: {pyproject}",
            )
        dependencies: set[str] = set()
        for raw in raw_dependencies:
            if not isinstance(raw, str):
                return r[t.Pair[str, t.StrSequence]].fail(
                    f"project dependency must be a string: {pyproject}",
                )
            requirement = Requirement(raw)
            if requirement.marker is None or requirement.marker.evaluate():
                dependencies.add(canonicalize_name(requirement.name))
        return r[t.Pair[str, t.StrSequence]].ok((
            canonicalize_name(raw_name),
            tuple(sorted(dependencies)),
        ))

    @staticmethod
    def _distributions() -> MutableMapping[str, Distribution]:
        indexed: MutableMapping[str, Distribution] = {}
        # Import search paths may repeat the same physical directory. Query each
        # directory once; distinct installations with the same name still fail.
        paths = list(dict.fromkeys(str(Path(path).resolve()) for path in sys.path))
        for installed in distributions(path=paths):
            raw_name = installed.metadata.get("Name")
            if not isinstance(raw_name, str) or not raw_name.strip():
                continue
            name = canonicalize_name(raw_name)
            if name in indexed:
                msg = f"duplicate installed distribution metadata: {name}"
                raise ValueError(msg)
            indexed[name] = installed
        return indexed

    @classmethod
    def _runtime_closure(
        cls,
        direct: t.StrSequence,
        indexed: t.MappingKV[str, Distribution],
    ) -> frozenset[str]:
        pending = list(direct)
        resolved: set[str] = set()
        while pending:
            name = pending.pop()
            if name in resolved:
                continue
            installed = indexed.get(name)
            if installed is None:
                msg = f"required runtime distribution is not installed: {name}"
                raise ValueError(msg)
            resolved.add(name)
            pending.extend(cls._requirements(installed))
        return frozenset(resolved)

    @staticmethod
    def _requirements(installed: Distribution) -> t.StrSequence:
        requirements: set[str] = set()
        for raw in installed.requires or ():
            requirement = Requirement(raw)
            if requirement.marker is None or requirement.marker.evaluate():
                requirements.add(canonicalize_name(requirement.name))
        return tuple(sorted(requirements))

    @classmethod
    def _providers(
        cls,
        indexed: t.MappingKV[str, Distribution],
        *,
        scope: str,
        selected: frozenset[str],
    ) -> MutableMapping[str, Path]:
        providers: MutableMapping[str, Path] = {}
        for name in sorted(selected):
            installed = indexed.get(name)
            if installed is None:
                continue
            configs = cls._provider_configs(installed)
            if configs.failure:
                raise ValueError(configs.error or f"resolve codemod provider: {name}")
            if not configs.value:
                continue
            config = configs.value[0]
            declared_scope = cls._config_scope(config)
            if declared_scope.failure:
                raise ValueError(
                    declared_scope.error or f"resolve codemod scope: {config}",
                )
            if declared_scope.value == scope:
                providers[name] = config
        return providers

    @classmethod
    def _provider_order(
        cls,
        providers: t.MappingKV[str, Path],
        indexed: t.MappingKV[str, Distribution],
    ) -> p.Result[t.StrSequence]:
        selected = frozenset(providers)
        edges = {
            name: tuple(
                dependency
                for dependency in cls._requirements(indexed[name])
                if dependency in selected
            )
            for name in selected
        }
        try:
            ordered = FlextInfraUtilitiesDependencies.dependency_order(
                tuple(selected),
                dependencies=lambda name: edges.get(name, ()),
            )
        except ValueError as exc:
            return r[t.StrSequence].fail(
                f"codemod provider cycle: {exc}",
                exception=exc,
            )
        return r[t.StrSequence].ok(ordered)

    @staticmethod
    def _provider_configs(installed: Distribution) -> p.Result[t.SequenceOf[Path]]:
        raw_name = installed.metadata.get("Name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            return r[t.SequenceOf[Path]].fail(
                "codemod provider distribution has no canonical name",
            )
        package_name = canonicalize_name(raw_name).replace("-", "_")
        if not package_name.isidentifier():
            return r[t.SequenceOf[Path]].ok(())
        spec = find_spec(package_name)
        if spec is None:
            return r[t.SequenceOf[Path]].ok(())
        roots = tuple(Path(path) for path in spec.submodule_search_locations or ())
        if not roots and spec.origin is not None:
            roots = (Path(spec.origin).parent,)
        # A distribution's rule root is its config directory: the packaged
        # copy (<pkg>/config) of an installed wheel, or the config directory
        # beside src/ of an editable checkout (<root>/src/<pkg> -> <root>).
        configs = {
            base / c.Infra.CODEMOD_CONFIG_RELPATH
            for root in roots
            for base in (root, root.parents[1])
            if (base / c.Infra.CODEMOD_CONFIG_RELPATH).is_file()
        }
        if len(configs) > 1:
            return r[t.SequenceOf[Path]].fail(
                f"distribution exports multiple codemod configs: {raw_name}",
            )
        return r[t.SequenceOf[Path]].ok(tuple(sorted(configs)))

    @staticmethod
    def _config_scope(config: Path) -> p.Result[str]:
        parsed = u.Cli.yaml_parse(config.read_text(encoding=c.Cli.ENCODING_DEFAULT))
        if parsed.failure:
            return r[str].from_failure(parsed)
        scope = parsed.value.get(c.Infra.CODEMOD_SCOPE_KEY)
        if not isinstance(scope, str) or scope not in {
            c.Infra.CODEMOD_SCOPE_UNIVERSAL,
            c.Infra.CODEMOD_SCOPE_RUNTIME,
        }:
            return r[str].fail(f"codemod config has invalid scope: {config}")
        return r[str].ok(scope)

    @classmethod
    def _compose(
        cls,
        providers: t.SequenceOf[t.Pair[str, Path]],
        root_name: str,
        runtime_closure: frozenset[str],
    ) -> p.Result[m.Infra.CodemodRulePlan]:
        """Elect every provider rule once, honouring each rule's declared scope.

        A rule that bans a library outside its owning project declares the
        owner's distribution under ``metadata.owner``: the owner's own plan
        never elects it, every other project's plan does. A rule that binds
        only the consumers of a facade declares that distribution under
        ``metadata.consumers_of``: a plan elects it only when the facade is in
        the project's runtime closure, so the facade itself and the projects
        below it never do.
        """
        selected: MutableMapping[str, m.Infra.CodemodRule] = {}
        rulesets: list[m.Infra.CodemodRuleset] = []
        provider_order: list[str] = []
        for provider, provider_config in providers:
            if provider in provider_order:
                return r[m.Infra.CodemodRulePlan].fail(
                    f"codemod provider declared more than once: {provider}",
                )
            provider_order.append(provider)
            parsed = cls._rules(provider, provider_config)
            if parsed.failure:
                return r[m.Infra.CodemodRulePlan].from_failure(parsed)
            elected: list[str] = []
            fixable: list[str] = []
            for rule in parsed.value:
                if rule.owner is not None and canonicalize_name(rule.owner) == root_name:
                    continue
                if (
                    rule.consumers_of is not None
                    and canonicalize_name(rule.consumers_of) not in runtime_closure
                ):
                    continue
                previous = selected.get(rule.id)
                if previous is not None:
                    if previous.provider == provider:
                        return r[m.Infra.CodemodRulePlan].fail(
                            f"duplicate codemod rule id in {provider}: {rule.id}",
                        )
                    if previous.digest != rule.digest:
                        return r[m.Infra.CodemodRulePlan].fail(
                            "conflicting codemod rule id "
                            f"{rule.id}: {previous.provider}:{previous.resource} "
                            f"({previous.digest}) != {rule.provider}:{rule.resource} "
                            f"({rule.digest})",
                        )
                    continue
                selected[rule.id] = rule
                elected.append(rule.id)
                if rule.fixable:
                    fixable.append(rule.id)
            if elected:
                rulesets.append(
                    m.Infra.CodemodRuleset(
                        provider=provider,
                        config=provider_config,
                        rule_ids=tuple(elected),
                        fixable_rule_ids=tuple(fixable),
                    ),
                )
        if not selected:
            return r[m.Infra.CodemodRulePlan].fail("no ast-grep rules discovered")
        return r[m.Infra.CodemodRulePlan].ok(
            m.Infra.CodemodRulePlan(
                provider_order=tuple(provider_order),
                rules=tuple(selected.values()),
                rulesets=tuple(rulesets),
            ),
        )

    @classmethod
    def _rules(
        cls,
        provider: str,
        config: Path,
    ) -> p.Result[t.SequenceOf[m.Infra.CodemodRule]]:
        parsed_config = u.Cli.yaml_parse(
            config.read_text(encoding=c.Cli.ENCODING_DEFAULT),
        )
        if parsed_config.failure:
            return r[t.SequenceOf[m.Infra.CodemodRule]].from_failure(parsed_config)
        raw_dirs = parsed_config.value.get(c.Infra.CODEMOD_RULE_DIRS_KEY)
        if not isinstance(raw_dirs, Sequence) or isinstance(raw_dirs, str):
            return r[t.SequenceOf[m.Infra.CodemodRule]].fail(
                f"codemod config ruleDirs must be a sequence: {config}",
            )
        rules: list[m.Infra.CodemodRule] = []
        config_root = config.parent.resolve()
        for raw_dir in raw_dirs:
            if not isinstance(raw_dir, str) or not raw_dir.strip():
                return r[t.SequenceOf[m.Infra.CodemodRule]].fail(
                    f"codemod config has invalid ruleDirs entry: {config}",
                )
            rule_dir = (config_root / raw_dir).resolve()
            if not rule_dir.is_relative_to(config_root):
                return r[t.SequenceOf[m.Infra.CodemodRule]].fail(
                    f"codemod ruleDirs escapes provider root: {rule_dir}",
                )
            if not rule_dir.is_dir():
                return r[t.SequenceOf[m.Infra.CodemodRule]].fail(
                    f"codemod ruleDirs entry is missing: {rule_dir}",
                )
            for resource in sorted(rule_dir.rglob("*.yml")):
                relative = resource.relative_to(rule_dir)
                if any(part.startswith("_") for part in relative.parts):
                    continue
                documents = c.Infra.CODEMOD_DOCUMENT_SEPARATOR_RE.split(
                    resource.read_text(encoding=c.Cli.ENCODING_DEFAULT),
                )
                for raw_document in documents:
                    if not any(
                        line.strip() and not line.lstrip().startswith("#")
                        for line in raw_document.splitlines()
                    ):
                        continue
                    parsed_rule = u.Cli.yaml_parse(raw_document)
                    if parsed_rule.failure:
                        return r[t.SequenceOf[m.Infra.CodemodRule]].from_failure(
                            parsed_rule,
                        )
                    rule_id = parsed_rule.value.get("id")
                    if not isinstance(rule_id, str) or not rule_id.strip():
                        return r[t.SequenceOf[m.Infra.CodemodRule]].fail(
                            f"ast-grep rule document missing id: {resource}",
                        )
                    canonical = u.Cli.json_dumps(
                        dict(parsed_rule.value),
                        sort_keys=True,
                    )
                    if canonical.failure:
                        return r[t.SequenceOf[m.Infra.CodemodRule]].from_failure(
                            canonical,
                        )
                    declared = cls._declared_expected(parsed_rule.value)
                    if declared.failure:
                        return r[t.SequenceOf[m.Infra.CodemodRule]].fail(
                            f"{declared.error}: {resource}",
                        )
                    metadata = parsed_rule.value.get(c.Infra.CODEMOD_RULE_METADATA_KEY)
                    declared_metadata: t.JsonMapping = (
                        metadata if isinstance(metadata, Mapping) else {}
                    )
                    context = cls._declared_context(
                        declared_metadata.get(c.Infra.CODEMOD_RULE_CONTEXT_KEY)
                    )
                    if context.failure:
                        return r[t.SequenceOf[m.Infra.CodemodRule]].fail(
                            f"{context.error}: {resource}"
                        )
                    rules.append(
                        m.Infra.CodemodRule.model_validate({
                            "id": rule_id,
                            "digest": u.Cli.sha256_content(canonical.value),
                            "provider": provider,
                            "resource": resource,
                            "fixable": "fix" in parsed_rule.value,
                            "expected": declared.value[0] if declared.value else None,
                            "owner": declared_metadata.get(
                                c.Infra.CODEMOD_RULE_OWNER_KEY
                            ),
                            "consumers_of": declared_metadata.get(
                                c.Infra.CODEMOD_RULE_CONSUMERS_OF_KEY
                            ),
                            "relocation": declared_metadata.get(
                                c.Infra.CODEMOD_RULE_RELOCATION_KEY
                            ),
                            "context": context.value,
                        })
                    )
        return r[t.SequenceOf[m.Infra.CodemodRule]].ok(tuple(rules))

    @staticmethod
    def _declared_context(
        raw: t.JsonValue | None,
    ) -> p.Result[t.VariadicTuple[m.Infra.CodemodContextCondition]]:
        """Read ``metadata.context``: ``{VAR: {is|not: predicate}}``.

        Each entry binds one captured single metavariable to one project
        predicate that must hold (``is``) or fail (``not``). Absence is the
        empty tuple; any other shape is a malformed rule document.
        """
        conditions = r[t.VariadicTuple[m.Infra.CodemodContextCondition]]
        if raw is None:
            return conditions.ok(())
        if not isinstance(raw, Mapping) or not raw:
            return conditions.fail(
                "ast-grep rule metadata.context must be a non-empty mapping"
            )
        parsed: list[m.Infra.CodemodContextCondition] = []
        for variable, condition in raw.items():
            if not isinstance(condition, Mapping) or len(condition) != 1:
                return conditions.fail(
                    f"ast-grep rule context ${variable} must hold exactly one of "
                    f"{c.Infra.CODEMOD_CONTEXT_HOLDS_KEY!r} or "
                    f"{c.Infra.CODEMOD_CONTEXT_FAILS_KEY!r}"
                )
            ((key, predicate),) = condition.items()
            if key not in {
                c.Infra.CODEMOD_CONTEXT_HOLDS_KEY,
                c.Infra.CODEMOD_CONTEXT_FAILS_KEY,
            }:
                return conditions.fail(
                    f"ast-grep rule context ${variable} has unknown key {key!r}"
                )
            parsed.append(
                m.Infra.CodemodContextCondition.model_validate({
                    "variable": variable,
                    "predicate": predicate,
                    "holds": key == c.Infra.CODEMOD_CONTEXT_HOLDS_KEY,
                })
            )
        return conditions.ok(tuple(parsed))

    @classmethod
    def codemod_context_admits(
        cls,
        root: Path,
        rule: m.Infra.CodemodRule,
        file_path: Path,
        captures: t.JsonMapping,
    ) -> bool:
        """Return whether one finding satisfies its rule's project context.

        ``captures`` is ast-grep's ``metaVariables.single`` payload of the
        finding. A declared variable the finding did not capture is a rule
        defect and raises; the syntactic match alone never stands in for it.
        """
        for condition in rule.context:
            capture = captures.get(condition.variable)
            text = capture.get("text") if isinstance(capture, Mapping) else None
            if not isinstance(text, str) or not text.strip():
                msg = (
                    f"{rule.id}: context variable ${condition.variable} was not "
                    f"captured in {file_path}"
                )
                raise ValueError(msg)
            source = file_path if file_path.is_absolute() else root / file_path
            holds = cls._context_holds(
                root.resolve(), condition.predicate, text.strip(), source.resolve()
            )
            if holds is not condition.holds:
                return False
        return True

    @classmethod
    def _context_holds(
        cls,
        root: Path,
        predicate: c.Infra.CodemodContextPredicate,
        value: str,
        file_path: Path,
    ) -> bool:
        """Evaluate one predicate against the project SSOT it names."""
        module = value.split(maxsplit=1)[0].split(".", maxsplit=1)[0]
        match predicate:
            case c.Infra.CodemodContextPredicate.STDLIB_MODULE:
                return module in sys.stdlib_module_names
            case c.Infra.CodemodContextPredicate.OWN_PACKAGE:
                return module == FlextInfraUtilitiesPyproject.project_package_name(
                    root
                )
            case c.Infra.CodemodContextPredicate.RUNTIME_PACKAGE:
                return module in cls._runtime_modules(root)
            case c.Infra.CodemodContextPredicate.FILE_FAMILY:
                return value in cls._file_families(file_path)

    @classmethod
    @lru_cache(maxsize=8)
    def _runtime_modules(cls, root: Path) -> frozenset[str]:
        """Top-level import names provided by the project's runtime closure."""
        project = cls._project(root).unwrap()
        closure = cls._runtime_closure(project[1], cls._distributions())
        return frozenset(
            module
            for module, providers in packages_distributions().items()
            if any(canonicalize_name(name) in closure for name in providers)
        )

    @staticmethod
    def _file_families(file_path: Path) -> frozenset[str]:
        """Facade letters the module itself declares in its ``__all__``.

        Letter ownership is the module's own declaration, never its file
        name; the letter vocabulary is the tooling import-layer order.
        """
        declared = FlextInfraUtilitiesRopeAnalysisExports.public_export_names_source(
            file_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
        )
        return frozenset(config.Infra.tooling.lazy_init.import_layer_order).intersection(
            declared
        )

    @staticmethod
    def _declared_expected(
        document: t.MappingKV[str, t.JsonValue],
    ) -> p.Result[t.VariadicTuple[int]]:
        """Read one rule's declared finding-count receipt from its metadata.

        The receipt is the same contract the sed-by-list phase already owns
        (``ModTextRule.expected``): a rule that declares how many findings it
        must produce turns a silent drift — a guard that stopped matching, a
        pattern that started over-matching — into a loud failure. ast-grep
        rejects unknown top-level keys, so the declaration lives under the
        ``metadata`` mapping it does accept. Absence is the empty tuple: a
        declared `expected: 0` is a real receipt ("this rule must never match
        again") and must not collapse into "no receipt declared".
        """
        metadata = document.get(c.Infra.CODEMOD_RULE_METADATA_KEY)
        if metadata is None:
            return r[t.VariadicTuple[int]].ok(())
        if not isinstance(metadata, Mapping):
            return r[t.VariadicTuple[int]].fail(
                "ast-grep rule metadata must be a mapping",
            )
        expected = metadata.get(c.Infra.CODEMOD_TEXT_KEY_EXPECTED)
        if expected is None:
            return r[t.VariadicTuple[int]].ok(())
        if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
            return r[t.VariadicTuple[int]].fail(
                "ast-grep rule expected receipt must be a non-negative integer",
            )
        return r[t.VariadicTuple[int]].ok((expected,))


__all__: list[str] = ["FlextInfraUtilitiesCodemodRules"]
