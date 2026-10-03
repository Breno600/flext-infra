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

from collections.abc import Generator
from pathlib import Path
from warnings import WarningMessage

import pytest
from xdist.dsession import DSession

from flext_infra._constants.check import FlextInfraConstantsCheck


class FlextInfraPytestCollection:
    """Pytest entry-point plugin for the runner's explicit selection contract."""

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
            from flext_infra._models.validate import FlextInfraModelsCore

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
        from flext_cli import u

        from flext_infra._models.validate import FlextInfraModelsCore

        manifest = FlextInfraModelsCore.PytestCollectionManifest(
            node_ids=tuple(item.nodeid for item in session.items),
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
            from flext_infra._constants.make import FlextInfraConstantsMake

            self.report = report_log.with_suffix(
                FlextInfraConstantsMake.PYTEST_WARNING_EVENTS_SUFFIX,
            )
            self.report.parent.mkdir(parents=True, exist_ok=True)
            self.report.write_text("", encoding="utf-8")

        @pytest.hookimpl(tryfirst=True)
        def pytest_warning_recorded(self, warning_message: WarningMessage) -> None:
            """Record the real warning once before report-log serializes it."""
            from flext_infra._models.validate import FlextInfraModelsCore

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
