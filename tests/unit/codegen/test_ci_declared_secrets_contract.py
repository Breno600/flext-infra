"""Verify every rendered ci.yml secret access is a declared workflow_call input."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from flext_cli import u
from flext_tests import tm

from flext_infra import c, t

from ._support import CodegenTestSupport


class TestsFlextInfraCiDeclaredSecretsContract:
    """Keep rendered secret accesses on the declared optional contract.

    The GitHub Actions language service validates ``secrets.*`` accesses
    against the live repository secret list unless a ``workflow_call``
    trigger declares the names, so the generator owns the pairing: every
    referenced secret must appear as a ``required: false`` workflow_call
    secret input in the same rendered workflow. The check is by construction
    for arbitrary fragment-configured names, never frozen to today's values.
    """

    ci_template = (
        Path(__file__).resolve().parents[3]
        / "src/flext_infra/templates/project/base/.github/workflows/ci.yml.j2"
    )

    @classmethod
    def render_ci(cls, tmp_path: Path) -> Path:
        """Render the ci.yml template once and materialize it for parsing."""
        spec = CodegenTestSupport.Ci.workflow_spec(
            dist="mcb",
            make_profile=c.Infra.MakeProfile.STANDALONE,
            repository_branch="conformance/declared-secrets",
            ci_trigger_branches=CodegenTestSupport.Ci.ci_trigger_branches(
                "conformance/declared-secrets"
            ),
        )
        workflow_path = tmp_path / "ci.yml"
        workflow_path.write_text(tm.ok(u.Cli.template_render(cls.ci_template, spec)))
        return workflow_path

    @classmethod
    def _declared_secret_names(cls, workflow_path: Path) -> t.JsonMapping:
        """Return the workflow_call secret contract parsed from the render."""
        document = u.Cli.yaml_load_mapping(workflow_path)
        triggers = t.Cli.JSON_MAPPING_ADAPTER.validate_python(document["on"])
        workflow_call = t.Cli.JSON_MAPPING_ADAPTER.validate_python(
            triggers["workflow_call"]
        )
        return t.Cli.JSON_MAPPING_ADAPTER.validate_python(workflow_call["secrets"])

    @classmethod
    def _referenced_secret_names(cls, workflow_path: Path) -> set[str]:
        """Collect every ``secrets.<NAME>`` access in the rendered workflow."""
        document = u.Cli.yaml_load_mapping(workflow_path)
        jobs = t.Cli.JSON_MAPPING_ADAPTER.validate_python(document["jobs"])
        referenced: set[str] = set()
        for raw_job in jobs.values():
            job = t.Cli.JSON_MAPPING_ADAPTER.validate_python(raw_job)
            raw_steps = job["steps"]
            if not isinstance(raw_steps, list):
                continue
            for raw_step in raw_steps:
                if not isinstance(raw_step, Mapping):
                    continue
                raw_env = raw_step.get("env")
                if not isinstance(raw_env, Mapping):
                    continue
                for raw_value in raw_env.values():
                    if isinstance(raw_value, str) and "secrets." in raw_value:
                        tail = raw_value.split("secrets.", maxsplit=1)[1]
                        referenced.add(tail.split("}", maxsplit=1)[0].strip())
        return referenced

    def test_secret_accesses_are_declared_optional_workflow_call_inputs(
        self, tmp_path: Path
    ) -> None:
        """Every referenced secret resolves to an optional workflow_call input."""
        workflow_path = self.render_ci(tmp_path)
        declared = self._declared_secret_names(workflow_path)

        # GITHUB_TOKEN is platform-provided and reserved: it can never be a
        # declared reusable-workflow secret input, so it is out of contract.
        referenced = self._referenced_secret_names(workflow_path)
        referenced.discard("GITHUB_TOKEN")

        tm.that(referenced - set(declared), eq=set())
        for contract in declared.values():
            specification = t.Cli.JSON_MAPPING_ADAPTER.validate_python(contract)
            tm.that(specification["required"], eq=False)
