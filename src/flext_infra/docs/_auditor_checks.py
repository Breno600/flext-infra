"""Issue collection helpers for FlextInfraDocAuditor.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra.utilities import u

if TYPE_CHECKING:
    from collections.abc import Callable

    from flext_infra.docs.models import m
    from flext_infra.docs.typings import t


class FlextInfraDocAuditorChecksMixin:
    """Mixin for documentation audit issue checks."""

    @staticmethod
    def forbidden_term_issues(
        scope: m.Infra.DocScope,
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Return forbidden-term issues configured for one scope.

        Returns:
            Forbidden-term issues configured for one scope.

        """
        return u.Infra.docs_text_token_issues(
            scope,
            tokens=u.Infra.docs_audit_policy(scope).forbidden_terms,
            issue_type="forbidden_term",
        )

    @staticmethod
    def placeholder_issues(scope: m.Infra.DocScope) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Return placeholder-text issues for one scope.

        Returns:
            Placeholder-text issues for one scope.

        """
        return u.Infra.docs_placeholder_issues(
            scope,
            patterns=u.Infra.docs_audit_policy(scope).placeholder_patterns,
        )

    @staticmethod
    def machine_path_issues(
        scope: m.Infra.DocScope,
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Return machine-local paths outside exact historical evidence files.

        Returns:
            Machine-local paths outside exact historical evidence files.

        """
        return u.Infra.docs_machine_path_issues(
            scope,
            historical_evidence_files=(
                u.Infra.docs_audit_policy(scope).historical_evidence_files
            ),
        )

    def _collect_issues(
        self,
        scope: m.Infra.DocScope,
        checks: t.StrSequence,
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Collect issues for the requested check set in canonical order.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.AuditIssue]``.

        """
        handlers: t.VariadicTuple[
            t.Pair[str, Callable[[m.Infra.DocScope], t.SequenceOf[m.Infra.AuditIssue]]]
        ] = (
            ("links", u.Infra.docs_broken_link_issues),
            ("forbidden-terms", self.forbidden_term_issues),
            ("placeholders", self.placeholder_issues),
            ("machine-paths", self.machine_path_issues),
            ("stale-symbols", u.Infra.docs_stale_symbol_issues),
            ("scope-boundary", u.Infra.docs_scope_boundary_issues),
            ("generated-ownership", u.Infra.docs_generated_ownership_issues),
            ("command-contract", u.Infra.docs_command_contract_issues),
            ("docstrings", u.Infra.docs_public_docstring_issues),
            ("python-codeblocks", u.Infra.docs_python_codeblock_issues),
        )
        return tuple(
            issue
            for check_name, handler in handlers
            if check_name in checks
            for issue in handler(scope)
        )


__all__: list[str] = ["FlextInfraDocAuditorChecksMixin"]
