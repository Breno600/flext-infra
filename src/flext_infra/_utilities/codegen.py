"""Codegen utilities composition for the infrastructure namespace."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from flext_cli import u

from flext_core import r
from flext_infra import c, config, m, p, t

from .codegen_facades import FlextInfraUtilitiesCodegenFacades
from .codegen_file_plan import FlextInfraUtilitiesCodegenFilePlan
from .gitignore import FlextInfraUtilitiesGitignore


class FlextInfraUtilitiesCodegen(
    FlextInfraUtilitiesCodegenFacades,
    FlextInfraUtilitiesCodegenFilePlan,
    FlextInfraUtilitiesGitignore,
):
    """Compose all codegen utility concerns for ``u.Infra``."""

    if TYPE_CHECKING:

        @staticmethod
        def project_root(file_path: Path) -> Path | None: ...

    @staticmethod
    def mise_bootstrap_environment() -> m.Infra.MiseBootstrapEnvironmentSpec:
        """Return the single typed isolation contract used by setup and codegen."""
        return m.Infra.MiseBootstrapEnvironmentSpec(
            storage_root_variable=c.Infra.MISE_BOOTSTRAP_STORAGE_ROOT_VARIABLE,
            fixed_environment=(
                *c.Infra.MISE_BOOTSTRAP_FIXED_ENVIRONMENT,
                # Safe mode ignores project settings; project platform policy
                # enters the isolated runtime explicitly from the same owner.
                (
                    "MISE_LOCKFILE_PLATFORMS",
                    ",".join(config.Infra.codegen.toolchain.mise_lockfile_platforms),
                ),
            ),
            transient_environment=tuple(c.Infra.MISE_BOOTSTRAP_TRANSIENT_ENVIRONMENT),
            persistent_environment=tuple(c.Infra.MISE_BOOTSTRAP_PERSISTENT_ENVIRONMENT),
            empty_files=tuple(c.Infra.MISE_BOOTSTRAP_EMPTY_FILES),
            passthrough_environment=tuple(
                c.Infra.MISE_BOOTSTRAP_PASSTHROUGH_ENVIRONMENT
            ),
            version_pin_file=c.Infra.MISE_VERSION_PIN_FILENAME,
        )

    @staticmethod
    def envrc_render_spec() -> m.Infra.EnvrcRenderSpec:
        """Return the sole typed context every generated ``.envrc`` renders from."""
        toolchain = config.Infra.codegen.toolchain
        return m.Infra.EnvrcRenderSpec(
            state_directory_name=toolchain.state_directory_name,
            scratch_namespace=toolchain.scratch_namespace,
            scratch_home_relative=toolchain.scratch_home_relative,
            pycache_namespace=toolchain.pycache_namespace,
            environment_path_prepends=toolchain.environment_path_prepends,
            mise_bootstrap=FlextInfraUtilitiesCodegen.mise_bootstrap_environment(),
        )

    @staticmethod
    def prepare_mise_runtime_storage(
        project_root: Path,
        environment: t.StrMapping,
        contract: m.Infra.MiseBootstrapEnvironmentSpec,
    ) -> p.Result[Path]:
        """Resolve and create one persistent Mise storage outside the checkout."""
        configured = environment.get(contract.storage_root_variable, "").strip()
        xdg_data_home = environment.get("XDG_DATA_HOME", "").strip()
        caller_home = environment.get("HOME", "").strip()
        if configured:
            raw_root = configured
        elif xdg_data_home:
            raw_root = str(Path(xdg_data_home) / "mise")
        elif caller_home:
            raw_root = str(Path(caller_home) / ".local" / "share" / "mise")
        else:
            return r[Path].fail(
                f"{contract.storage_root_variable}, XDG_DATA_HOME, or HOME must "
                "identify persistent Mise storage"
            )
        normalized = os.path.normpath(raw_root)
        if raw_root != normalized:
            return r[Path].fail(f"Mise storage path must be normalized: {raw_root}")
        storage_root = Path(normalized)
        if not storage_root.is_absolute():
            return r[Path].fail(f"Mise storage path must be absolute: {storage_root}")
        physical_project = project_root.resolve(strict=True)
        physical_tmp = Path(tempfile.gettempdir()).resolve(strict=True)
        # Containment is decided before the temp-root rule: a checkout may itself
        # sit under the temporary root, and reporting `/tmp` there names the
        # sandbox instead of the actual defect, which is the storage living
        # inside the checkout it is supposed to outlive.
        if storage_root == physical_project or storage_root.is_relative_to(
            physical_project
        ):
            return r[Path].fail(
                f"persistent Mise storage must be outside the checkout: {storage_root}"
            )
        if storage_root == physical_tmp or storage_root.is_relative_to(physical_tmp):
            return r[Path].fail(
                f"persistent Mise storage must not live under /tmp: {storage_root}"
            )
        if physical_project.is_relative_to(storage_root):
            return r[Path].fail(
                f"persistent Mise storage must not contain the checkout: {storage_root}"
            )
        if storage_root.is_symlink():
            return r[Path].fail(
                f"Mise storage path must not be a symlink: {storage_root}"
            )
        created_root = FlextInfraUtilitiesCodegen._create_mise_storage_directory(
            storage_root
        )
        if created_root.failure:
            return r[Path].from_failure(created_root)
        physical_root = storage_root.resolve(strict=True)
        if physical_root == physical_tmp or physical_root.is_relative_to(physical_tmp):
            return r[Path].fail(
                f"persistent Mise storage must not live under /tmp: {physical_root}"
            )
        if physical_root == physical_project or physical_root.is_relative_to(
            physical_project
        ):
            return r[Path].fail(
                f"persistent Mise storage must not contain the checkout: {physical_root}"
            )
        if physical_project.is_relative_to(physical_root):
            return r[Path].fail(
                f"persistent Mise storage must not contain the checkout: {physical_root}"
            )
        relative_directories = {
            relative
            for _name, relative in contract.persistent_environment
            if relative != "."
        }
        relative_directories.add("bootstrap")
        for relative in sorted(relative_directories):
            directory = physical_root / relative
            if directory.is_symlink():
                return r[Path].fail(
                    f"persistent Mise path must not be a symlink: {directory}"
                )
            created = FlextInfraUtilitiesCodegen._create_mise_storage_directory(
                directory
            )
            if created.failure:
                return r[Path].from_failure(created)
            physical_directory = directory.resolve(strict=True)
            if not physical_directory.is_relative_to(physical_root):
                return r[Path].fail(
                    f"persistent Mise path escaped storage: {physical_directory}"
                )
        return r[Path].ok(physical_root)

    @staticmethod
    def mise_runtime_install_path(storage_root: Path, release: str) -> p.Result[Path]:
        """Return the immutable persistent binary path for one exact release."""
        components = release.split(".")
        if len(components) != c.Infra.MISE_RELEASE_COMPONENT_COUNT or not all(
            component.isdecimal() for component in components
        ):
            return r[Path].fail(f"invalid Mise runtime release: {release}")
        suffix = ".exe" if os.name == "nt" else ""
        return r[Path].ok(storage_root / "bootstrap" / f"mise-{release}{suffix}")

    @staticmethod
    def _create_mise_storage_directory(path: Path) -> p.Result[bool]:
        """Create one persistent directory through the atomic filesystem owner."""
        if path.exists():
            if not path.is_dir():
                return r[bool].fail(f"persistent Mise path is not a directory: {path}")
            return r[bool].ok(True)
        planned = u.Cli.atomic_plan_directory_chain(path)
        if planned.failure:
            return r[bool].from_failure(planned)
        created = u.Cli.atomic_create_directory_chain_guarded(
            planned.value, permission_mode=0o700
        )
        if created.failure:
            return r[bool].from_failure(created)
        return r[bool].ok(True)

    @staticmethod
    def generate_module_skeleton(
        *, class_name: str, base_class: str, base_module: str, docstring: str
    ) -> str:
        """Render one module skeleton through the cli template engine (ADR-005).

        The body lives in ``templates/module_skeleton.py.j2``; this method only
        builds the context (explicit base module) and renders fail-closed via
        ``u.Cli.template_render``. A render failure is a real incident and
        surfaces via ``unwrap`` (no silent fallback).
        """
        template_path = (
            Path(__file__).resolve().parent.parent
            / "templates"
            / c.Infra.TEMPLATE_MODULE_SKELETON
        )
        # NOTE (multi-agent, flext-wkii.17 / agent: uv_overlay_owner): preserve
        # the exact validated model identity across the template boundary.
        context = m.Infra.ModuleSkeletonRenderContext(
            class_name=class_name,
            base_class=base_class,
            base_module=base_module,
            docstring=docstring,
        )
        rendered: p.Result[str] = u.Cli.template_render(template_path, context)
        content: str = rendered.unwrap()
        return content

    @staticmethod
    def generate_test_module_skeleton(
        *,
        class_name: str,
        base_class: str,
        project_module: str,
        alias: str,
        namespace: str,
        project_namespace: str,
        docstring: str,
    ) -> str:
        """Render one canonical test facade skeleton."""
        template_path = (
            Path(__file__).resolve().parent.parent
            / "templates"
            / c.Infra.TEMPLATE_TEST_MODULE_SKELETON
        )
        context = m.Infra.TestModuleSkeletonRenderContext(
            class_name=class_name,
            base_class=base_class,
            project_module=project_module,
            alias=alias,
            namespace=namespace,
            project_namespace=project_namespace,
            docstring=docstring,
        )
        rendered: p.Result[str] = u.Cli.template_render(template_path, context)
        return rendered.unwrap()

    @staticmethod
    def dir_has_py_files(pkg_dir: Path) -> bool:
        """Return whether a package directory contains canonical Python files."""
        if not pkg_dir.is_dir():
            return False
        return any(
            child.is_file() and child.suffix == ".py" for child in pkg_dir.iterdir()
        )

    @staticmethod
    def parse_final_constant_definitions(
        source_lines: t.SequenceOf[str],
    ) -> t.SequenceOf[tuple[str, str, str, str, int]]:
        """Parse ``NAME: Final[...] = VALUE`` definitions with class-path context."""
        class_stack: t.MutableSequenceOf[t.Pair[str, int]] = []
        parsed: t.MutableSequenceOf[tuple[str, str, str, str, int]] = []
        for line_number, line in enumerate(source_lines, 1):
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            FlextInfraUtilitiesCodegen.update_class_stack(class_stack, stripped, indent)
            match = c.Infra.DETECTION_FINAL_DECL_RE.match(line)
            if match is None:
                continue
            parsed.append((
                match.group("name"),
                match.group("ann"),
                match.group("value").strip(),
                ".".join(name for name, _ in class_stack),
                line_number,
            ))
        return tuple(parsed)

    @staticmethod
    def update_class_stack(
        class_stack: t.MutableSequenceOf[tuple[str, int]],
        stripped_line: str,
        indent: int,
    ) -> None:
        """Keep class-path stack in sync while iterating constant source lines."""
        class_match = (
            c.Infra.DETECTION_CLASS_DECL_RE.match(stripped_line)
            if stripped_line.startswith("class ") and stripped_line.endswith(":")
            else None
        )
        if class_match is not None:
            while class_stack and class_stack[-1][1] >= indent:
                class_stack.pop()
            class_stack.append((class_match.group(1), indent))
            return
        while class_stack and indent <= class_stack[-1][1]:
            class_stack.pop()


__all__: list[str] = ["FlextInfraUtilitiesCodegen"]
