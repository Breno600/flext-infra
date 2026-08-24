"""Contract tests for the make-managed development-lane verb."""

from __future__ import annotations

from flext_infra import config, m
from flext_tests import tm


class TestsCodegenWorkVerb:
    """`work` is the single canonical public lane verb."""

    def _verb(self, name: str) -> m.Infra.MakeVerbSpec:
        matches = tuple(
            verb for verb in config.Infra.codegen.make.verbs if verb.name == name
        )
        tm.that(matches, len=1)
        return matches[0]

    def test_work_is_a_canonical_public_verb(self) -> None:
        """Every generated project receives the governed lane route.

        Declaring it in `extra_verbs` would make it repository-local, which
        would defeat the purpose: every project must expose the same lane
        surface.
        """
        tm.that(self._verb("work").name, eq="work")

    def test_no_public_worktree_verb_competes_with_work(self) -> None:
        """One lane surface only.

        `worktree` was the raw registry verb. Keeping it public alongside
        `work` would let a caller create a lane that no bead owns, which is
        exactly the unrecoverable state the saga exists to prevent.
        """
        names = tuple(verb.name for verb in config.Infra.codegen.make.verbs)
        tm.that(names, lacks="worktree")

    def test_work_defaults_to_a_read_only_selector(self) -> None:
        """The default selector reports lane state without mutating anything."""
        tm.that(self._verb("work").default_what, eq="status")

    def test_work_owns_the_full_lane_lifecycle(self) -> None:
        """Start, status, land, and finish are the declared saga steps."""
        tm.that(set(self._verb("work").whats), eq={"start", "status", "land", "finish"})

    def test_lane_mutation_requires_the_apply_guard(self) -> None:
        """Lane mutation is authority-bearing, so the verb is apply-guarded.

        `status` stays usable without `APPLY=Y` because its recipe never calls
        `_require_apply`; the guard lives in the mutating recipes.
        """
        tm.that(self._verb("work").apply_guarded, eq=True)
