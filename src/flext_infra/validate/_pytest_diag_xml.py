"""JUnit-XML diagnostics parsing for the pytest-diag extractor (§3.1 split).

JUnit-XML parsing cluster for pytest diagnostics, composed
into ``FlextInfraPytestDiagExtractor`` via FLEXT.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from defusedxml import ElementTree as DefusedET

from flext_infra import c, m, p

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import t


class FlextInfraPytestDiagXmlMixin:
    """JUnit-XML parsing helpers for pytest diagnostics."""

    @staticmethod
    def _as_xml_element(
        value: p.Infra.XmlElementLike | t.JsonValue,
    ) -> p.Infra.XmlElementLike:
        """Require the typed stdlib element API from defusedxml."""
        if not isinstance(value, p.Infra.XmlElementLike):
            msg = f"invalid XML element: {type(value).__name__}"
            raise TypeError(msg)
        return value

    @staticmethod
    def _build_trace_chunk(
        heading: str, label: str, element: p.Infra.XmlElementLike
    ) -> str:
        """Build an error/failure trace chunk from a JUnit XML element."""
        msg = (element.attrib.get(c.Infra.RK_MESSAGE) or "").strip()
        trace = (element.text or "").strip()
        chunk: t.MutableSequenceOf[str] = [f"=== {heading}: {label} ==="]
        if msg:
            chunk.append(msg)
        if trace:
            chunk.append(trace)
        return "\n".join(chunk)

    @staticmethod
    def _process_testcase(
        case: p.Infra.XmlElementLike, diag: m.Infra.DiagResult
    ) -> t.Pair[float, str]:
        """Process a single testcase element; returns (seconds, label)."""
        classname = case.attrib.get("classname", "")
        name = case.attrib.get(c.Infra.NAME, "")
        label = f"{classname}::{name}" if classname else name
        secs = float(case.attrib["time"])
        if (failure := case.find("failure")) is not None:
            diag.failed_cases.append(label)
            diag.error_traces.append(
                FlextInfraPytestDiagXmlMixin._build_trace_chunk(
                    "FAILURE", label, failure
                )
            )
        if (error := case.find(c.Infra.ERROR)) is not None:
            diag.error_cases.append(label)
            diag.error_traces.append(
                FlextInfraPytestDiagXmlMixin._build_trace_chunk("ERROR", label, error)
            )
        if (skipped := case.find("skipped")) is not None:
            reason = (
                skipped.attrib.get(c.Infra.RK_MESSAGE) or skipped.text or ""
            ).strip()
            diag.skip_cases.append(f"{label} | {reason}" if reason else label)
        return secs, label

    @staticmethod
    def _parse_xml(junit_path: Path, diag: m.Infra.DiagResult) -> None:
        """Parse the required JUnit XML and populate diagnostics."""
        root_raw = DefusedET.parse(junit_path).getroot()
        if root_raw is None:
            msg = f"JUnit XML has no root element: {junit_path}"
            raise ValueError(msg)
        root = FlextInfraPytestDiagXmlMixin._as_xml_element(root_raw)
        slow_rows: t.MutableSequenceOf[t.Pair[float, str]] = []
        for case_raw in root.iter("testcase"):
            case = FlextInfraPytestDiagXmlMixin._as_xml_element(case_raw)
            slow_rows.append(FlextInfraPytestDiagXmlMixin._process_testcase(case, diag))
        if slow_rows:
            diag.slow_entries = [
                f"{secs:.6f}s | {label}"
                for secs, label in sorted(slow_rows, reverse=True)
            ]


__all__: list[str] = ["FlextInfraPytestDiagXmlMixin"]
