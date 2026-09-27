# Check policy suspension

`config/codegen.yaml` owns `Infra.codegen.make.policy_check_suspension_reason`. A
nonempty reason authorizes temporary suspension of custom infra policy checks across the
fleet. Setting it to `null` restores their execution. Gate identities and their
external/policy classification share `c.Infra.GATE_METADATA`; SARIF tool metadata
derives from it.

The check dispatcher continues running external lint, format, type, security, and
Markdown tools, including `markdown-code`. Custom checks, including `codemod`,
`loc-cap`, and `duplication`, are reported as **SUSPENDED / NOT RUN** before any policy
gate is instantiated. Repair operations retain their existing behavior.

A suspension is separate from `GateExecution` and never creates a passing result.
`ProjectResult.passed` requires complete execution; `accepted` records acceptance of the
active scope under the declared suspension. An active failure still rejects the command.
Empty project selections and unavailable requested projects fail.

Markdown reports list each suspended gate and its authority. SARIF records the same
typed entries under `runs[].properties.suspendedChecks`, outside diagnostic results. The
console distinguishes active-check acceptance from full-scope validation. An exit-zero
check with suspended policies does not prove complete fleet validation.

Workspace orchestration preserves its `PASS` state and `passed` count as command exit
outcomes. Every aggregate result labels this meaning with `result_scope=command_exit`.
For `check`, `test`, and `test-full`, the active suspension also appears as
`custom_policy_enforcement=suspended`, with its authority printed before execution.
These fields do not certify that all policies executed.

The same authority applies to the explicitly classified MRO/enforcement warning
categories in the test runner. Their messages and counts remain visible; unrelated
warnings and all functional failures remain blocking. Darwin-specific resource contracts
still require native macOS evidence.
