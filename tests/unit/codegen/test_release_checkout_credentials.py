"""Verify generated release jobs retain the credential required by Git pushes."""

from __future__ import annotations

from pathlib import Path

from flext_cli import t, u
from flext_tests import tm

from flext_infra import c

from ._support import CodegenTestSupport


class TestsFlextInfraReleaseCheckoutCredentials:
    """Release jobs push branches and tags through the checkout credential."""

    release_template = (
        Path(__file__).resolve().parents[3]
        / "src/flext_infra/templates/project/base/.github/workflows/release.yml.j2"
    )

    @classmethod
    def render_release(cls) -> t.JsonMapping:
        repository_branch = "develop"
        spec = CodegenTestSupport.Ci.workflow_spec(
            dist="example-workspace",
            make_profile=c.Infra.MakeProfile.STANDALONE,
            repository_branch=repository_branch,
            ci_trigger_branches=CodegenTestSupport.Ci.ci_trigger_branches(
                repository_branch
            ),
        ).model_copy(
            update={
                "private_submodules": (
                    CodegenTestSupport.Ci.synthetic_private_submodules()
                )
            }
        )
        rendered = tm.ok(u.Cli.template_render(cls.release_template, spec))
        return t.Cli.JSON_MAPPING_ADAPTER.validate_python(
            tm.ok(u.Cli.yaml_parse(rendered))
        )

    @staticmethod
    def checkout_credentials(job: t.JsonValue) -> bool:
        mapping = t.Cli.JSON_MAPPING_ADAPTER.validate_python(job)
        steps = mapping["steps"]
        if not isinstance(steps, list):
            msg = "workflow job steps must be a sequence"
            raise TypeError(msg)
        checkout = t.Cli.JSON_MAPPING_ADAPTER.validate_python(steps[0])
        inputs = t.Cli.JSON_MAPPING_ADAPTER.validate_python(checkout["with"])
        value = inputs["persist-credentials"]
        if not isinstance(value, bool):
            msg = "persist-credentials must render as a YAML boolean"
            raise TypeError(msg)
        return value

    def test_release_push_jobs_persist_declared_checkout_token(self) -> None:
        document = self.render_release()
        jobs = t.Cli.JSON_MAPPING_ADAPTER.validate_python(document["jobs"])

        tm.that(self.checkout_credentials(jobs["identity"]), eq=False)
        tm.that(self.checkout_credentials(jobs["version"]), eq=True)
        tm.that(self.checkout_credentials(jobs["publish"]), eq=True)
