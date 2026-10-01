"""Pyright Language Server Protocol diagnostics detector."""

from __future__ import annotations

import time
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from flext_core import r
from flext_infra import c, p, t, u

if TYPE_CHECKING:
    from collections.abc import Iterable


class FlextInfraLspDiagnosticsDetector:
    """Validate changed Python files through a real interactive LSP session."""

    _HEADER_SEPARATOR: ClassVar[bytes] = b"\r\n\r\n"
    _CONTENT_LENGTH: ClassVar[bytes] = b"Content-Length:"
    _INITIALIZE_ID: ClassVar[int] = 1
    _SHUTDOWN_ID: ClassVar[int] = 2
    _DOCUMENT_ID_START: ClassVar[int] = 10

    @classmethod
    def validate(cls, repository_root: Path, files: Iterable[Path]) -> p.Result[bool]:
        """Require clean diagnostics from a complete request/response lifecycle."""
        root = repository_root.resolve()
        targets = tuple(
            sorted({
                resolved
                for path in files
                if (
                    resolved := (path if path.is_absolute() else root / path).resolve()
                ).is_file()
                and resolved.suffix == c.Infra.EXT_PYTHON
            })
        )
        started = u.Cli.process_start((c.Infra.PYRIGHT_LANGSERVER, "--stdio"), cwd=root)
        if started.failure:
            return r[bool].from_failure(started)
        process = started.value
        deadline = time.monotonic() + c.Infra.TIMEOUT_SHORT
        response_ids: set[int] = set()
        expected_uris = {path.as_uri() for path in targets}
        published_uris: set[str] = set()

        def remaining() -> float:
            return deadline - time.monotonic()

        def reject(detail: str) -> p.Result[bool]:
            killed = process.kill()
            reaped = process.wait(timeout=c.Infra.TIMEOUT_SHORT)
            cleanup = tuple(
                error
                for result in (killed, reaped)
                if result.failure
                if (error := result.error)
            )
            suffix = f"; cleanup: {'; '.join(cleanup)}" if cleanup else ""
            return r[bool].fail(f"{detail}{suffix}")

        def send(message: t.JsonMapping) -> p.Result[bool]:
            return process.stdin_write(cls._frame(message))

        def receive() -> p.Result[t.JsonMapping]:
            header = process.stdout_read_until(
                cls._HEADER_SEPARATOR, timeout=remaining()
            )
            if header.failure:
                return r[t.JsonMapping].from_failure(header)
            fields = tuple(
                line
                for line in header.value.removesuffix(cls._HEADER_SEPARATOR).split(
                    b"\r\n"
                )
                if line.startswith(cls._CONTENT_LENGTH)
            )
            if len(fields) != 1:
                return r[t.JsonMapping].fail("LSP response requires one Content-Length")
            body = process.stdout_read_exact(
                int(fields[0].split(b":", maxsplit=1)[1]), timeout=remaining()
            )
            if body.failure:
                return r[t.JsonMapping].from_failure(body)
            decoded = u.Cli.json_loads(body.value)
            if decoded.failure:
                return r[t.JsonMapping].from_failure(decoded)
            if not isinstance(decoded.value, Mapping):
                return r[t.JsonMapping].fail("LSP response body must be an object")
            return r[t.JsonMapping].ok(
                t.Infra.INFRA_MAPPING_ADAPTER.validate_python(decoded.value)
            )

        def record(message: t.JsonMapping) -> p.Result[bool]:
            if "error" in message:
                return r[bool].fail(u.Cli.json_dumps(dict(message)).unwrap())
            response_id = message.get("id")
            method = message.get("method")
            if isinstance(response_id, int) and not isinstance(response_id, bool):
                if isinstance(method, str):
                    return r[bool].fail(f"unsupported LSP server request: {method}")
                response_ids.add(response_id)
            if method != "textDocument/publishDiagnostics":
                return r[bool].ok(True)
            params = message.get("params")
            if not isinstance(params, Mapping):
                return r[bool].fail("LSP diagnostics params must be an object")
            uri = params.get("uri")
            diagnostics = params.get("diagnostics")
            if not isinstance(uri, str) or not isinstance(diagnostics, list):
                return r[bool].fail("LSP diagnostics require uri and list payload")
            published_uris.add(uri)
            if diagnostics:
                return r[bool].fail(f"{uri}: {u.Cli.json_dumps(diagnostics).unwrap()}")
            return r[bool].ok(True)

        initialize = send({
            "jsonrpc": c.Infra.JSON_RPC_VERSION,
            "id": cls._INITIALIZE_ID,
            "method": "initialize",
            "params": {
                "processId": None,
                "rootUri": root.as_uri(),
                "capabilities": {},
                "workspaceFolders": [{"uri": root.as_uri(), "name": root.name}],
            },
        })
        if initialize.failure:
            return reject(initialize.error or "LSP initialize write failed")
        while cls._INITIALIZE_ID not in response_ids:
            received = receive()
            if received.failure:
                return reject(received.error or "LSP initialize response failed")
            recorded = record(received.value)
            if recorded.failure:
                return reject(recorded.error or "LSP initialize response invalid")
        initialized = send({
            "jsonrpc": c.Infra.JSON_RPC_VERSION,
            "method": "initialized",
            "params": {},
        })
        if initialized.failure:
            return reject(initialized.error or "LSP initialized write failed")
        document_ids: set[int] = set()
        for document_id, path in enumerate(targets, start=cls._DOCUMENT_ID_START):
            document_ids.add(document_id)
            source = u.Cli.files_read_text(path)
            if source.failure:
                return reject(source.error or f"LSP source read failed: {path}")
            messages: t.Pair[t.JsonMapping, t.JsonMapping] = (
                {
                    "jsonrpc": c.Infra.JSON_RPC_VERSION,
                    "method": "textDocument/didOpen",
                    "params": {
                        "textDocument": {
                            "uri": path.as_uri(),
                            "languageId": "python",
                            "version": 1,
                            "text": source.value,
                        }
                    },
                },
                {
                    "jsonrpc": c.Infra.JSON_RPC_VERSION,
                    "id": document_id,
                    "method": "textDocument/documentSymbol",
                    "params": {"textDocument": {"uri": path.as_uri()}},
                },
            )
            for message in messages:
                sent = send(message)
                if sent.failure:
                    return reject(sent.error or f"LSP document write failed: {path}")
        while not document_ids.issubset(response_ids) or not expected_uris.issubset(
            published_uris
        ):
            received = receive()
            if received.failure:
                return reject(received.error or "LSP document response failed")
            recorded = record(received.value)
            if recorded.failure:
                return reject(recorded.error or "LSP document response invalid")
        shutdown = send({
            "jsonrpc": c.Infra.JSON_RPC_VERSION,
            "id": cls._SHUTDOWN_ID,
            "method": "shutdown",
            "params": None,
        })
        if shutdown.failure:
            return reject(shutdown.error or "LSP shutdown write failed")
        while cls._SHUTDOWN_ID not in response_ids:
            received = receive()
            if received.failure:
                return reject(received.error or "LSP shutdown response failed")
            recorded = record(received.value)
            if recorded.failure:
                return reject(recorded.error or "LSP shutdown response invalid")
        exited = send({
            "jsonrpc": c.Infra.JSON_RPC_VERSION,
            "method": "exit",
            "params": None,
        })
        if exited.failure:
            return reject(exited.error or "LSP exit write failed")
        completed = process.wait(timeout=remaining())
        if completed.failure:
            return reject(completed.error or "LSP process wait failed")
        if completed.value != 0:
            return r[bool].fail(
                f"{c.Infra.PYRIGHT_LANGSERVER} exited with code {completed.value}: "
                f"{process.stderr or process.stdout}"
            )
        if process.stderr:
            return r[bool].fail(process.stderr)
        if process.stdout:
            return r[bool].fail(f"unconsumed LSP output: {process.stdout}")
        return r[bool].ok(True)

    @classmethod
    def _frame(cls, payload: t.JsonMapping) -> bytes:
        """Frame one validated JSON-RPC payload for LSP stdio transport."""
        body = u.Cli.json_dumps(dict(payload)).unwrap().encode(c.Cli.ENCODING_DEFAULT)
        return (
            cls._CONTENT_LENGTH
            + b" "
            + str(len(body)).encode(c.Cli.ENCODING_DEFAULT)
            + cls._HEADER_SEPARATOR
            + body
        )


__all__: list[str] = ["FlextInfraLspDiagnosticsDetector"]
