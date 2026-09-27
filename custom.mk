# Project-local lifecycle hooks for flext-infra.
#
# Owner: this handwritten file may define only pre-<verb> and post-<verb>
# hooks for public verbs declared in config/codegen.yaml. Distinct operations
# belong in that typed verb catalog and its generated Make implementation.

.PHONY: post-gen
post-gen:
	@$(PROJECT_INFRA_RUN) -c 'from pathlib import Path; from flext_infra import u; from flext_infra.codemod import FlextInfraModGateEngine; root = Path.cwd(); plan = u.Infra.codemod_rule_plan(root).unwrap(); FlextInfraModGateEngine.validate_rule_fixtures(root, tuple(dict.fromkeys(rule.resource for rule in plan.rules))).unwrap()'
