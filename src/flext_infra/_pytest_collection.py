"""Enforce the runner's collection manifest through pytest's public hook API.

The runner resolves selected node IDs once and passes that ordered manifest as
pytest arguments. Testmon still records dependencies in every worker, but its
worker-local stable/unstable classification must not define xdist's index order.
Missing, additional or duplicate tests fail loudly. The same installed plugin
records warning identities before report-log reduces their categories to names.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from collections.abc import Generator
from hashlib import sha256
from pathlib import Path
from sys import monitoring
from traceback import format_exception
from types import CodeType
from typing import ClassVar
from warnings import WarningMessage

import pytest
from flext_cli import u
from pytest_markdown_docs.definitions import FenceTestDefinition
from pytest_markdown_docs.plugin import (
    FenceSyntax,
    MarkdownInlinePythonItem,
    MarkdownTextFile,
    extract_fence_tests,
)
from xdist.dsession import DSession

from flext_infra._constants.check import FlextInfraConstantsCheck
from flext_infra._constants.make import FlextInfraConstantsMake
from flext_infra._models.validate import FlextInfraModelsCore


class FlextInfraPytestCollection:
    """Pytest entry-point plugin for the runner's explicit selection contract."""

    _markdown: ClassVar[
        pytest.StashKey[FlextInfraModelsCore.PytestMarkdownCollection]
    ] = pytest.StashKey()

    @staticmethod
    def _origin(
        definition: FenceTestDefinition,
        root: Path,
    ) -> FlextInfraModelsCore.PytestMarkdownOrigin:
        """Bind the SDK definition without compiling or interpreting its source.

        Returns:
            The resulting ``FlextInfraModelsCore.PytestMarkdownOrigin``.
        """
        return FlextInfraModelsCore.PytestMarkdownOrigin(
            source_path=definition.source_path.resolve().relative_to(root).as_posix(),
            start_line=definition.start_line,
            source_sha256=sha256(definition.source.encode("utf-8")).hexdigest(),
            max_retries=definition.max_retries,
        )

    @staticmethod
    def pytest_collectstart(collector: pytest.Collector) -> None:
        """Measure eligibility before the real collector can omit any item."""
        if not isinstance(collector, MarkdownTextFile):
            return
        state = collector.config.stash[FlextInfraPytestCollection._markdown]
        parser = collector.config.hook.pytest_markdown_docs_markdown_it()
        syntax = FenceSyntax(collector.config.getoption("markdowndocs_syntax"))
        definitions = extract_fence_tests(
            parser,
            collector.path.read_text(encoding="utf-8"),
            start_line_offset=0,
            source_path=collector.path,
            markdown_type=collector.path.suffix.removeprefix("."),
            fence_syntax=syntax,
        )
        state.eligible.extend(
            FlextInfraPytestCollection._origin(definition, collector.config.rootpath)
            for definition in definitions
        )

    @staticmethod
    def pytest_itemcollected(item: pytest.Item) -> None:
        """Retain actual Markdown node identities before selector hooks run."""
        if not isinstance(item, MarkdownInlinePythonItem) or not isinstance(
            item.parent,
            MarkdownTextFile,
        ):
            return
        state = item.config.stash[FlextInfraPytestCollection._markdown]
        observation = FlextInfraModelsCore.PytestMarkdownItem(
            node_id=item.nodeid,
            origin=FlextInfraPytestCollection._origin(
                item.test_definition,
                item.config.rootpath,
            ),
        )
        state.collected.append(observation)
        item.user_properties.append((
            "flext_markdown_origin",
            observation.model_dump_json(),
        ))

    @staticmethod
    def pytest_deselected(items: list[pytest.Item]) -> None:
        """Account for selector effects through their public notification."""
        for item in items:
            if isinstance(item, MarkdownInlinePythonItem) and isinstance(
                item.parent,
                MarkdownTextFile,
            ):
                item.config.stash[
                    FlextInfraPytestCollection._markdown
                ].deselected.append(
                    item.nodeid,
                )

    @staticmethod
    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_call(item: pytest.Item) -> Generator[None]:
        """Observe the real runner without replacing it or patching the SDK.

        Raises:
            RuntimeError: If Markdown execution requires exactly one runner attempt.
        """
        if not isinstance(item, MarkdownInlinePythonItem) or not isinstance(
            item.parent,
            MarkdownTextFile,
        ):
            yield
            return
        tool = monitoring.PROFILER_ID
        code = item.runner.runtest.__code__
        observer = FlextInfraPytestCollection.MarkdownAttempts(code)
        monitoring.use_tool_id(tool, "flext-markdown-attempts")
        try:
            monitoring.register_callback(
                tool, monitoring.events.PY_START, observer.start,
            )
            monitoring.register_callback(
                tool, monitoring.events.PY_UNWIND, observer.unwind,
            )
            monitoring.set_local_events(tool, code, monitoring.events.PY_START)
            monitoring.set_events(tool, monitoring.events.PY_UNWIND)
            try:
                yield
            except BaseException as error:
                if observer.first_error is not None and observer.first_error is not error:
                    raise observer.first_error from error
                raise
            finally:
                proof = FlextInfraModelsCore.PytestMarkdownAttempt(
                    node_id=item.nodeid,
                    attempts=observer.attempts,
                    first_exception_type=(
                        None
                        if observer.first_error is None
                        else type(observer.first_error).__qualname__
                    ),
                    first_exception_traceback=(
                        None
                        if observer.first_error is None
                        else "".join(format_exception(observer.first_error))
                    ),
                )
                item.user_properties.append((
                    "flext_markdown_attempt",
                    proof.model_dump_json(),
                ))
            if observer.first_error is not None:
                raise observer.first_error
            if observer.attempts != 1:
                msg = (
                    "Markdown execution requires exactly one runner attempt: "
                    f"{item.nodeid}"
                )
                raise RuntimeError(msg)
        finally:
            monitoring.set_events(tool, 0)
            monitoring.set_local_events(tool, code, 0)
            monitoring.register_callback(tool, monitoring.events.PY_START, None)
            monitoring.register_callback(tool, monitoring.events.PY_UNWIND, None)
            monitoring.free_tool_id(tool)

    class MarkdownAttempts:
        """One runtest-hook observer using native interpreter events."""

        def __init__(self, code: CodeType) -> None:
            self.code = code
            self.attempts = 0
            self.first_error: BaseException | None = None

        def start(self, _code: CodeType, _instruction_offset: int) -> None:
            """Count every entry into the already-selected SDK runner."""
            self.attempts += 1

        def unwind(
            self,
            code: CodeType,
            _instruction_offset: int,
            exception: BaseException,
        ) -> None:
            """Retain the first exception before the plugin can retry it."""
            if code is self.code and self.first_error is None:
                self.first_error = exception

    @staticmethod
    def pytest_addoption(parser: pytest.Parser) -> None:
        """Require explicit activation by the canonical runner."""
        parser.addoption(
            FlextInfraConstantsCheck.PYTEST_SELECTED_COLLECTION_OPTION,
            default=None,
            help="Manifest whose ordered node-ID selection every worker enforces.",
        )
        parser.addoption(
            FlextInfraConstantsCheck.PYTEST_COLLECTION_MANIFEST_OPTION,
            default=None,
            help="Path where a collect-only session publishes its final items.",
        )
        parser.addoption(
            FlextInfraConstantsCheck.PYTEST_SUITE_STOP_OPTION,
            type=float,
            default=None,
            help="Monotonic instant after which the session stops gracefully.",
        )

    @staticmethod
    def pytest_configure(config: pytest.Config) -> None:
        """Record warnings once, on the controller or in serial execution."""
        config.stash[FlextInfraPytestCollection._markdown] = (
            FlextInfraModelsCore.PytestMarkdownCollection()
        )
        report_log = config.getoption("report_log")
        if report_log and not hasattr(config, "workerinput"):
            config.pluginmanager.register(
                FlextInfraPytestCollection.WarningAccounting(Path(report_log)),
            )
        stop_at = config.getoption(FlextInfraConstantsCheck.PYTEST_SUITE_STOP_OPTION)
        if stop_at is not None and not hasattr(config, "workerinput"):
            config.pluginmanager.register(
                FlextInfraPytestCollection.SuiteStop(stop_at_monotonic=stop_at),
            )

    @staticmethod
    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_collection_finish(session: pytest.Session) -> Generator[None]:
        """Validate before xdist publishes worker IDs, preserving raw failures.

        Both manifest routes are runner-passed options: a session that names
        neither imports no model. A requested manifest loads only its owning
        model module, never the whole model facade, because every runner
        collection process pays that import.

        Raises:
            ValueError: If Runner collection manifest contains duplicate node IDs; or if
                Runner collection differs from selection.

        """
        selected: str | None = session.config.getoption(
            FlextInfraConstantsCheck.PYTEST_SELECTED_COLLECTION_OPTION,
        )
        if selected is not None:
            manifest = (
                FlextInfraModelsCore.PytestCollectionManifest.model_validate_json(
                    Path(selected).read_text(encoding="utf-8"),
                )
            )
            order = {node_id: index for index, node_id in enumerate(manifest.node_ids)}
            collected = [item.nodeid for item in session.items]
            if len(order) != len(manifest.node_ids) or len(set(collected)) != len(
                collected,
            ):
                msg = "Runner collection manifest contains duplicate node IDs"
                raise ValueError(msg)
            if set(collected) != set(order):
                missing = sorted(set(order) - set(collected))
                unexpected = sorted(set(collected) - set(order))
                msg = (
                    f"Runner collection differs from selection: "
                    f"{missing=}, {unexpected=}"
                )
                raise ValueError(msg)
            session.items.sort(key=lambda item: order[item.nodeid])
        yield
        target: str | None = session.config.getoption(
            FlextInfraConstantsCheck.PYTEST_COLLECTION_MANIFEST_OPTION,
        )
        if target is not None and session.config.getoption("collectonly"):
            FlextInfraPytestCollection._write_collection_manifest(session, Path(target))

    @staticmethod
    def _write_collection_manifest(session: pytest.Session, target: Path) -> None:
        """Publish final selected items after testmon and every collection hook."""
        state = session.config.stash[FlextInfraPytestCollection._markdown]
        manifest = FlextInfraModelsCore.PytestCollectionManifest(
            node_ids=tuple(item.nodeid for item in session.items),
            markdown_eligible=tuple(state.eligible),
            markdown_collected=tuple(state.collected),
            markdown_deselected=tuple(state.deselected),
        )
        u.Cli.atomic_write_text_file(target, manifest.model_dump_json() + "\n").unwrap()

    class SuiteStop:
        """End the session gracefully at the runner's derived stop instant.

        The controller stops dispatch through the same path as max-failures:
        xdist queues the shutdown marker, so each worker's final item runs
        with no successor and pytest-testmon flushes every batched result.
        A process-deadline SIGTERM instead discards the unflushed batches.

        When every collected item has already completed, nothing is left to
        stop and the stop request would only recolor a finished green suite
        red, so the request is suppressed at that boundary.
        """

        def __init__(self, *, stop_at_monotonic: float) -> None:
            self.stop_at_monotonic = stop_at_monotonic
            self.session: pytest.Session | None = None
            self.controller: DSession | None = None
            self.completed_items: set[str] = set()

        def pytest_sessionstart(self, session: pytest.Session) -> None:
            """Bind the controller session that owns the stop decision."""
            self.session = session
            self.controller = session if isinstance(session, DSession) else None

        def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
            """Request the stop once a completed item crosses the instant.

            The request is suppressed when this item was the last one still
            pending: a suite that already finished must end green instead of
            being interrupted after its own final result.
            """
            session = self.session
            if session is None or report.when != "teardown":
                return
            # The instant is computed in the runner parent and handed to this
            # process as a CLI option; a clock skew between the two (or a
            # stale parent clock) must never stop a suite whose deadline has
            # not actually passed on this process's own monotonic clock.
            if time.monotonic() < self.stop_at_monotonic:
                return
            self.completed_items.add(report.nodeid)
            total_items = len(session.items)
            if total_items and len(self.completed_items) >= total_items:
                return
            # Testmon writes an in-flight coverage batch only when it attaches
            # nodes_files_lines to a teardown report. Stopping earlier leaves
            # selected rows without durable execution data on the next run.
            if not getattr(report, "nodes_files_lines", None):
                return
            reason = f"suite stop instant {self.stop_at_monotonic:.3f} reached"
            controller = self.controller
            if isinstance(controller, DSession):
                if not controller.shouldstop:
                    controller.shouldstop = reason
            elif not session.shouldstop:
                session.shouldstop = reason

    class WarningAccounting:
        """Preserve the real class identity of every recorded warning."""

        def __init__(self, report_log: Path) -> None:
            # Owner modules, never the root facades: this plugin loads in every
            # consumer test process, and ``m.Infra`` builds the whole model
            # family (seconds of class construction) to write one JSON line.
            self.report = report_log.with_suffix(
                FlextInfraConstantsMake.PYTEST_WARNING_EVENTS_SUFFIX,
            )
            self.report.parent.mkdir(parents=True, exist_ok=True)
            self.report.write_text("", encoding="utf-8")

        @pytest.hookimpl(tryfirst=True)
        def pytest_warning_recorded(self, warning_message: WarningMessage) -> None:
            """Record the real warning once before report-log serializes it."""
            category = warning_message.category
            event = FlextInfraModelsCore.PytestWarningEvent(
                category=category.__name__,
                category_module=category.__module__,
                category_qualname=category.__qualname__,
                filename=warning_message.filename,
                lineno=warning_message.lineno,
                message=str(warning_message.message),
            )
            with self.report.open("a", encoding="utf-8") as stream:
                stream.write(event.model_dump_json() + "\n")


__all__: list[str] = ["FlextInfraPytestCollection"]
