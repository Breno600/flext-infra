"""Static contracts enforced on every managed direnv environment file.

The lint is pure (no subprocess): gates run it before the runtime smoke so
contract defects fail with precise messages, and the workspace sync runs it
after every generated write so a regression can never land silently.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from flext_infra import c, m, t, u


class FlextInfraWorkspaceEnvironmentContracts:
    """Static contract lint for one managed direnv environment file."""

    _UNGUARDED_DIRENV_DIR: Final[re.Pattern[str]] = re.compile(
        r"\$\{?DIRENV_DIR(?![\s]*[:\-])",
    )
    _QUOTED_ENV_TARGET: Final[re.Pattern[str]] = re.compile(
        r'^(?:source_env|watch_file)\s+"([^"]+)"\s*$',
    )
    _HOME_PREFIX: Final[re.Pattern[str]] = re.compile(r"^\$\{?HOME\}?(.*)$")

    _MANAGED_SECTION_START: Final[re.Pattern[str]] = re.compile(
        r"^# === SECTION: .* \(managed\) ===$",
    )
    _MANAGED_SECTION_END: Final[re.Pattern[str]] = re.compile(r"^# End SECTION: .*$")
    _ENVRC_LOCAL_GENERATED_MARKERS: Final[t.StrSequence] = (
        *c.Infra.WORKSPACE_ENV_GENERATED_MARKERS,
        *c.Infra.TEMPLATE_GENERATED_MARKERS,
    )
    # Local overrides carry operator customization only. Beads activation is a
    # generated property of `.envrc`; any residue here is a second activation
    # owner whose drift already diverged (historical jq conditions differed).
    _ENVRC_LOCAL_FORBIDDEN_VARS: Final[t.StrSequence] = (
        c.Infra.ENVRC_LOCAL_FORBIDDEN_VARS
    )

    @classmethod
    def _resolve_env_target(
        cls,
        raw: str,
        root: Path,
        *,
        resolve_home: bool,
    ) -> Path | None:
        """Resolve one quoted target to a concrete path, or None when dynamic.

        A ``${HOME}``/``~`` target describes machine state: it is skipped at
        generation time and, when resolved at check time, the REAL home is
        substituted for the prefix — stripping the prefix without substituting
        would probe a bogus absolute path (``/.config/...``) that never exists.
        """
        home_match = cls._HOME_PREFIX.match(raw)
        candidate = home_match.group(1) if home_match is not None else raw
        if candidate.startswith("~"):
            candidate = f"${{HOME}}{candidate[1:]}"
            home_match = cls._HOME_PREFIX.match(candidate)
            candidate = home_match.group(1) if home_match is not None else candidate
        if "$" in candidate:
            return None
        if home_match is not None:
            if not resolve_home:
                return None
            # A ${HOME} target describes machine state, so it probes the real
            # account home (``u.Infra.real_account_home``), never the ambient
            # HOME: check pipelines run under redirected homes where the
            # referenced files legitimately live only in the real account.
            return u.Infra.real_account_home() / candidate.lstrip("/")
        resolved = Path(candidate)
        if not resolved.is_absolute():
            resolved = root / resolved
        return resolved

    @classmethod
    def envrc_contract_violations(
        cls,
        content: str,
        *,
        root: Path,
        resolve_home: bool = True,
    ) -> t.VariadicTuple[m.Infra.EnvironmentContractViolation]:
        """Return one typed violation per direnv contract issue in ``content``.

        Contracts enforced:
        - ``DIRENV_DIR`` is never read unguarded: ``strict_env`` does not export
          it, so any ``${DIRENV_DIR}`` / ``${DIRENV_DIR#...}`` / ``$DIRENV_DIR``
          read breaks activation with an unbound-variable error. Guarded reads
          (``${DIRENV_DIR:-...}`` / ``${DIRENV_DIR-}``) stay legal.
        - Every literal ``source_env`` / ``watch_file`` target must exist. Targets
          derived from runtime variables (any remaining ``$``) are skipped. With
          ``resolve_home=False`` (generation-time lint) ``${HOME}`` targets are also
          skipped because they describe machine state, not repository state.
        """
        violations: list[m.Infra.EnvironmentContractViolation] = []
        for match in cls._UNGUARDED_DIRENV_DIR.finditer(content):
            line = content.count("\n", 0, match.start()) + 1
            violations.append(
                m.Infra.EnvironmentContractViolation(
                    line=line,
                    message=(
                        "DIRENV_DIR read without a `:-` guard "
                        f"(strict_env does not export it): {match.group(0)!r}"
                    ),
                    token=match.group(0),
                ),
            )
        for line_number, line in enumerate(content.splitlines(), start=1):
            target_match = cls._QUOTED_ENV_TARGET.match(line.strip())
            if target_match is None:
                continue
            resolved = cls._resolve_env_target(
                target_match.group(1),
                root,
                resolve_home=resolve_home,
            )
            if resolved is None:
                continue
            if not resolved.exists():
                violations.append(
                    m.Infra.EnvironmentContractViolation(
                        line=line_number,
                        message=f"environment target does not exist: {resolved}",
                        token=str(resolved),
                    ),
                )
        return tuple(violations)

    @classmethod
    def envrc_local_normalized(cls, content: str) -> str:
        """Strip generated residue from one ``.envrc.local`` body.

        Removes historical managed sections (from a ``# === SECTION: ...
        (managed) ===`` opener through its ``# End SECTION:`` closer,
        unterminated sections included) and generated ownership marker
        lines. Custom operator content is preserved verbatim; an empty
        remainder means the file must not exist.
        """
        kept: list[str] = []
        skipping = False
        for line in content.splitlines():
            stripped = line.strip()
            if skipping:
                if cls._MANAGED_SECTION_END.match(stripped):
                    skipping = False
                continue
            if cls._MANAGED_SECTION_START.match(stripped):
                skipping = True
                continue
            if stripped and any(
                stripped.startswith(marker)
                for marker in cls._ENVRC_LOCAL_GENERATED_MARKERS
            ):
                continue
            kept.append(line)
        normalized = "\n".join(kept).strip("\n")
        return f"{normalized}\n" if normalized else ""

    @classmethod
    def envrc_local_contract_violations(
        cls,
        content: str,
    ) -> t.VariadicTuple[m.Infra.EnvironmentContractViolation]:
        """Return one typed violation per activation residue in ``.envrc.local``.

        Local overrides never activate Beads: managed section markers,
        generated ownership markers, and inherited orchestration or Beads
        endpoint variables are all residue of a second activation owner.
        """
        violations: list[m.Infra.EnvironmentContractViolation] = []
        for line_number, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            if cls._MANAGED_SECTION_START.match(
                stripped,
            ) or cls._MANAGED_SECTION_END.match(stripped):
                violations.append(
                    m.Infra.EnvironmentContractViolation(
                        line=line_number,
                        message=(
                            f"managed section marker in local overrides: {stripped!r}"
                        ),
                        token=stripped,
                    ),
                )
                continue
            if any(
                stripped.startswith(marker)
                for marker in cls._ENVRC_LOCAL_GENERATED_MARKERS
            ):
                violations.append(
                    m.Infra.EnvironmentContractViolation(
                        line=line_number,
                        message=(
                            "generated ownership marker in local overrides: "
                            f"{stripped!r}"
                        ),
                        token=stripped,
                    ),
                )
                continue
            for token in cls._ENVRC_LOCAL_FORBIDDEN_VARS:
                if token in stripped:
                    violations.append(
                        m.Infra.EnvironmentContractViolation(
                            line=line_number,
                            message=(
                                f"Beads activation variable in local overrides: {token}"
                            ),
                            token=token,
                        ),
                    )
                    break
        return tuple(violations)


__all__: t.VariadicTuple[str] = ("FlextInfraWorkspaceEnvironmentContracts",)
