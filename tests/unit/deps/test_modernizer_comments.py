"""Comment injection phase tests for deps modernizer."""

from __future__ import annotations

from flext_tests import tm

from flext_infra import FlextInfraInjectCommentsPhase, c, u


class TestsFlextInfraDepsModernizerComments:
    """Tests comment injection behavior."""

    def _owned_marker(self, section: str) -> str:
        spec = tm.ok(u.Infra.pyproject_managed_file())
        owned = next(
            item
            for item in spec.conflict_sections
            if u.Infra.toml_section_is_owned(section, (item,))
        )
        return f"# [MANAGED] {owned}"

    def test_inject_comments_adds_banner(self) -> None:
        """Inject the canonical managed banner."""
        rendered = "[project]\nname = 'test'"
        result, changes = FlextInfraInjectCommentsPhase().apply(rendered)
        tm.that(result, starts=c.Infra.BANNER)
        tm.that(any("banner" in change for change in changes), eq=True)

    def test_inject_comments_injects_markers(self) -> None:
        """Report managed section marker injection."""
        rendered = "[project]\nname = 'test'\n[tool.pytest]"
        _, changes = FlextInfraInjectCommentsPhase().apply(rendered)
        tm.that(any("marker" in change for change in changes), eq=True)

    def test_inject_comments_marks_project_keys_from_ssot(self) -> None:
        """[project] comments list preserve/overwrite keys from the managed file."""
        spec = tm.ok(u.Infra.pyproject_managed_file())
        result, _changes = FlextInfraInjectCommentsPhase().apply(
            "[project]\nname = 'test'\n"
        )
        custom_line = next(
            line for line in result.splitlines() if line.startswith("# [CUSTOM]")
        )
        for key in spec.preserve_project_keys:
            tm.that(custom_line, has=key)
        tm.that(result, has="# [MANAGED] " + ", ".join(spec.overwrite_project_keys))
        tm.that(custom_line, lacks="project metadata")

    def test_inject_comments_marks_unlisted_tool_table_custom(self) -> None:
        """A [tool.*] table absent from conflict_sections is CUSTOM."""
        result, _changes = FlextInfraInjectCommentsPhase().apply(
            "[tool.bandit]\nskips = []\n"
        )
        tm.that(result, has="# [CUSTOM] tool.bandit")

    def test_inject_comments_removes_broken_group_section(self) -> None:
        """Remove unsupported dependency-group sections."""
        rendered = "[group.dev.dependencies]\npytest = '^7.0'"
        result, changes = FlextInfraInjectCommentsPhase().apply(rendered)
        tm.that("[group.dev.dependencies]" not in result, eq=True)
        tm.that(any("broken" in change for change in changes), eq=True)

    def test_inject_comments_handles_optional_dependencies_dev(self) -> None:
        """Preserve development dependencies content."""
        rendered = "[project.optional-dependencies]\ndev = ['pytest']"
        result, changes = FlextInfraInjectCommentsPhase().apply(rendered)
        tm.that(("dev" in result) or (changes), eq=True)

    def test_inject_comments_preserves_existing_markers(self) -> None:
        """Restamp a managed section from the SSOT, not a frozen phrase."""
        rendered = "# [MANAGED] build-system\n[build-system]"
        result, _ = FlextInfraInjectCommentsPhase().apply(rendered)
        tm.that(result, has=self._owned_marker("build-system"))

    def test_inject_comments_phase_apply_banner(self) -> None:
        """Return a change record when injecting the banner."""
        rendered = '[project]\nname = "test"\n'
        result, changes = FlextInfraInjectCommentsPhase().apply(rendered)
        tm.that(result, starts=c.Infra.BANNER)
        tm.that(changes, has="managed banner injected")

    def test_inject_comments_phase_apply_markers(self) -> None:
        """Annotate governed tool sections with managed markers."""
        rendered = '[project]\nname = "test"\n[tool.pytest]\n'
        result, _ = FlextInfraInjectCommentsPhase().apply(rendered)
        tm.that(result, has="[MANAGED]")

    def test_inject_comments_phase_apply_broken_group_section(self) -> None:
        """Report removal of an invalid dependency-group section."""
        rendered = '[group.dev.dependencies]\nrequests = "*"\n[project]\n'
        result, changes = FlextInfraInjectCommentsPhase().apply(rendered)
        tm.that("[group.dev.dependencies]" not in result, eq=True)
        tm.that(changes, has="broken [group.dev.dependencies] section removed")

    def test_inject_comments_phase_apply_with_optional_dependencies_dev(self) -> None:
        """Handle dotted development dependency declarations."""
        rendered = "[project.optional-dependencies]\noptional-dependencies.dev = ['pytest', 'coverage']\n"
        result, changes = FlextInfraInjectCommentsPhase().apply(rendered)
        tm.that(("optional-dependencies.dev" in result) or (changes), eq=True)

    def test_inject_comments_phase_repositions_marker_before_section(self) -> None:
        """Position a managed marker immediately before its section."""
        rendered = '[tool.coverage.report]\nprecision = 2\n# [MANAGED] pyrefly\n[tool.pyrefly]\npython-version = "3.13"'
        result, _changes = FlextInfraInjectCommentsPhase().apply(rendered)
        lines = result.splitlines()
        pyrefly_idx = lines.index("[tool.pyrefly]")
        tm.that(lines[pyrefly_idx - 1], eq=self._owned_marker("tool.pyrefly"))

    def test_inject_comments_phase_removes_auto_banner_and_auto_marker(self) -> None:
        """Replace superseded automatic banner and marker variants."""
        rendered = "# [MANAGED] FLEXT pyproject standardization\n# Sections with [MANAGED] are enforced by flext_infra.deps.modernizer.\n# Sections with [AUTO] are derived from workspace layout and dependencies.\n# [AUTO] merged from dev/docs/security/test/typings\n[project.optional-dependencies]\ndev = ['pytest']"
        result, _changes = FlextInfraInjectCommentsPhase().apply(rendered)
        tm.that(result, starts=c.Infra.BANNER)
        tm.that("[AUTO]" in result, eq=False)

    def test_inject_comments_phase_marks_pytest_and_coverage_subtables(self) -> None:
        """Annotate governed pytest and coverage subtables from the SSOT."""
        rendered = '[tool.pytest.ini_options]\nminversion = "8.0"\n[tool.coverage.report]\nprecision = 2'
        result, _changes = FlextInfraInjectCommentsPhase().apply(rendered)
        tm.that(result, has=self._owned_marker("tool.pytest.ini_options"))
        tm.that(result, has=self._owned_marker("tool.coverage.report"))

    def test_inject_comments_phase_deduplicates_family_markers(self) -> None:
        """Emit one marker for multiple tables in the same tool family."""
        rendered = (
            "[tool.coverage.run]\nbranch = true\n[tool.coverage.report]\nprecision = 2"
        )
        result, _changes = FlextInfraInjectCommentsPhase().apply(rendered)
        tm.that(result.count(self._owned_marker("tool.coverage")), eq=1)

    def test_inject_comments_phase_is_idempotent_on_managed_content(self) -> None:
        """Produce byte-identical output and no changes on a second pass."""
        rendered = (
            '[project]\nname = "test"\n[tool.pytest.ini_options]\nminversion = "8.0"\n'
        )
        first_result, first_changes = FlextInfraInjectCommentsPhase().apply(rendered)
        second_result, second_changes = FlextInfraInjectCommentsPhase().apply(
            first_result
        )
        tm.that(first_changes, len=(1, 20))
        tm.that(second_result, eq=first_result)
        tm.that(second_changes, empty=True)

    def test_inject_comments_normalizes_leading_parse_trivia(self) -> None:
        """Keep the managed banner byte-identical after TOML parse/render."""
        phase = FlextInfraInjectCommentsPhase()
        with_trivia, _changes = phase.apply('\n[project]\nname = "test"\n')
        without_trivia, _changes = phase.apply('[project]\nname = "test"\n')
        tm.that(with_trivia, eq=without_trivia)

    def test_inject_comments_is_idempotent_when_marker_precedes_blank_line(
        self,
    ) -> None:
        """Converge when a blank line already separates marker and section."""
        rendered = (
            '[project]\nname = "test"\n'
            f"\n{self._owned_marker('tool.pytest')}\n\n"
            '[tool.pytest.ini_options]\nminversion = "8.0"\n'
        )
        phase = FlextInfraInjectCommentsPhase()
        first_result, _first_changes = phase.apply(rendered)
        second_result, second_changes = phase.apply(first_result)
        tm.that(second_result, eq=first_result)
        tm.that(second_changes, empty=True)
