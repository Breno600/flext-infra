# Changelog

<!-- TOC START -->

- No sections found

<!-- TOC END -->

This file is managed by `make docs`.

- Unreleased

- **Exterminated the `APPLY` write-enable flag (operator law 2026-09-11).** Every public
  Make verb mutates by default with zero variables; read-only verification lives in
  dedicated verbs (`check`) and explicit modes (`codegen conform --mode check`). Docs,
  templates, config schema (`apply_variable`/`apply_value`/`apply_absent_value`,
  per-verb `requires_apply`, workflow `apply` intents) and the docs command contract
  validator were removed or inverted accordingly.

- E2E make-work disposable proof (bead flext-4gh1).
