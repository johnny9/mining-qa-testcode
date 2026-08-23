from __future__ import annotations

import argparse
import ipaddress
import json
import os
import signal
import socket
import tempfile
import threading
import time
from copy import deepcopy
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit


MAX_BODY_BYTES = 64 * 1024
MAX_EVENTS = 2_000
MAX_EVENT_BYTES = 2 * 1024 * 1024
SCENARIOS = frozenset(
    {
        "pass",
        "test-failure",
        "identity-mismatch",
        "http-unavailable",
        "malformed-info",
        "restart-never-returns",
        "cleanup-restore-rejected",
        "cleanup-restore-mismatch",
        "stratum-disconnect",
        "log-privacy-canary",
    }
)
FAULT_KINDS = frozenset(
    {
        "http_status",
        "drop_connection",
        "delay_ms",
        "malformed_json",
        "reject_patch",
        "ignore_patch",
        "stay_offline_after_restart",
        "stratum_disconnect_stage",
    }
)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class MockState:
    def __init__(self, state_file: Path, events_file: Path) -> None:
        self.state_file = state_file
        self.events_file = events_file
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.stratum_stop = threading.Event()
        self.stratum_thread: threading.Thread | None = None
        self.base_url = ""
        self.process_state = "starting"
        self.sequence = 0
        self.event_bytes = 0
        self.events: list[dict[str, Any]] = []
        self.scenario = "pass"
        self.canaries: tuple[str, ...] = ()
        self.patch_count = 0
        self.lifecycle_started = False
        self.mutating = False
        self.transition_delay_ms = 750
        self.faults: dict[str, dict[str, Any]] = {}
        self.offline_until = 0.0
        self.pending: dict[str, Any] = {}
        self.started_at = time.monotonic()
        self.device = self._baseline()

    @staticmethod
    def _baseline() -> dict[str, Any]:
        return {
            "boardVersion": "602",
            "ASICModel": "BM1370",
            "version": "mock-1.0.0",
            "hashRate": 1000.0,
            "sharesAccepted": 0,
            "sharesRejected": 0,
            "stratumURL": "127.0.0.1",
            "stratumPort": 3333,
            "stratumUser": "integration.worker",
            "stratumPassword": "*****",
            "stratumProtocol": "SV1",
            "stratumTLS": 0,
            "stratumSuggestedDifficulty": 1,
            "miningPaused": False,
            "uptimeSeconds": 1,
            "smallCoreCount": 2040,
        }

    def publish_state(self) -> None:
        _atomic_json(
            self.state_file,
            {
                "contract_version": 1,
                "base_url": self.base_url,
                "pid": os.getpid(),
                "process_state": self.process_state,
                "event_sequence": self.sequence,
            },
        )

    def record(self, kind: str, detail: Mapping[str, Any] | None = None) -> None:
        with self.lock:
            if self.sequence >= MAX_EVENTS:
                raise RuntimeError("mock event count limit exceeded")
            event = {
                "sequence": self.sequence + 1,
                "at": _timestamp(),
                "kind": kind,
                "request_id": f"mock-request-{self.sequence + 1:04d}",
                "detail": dict(detail or {}),
            }
            encoded = (
                json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            if self.event_bytes + len(encoded) > MAX_EVENT_BYTES:
                raise RuntimeError("mock event byte limit exceeded")
            with self.events_file.open("ab") as handle:
                handle.write(encoded)
            self.sequence += 1
            self.event_bytes += len(encoded)
            self.events.append(event)

    def reset(self, scenario: str, canaries: list[str]) -> None:
        if scenario not in SCENARIOS:
            raise ValueError(f"unsupported scenario: {scenario}")
        if len(canaries) > 16 or any(
            not isinstance(item, str) or not 1 <= len(item) <= 200 for item in canaries
        ):
            raise ValueError("privacy_canaries must contain at most 16 bounded strings")
        self.stop_stratum()
        with self.lock:
            self.device = self._baseline()
            self.pending = {}
            self.scenario = scenario
            self.canaries = tuple(canaries)
            self.patch_count = 0
            self.lifecycle_started = False
            self.mutating = False
            self.transition_delay_ms = 750
            self.faults = {}
            self.offline_until = 0.0
            self.started_at = time.monotonic()
            self.sequence = 0
            self.event_bytes = 0
            self.events = []
            self.events_file.parent.mkdir(parents=True, exist_ok=True)
            self.events_file.write_bytes(b"")
            self.record("started", {"scenario": scenario})

    def set_scenario(self, scenario: str, transition_delay_ms: int) -> None:
        if scenario not in SCENARIOS:
            raise ValueError(f"unsupported scenario: {scenario}")
        if (
            isinstance(transition_delay_ms, bool)
            or not isinstance(transition_delay_ms, int)
            or not 0 <= transition_delay_ms <= 2_000
        ):
            raise ValueError("transition_delay_ms must be from 0 through 2000")
        with self.lock:
            if self.lifecycle_started:
                raise PermissionError("scenario_active")
            self.scenario = scenario
            self.transition_delay_ms = transition_delay_ms
            self.record("fault_applied", {"scenario": scenario, "phase": "selected"})

    def set_faults(self, faults: list[Mapping[str, Any]]) -> None:
        if len(faults) > len(FAULT_KINDS):
            raise ValueError("too many faults")
        parsed: dict[str, dict[str, Any]] = {}
        for item in faults:
            if not isinstance(item, Mapping):
                raise ValueError("fault entries must be objects")
            kind = item.get("kind")
            count = item.get("count")
            if kind not in FAULT_KINDS:
                raise ValueError(f"unsupported fault: {kind}")
            if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 100:
                raise ValueError("fault count must be from 1 through 100")
            if kind in parsed:
                raise ValueError("fault kinds must not repeat")
            allowed = {"kind", "count"}
            if kind == "http_status":
                allowed.add("status")
            elif kind == "delay_ms":
                allowed.add("delay_ms")
            elif kind == "stratum_disconnect_stage":
                allowed.add("stage")
            if set(item) - allowed:
                raise ValueError(f"{kind} fault contains unsupported fields")
            value = {"kind": kind, "count": count}
            if kind == "http_status":
                status = item.get("status")
                if isinstance(status, bool) or not isinstance(status, int) or not 400 <= status <= 599:
                    raise ValueError("http_status fault requires status from 400 through 599")
                value["status"] = status
            if kind == "delay_ms":
                delay = item.get("delay_ms")
                if isinstance(delay, bool) or not isinstance(delay, int) or not 0 <= delay <= 2_000:
                    raise ValueError("delay_ms fault requires delay_ms from 0 through 2000")
                value["delay_ms"] = delay
            if kind == "stratum_disconnect_stage":
                stage = item.get("stage")
                if stage not in {"authorize", "notify"}:
                    raise ValueError("stratum_disconnect_stage must be authorize or notify")
                value["stage"] = stage
            parsed[str(kind)] = value
        with self.lock:
            self.faults = parsed

    def consume_fault(self, kind: str) -> dict[str, Any] | None:
        with self.lock:
            fault = self.faults.get(kind)
            if not fault:
                return None
            remaining = int(fault["count"]) - 1
            value = dict(fault)
            if remaining:
                fault["count"] = remaining
            else:
                self.faults.pop(kind, None)
            self.record("fault_applied", {"fault": kind, "remaining": remaining})
            return value

    def sanitized_state(self) -> dict[str, Any]:
        return {
            "miningPaused": bool(self.device.get("miningPaused")),
            "stratumHostClass": "loopback"
            if str(self.device.get("stratumURL")) in {"127.0.0.1", "::1", "localhost"}
            else "non-loopback",
            "stratumPort": int(self.device.get("stratumPort", 0)),
            "stratumProtocol": str(self.device.get("stratumProtocol", "")),
        }

    def public_device(self) -> dict[str, Any]:
        with self.lock:
            value = deepcopy(self.device)
            value["uptimeSeconds"] = max(0, int(time.monotonic() - self.started_at))
            value["stratumPassword"] = "*****"
            if self.scenario == "identity-mismatch":
                value["boardVersion"] = "601"
                value["ASICModel"] = "BZM"
            return value

    def patch(self, value: Mapping[str, Any]) -> None:
        with self.lock:
            self.mutating = True
            previous = self.sanitized_state()
            self.patch_count += 1
            if (
                self.scenario == "cleanup-restore-rejected" and self.patch_count >= 2
            ) or self.consume_fault("reject_patch"):
                self.mutating = False
                self.record("fault_applied", {"fault": "reject_patch", "phase": "cleanup"})
                raise PermissionError("cleanup restore rejected")
            update = dict(value)
            pools = update.pop("pools", None)
            if pools is not None:
                if not isinstance(pools, list) or len(pools) != 1 or not isinstance(pools[0], dict):
                    raise ValueError("pools must contain exactly one object")
                update.update(pools[0])
            allowed = {
                "stratumURL",
                "stratumPort",
                "stratumUser",
                "stratumPassword",
                "stratumProtocol",
                "stratumTLS",
                "stratumSuggestedDifficulty",
                "stratumExtranonceSubscribe",
                "stratumDecodeCoinbase",
                "primaryPoolIndex",
                "secondaryPoolIndex",
                "useFallbackStratum",
            }
            if not update or set(update) - allowed:
                self.mutating = False
                raise ValueError("PATCH contains unsupported fields")
            if not self.consume_fault("ignore_patch"):
                self.pending.update(update)
            next_state = dict(previous)
            if "stratumURL" in update:
                next_state["stratumHostClass"] = "loopback" if str(update["stratumURL"]) in {"127.0.0.1", "::1", "localhost"} else "non-loopback"
            for source, target in (("stratumPort", "stratumPort"), ("stratumProtocol", "stratumProtocol")):
                if source in update:
                    next_state[target] = update[source]
            self.record(
                "settings_patch",
                {"keys": sorted(update), "previous": previous, "next": next_state},
            )
            self.mutating = False

    def restart(self) -> None:
        with self.lock:
            self.device.update(self.pending)
            self.pending = {}
            self.started_at = time.monotonic()
            if self.scenario == "cleanup-restore-mismatch" and self.patch_count >= 2:
                self.device["stratumUser"] = "restore-mismatch"
                self.record("fault_applied", {"fault": "ignore_patch", "phase": "cleanup"})
            self.record("restart", {"patch_count": self.patch_count})
            if self.scenario == "restart-never-returns" or self.consume_fault("stay_offline_after_restart"):
                self.device["hashRate"] = 0.0
                self.record("offline")
                return
            self.offline_until = time.monotonic() + (self.transition_delay_ms / 1000)
            self.record("offline")
        self.start_stratum()

    def stop_stratum(self) -> None:
        self.stratum_stop.set()
        thread, self.stratum_thread = self.stratum_thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        self.stratum_stop = threading.Event()

    def start_stratum(self) -> None:
        self.stop_stratum()
        with self.lock:
            host = str(self.device.get("stratumURL", ""))
            port = int(self.device.get("stratumPort", 0))
            paused = bool(self.device.get("miningPaused", False))
        try:
            if paused or port <= 0 or not ipaddress.ip_address(host).is_loopback:
                return
        except ValueError:
            return
        thread = threading.Thread(
            target=self._stratum_client,
            args=(host, port, self.stratum_stop),
            name="mock-device-stratum",
            daemon=True,
        )
        self.stratum_thread = thread
        thread.start()

    def _stratum_client(self, host: str, port: int, stopped: threading.Event) -> None:
        try:
            with socket.create_connection((host, port), timeout=2.0) as connection:
                connection.settimeout(5.0)
                stream = connection.makefile("rwb", buffering=0)

                def send(payload: Mapping[str, Any]) -> None:
                    stream.write(
                        json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
                    )

                self.record("stratum_connect", {"host": "loopback", "port": port})
                send({"id": 1, "method": "mining.configure", "params": [["version-rolling"], {"version-rolling.mask": "1fffe000"}]})
                send({"id": 2, "method": "mining.subscribe", "params": ["mining-qa-mock/1"]})
                with self.lock:
                    username = str(self.device.get("stratumUser", "integration.worker"))
                send({"id": 3, "method": "mining.authorize", "params": [username, "x"]})
                self.record("stratum_authorize")
                disconnect = self.consume_fault("stratum_disconnect_stage")
                if disconnect and disconnect.get("stage") == "authorize":
                    return
                while not stopped.is_set():
                    try:
                        line = stream.readline(MAX_BODY_BYTES + 1)
                    except TimeoutError:
                        continue
                    if not line:
                        return
                    if len(line) > MAX_BODY_BYTES:
                        return
                    message = json.loads(line)
                    if message.get("method") != "mining.notify":
                        if message.get("id") == 4:
                            accepted = bool(message.get("result")) and self.scenario != "test-failure"
                            with self.lock:
                                key = "sharesAccepted" if accepted else "sharesRejected"
                                self.device[key] = int(self.device.get(key, 0)) + 1
                            self.record("stratum_submit", {"accepted": accepted})
                            return
                        continue
                    params = message.get("params")
                    if not isinstance(params, list) or len(params) < 8:
                        return
                    self.record("stratum_notify", {"job_id": str(params[0])[:64]})
                    if self.scenario == "stratum-disconnect" or (
                        disconnect and disconnect.get("stage") == "notify"
                    ):
                        self.record("fault_applied", {"fault": "stratum_disconnect_stage"})
                        return
                    send(
                        {
                            "id": 4,
                            "method": "mining.submit",
                            "params": [username, params[0], "0000000000000000", params[7], "00000000"],
                        }
                    )
        except (OSError, ValueError, json.JSONDecodeError):
            return


class MockHandler(BaseHTTPRequestHandler):
    server: "MockServer"
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _body(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length < 0 or length > MAX_BODY_BYTES:
            raise OverflowError("request body exceeds 64 KiB")
        raw = self.rfile.read(length)
        value = json.loads(raw or b"{}")
        if not isinstance(value, dict):
            raise ValueError("request body must be an object")
        return value

    def _send(self, status: int, value: Any, *, content_type: str = "application/json") -> None:
        payload = (
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
            if content_type == "application/json"
            else str(value).encode("utf-8")
        )
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)

    def _error(self, status: int, code: str, message: str) -> None:
        self._send(status, {"error": {"code": code, "message": message[:500]}})

    def _fault_response(self) -> bool:
        state = self.server.state
        delay = state.consume_fault("delay_ms")
        if delay:
            time.sleep(float(delay["delay_ms"]) / 1000)
        status = state.consume_fault("http_status")
        if status:
            self._error(int(status["status"]), "fault", "configured HTTP status fault")
            return True
        if state.consume_fault("drop_connection"):
            self.close_connection = True
            return True
        if state.consume_fault("malformed_json"):
            self._send(HTTPStatus.OK, "{malformed", content_type="application/json-invalid")
            return True
        return False

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        state = self.server.state
        try:
            if parsed.path == "/api/system/info":
                state.lifecycle_started = True
                if self._fault_response():
                    return
                if state.scenario == "http-unavailable":
                    self._error(HTTPStatus.SERVICE_UNAVAILABLE, "fault", "device unavailable")
                    return
                if state.scenario == "restart-never-returns" and state.patch_count:
                    self._error(HTTPStatus.SERVICE_UNAVAILABLE, "restarting", "device offline")
                    return
                with state.lock:
                    if time.monotonic() < state.offline_until:
                        self._error(HTTPStatus.SERVICE_UNAVAILABLE, "restarting", "device offline")
                        return
                    if state.offline_until:
                        state.offline_until = 0.0
                        state.record("online")
                state.record("info_read")
                if state.scenario == "malformed-info":
                    self._send(HTTPStatus.OK, {"boardVersion": ["wrong-shape"]})
                else:
                    self._send(HTTPStatus.OK, state.public_device())
                return
            if parsed.path == "/api/system/logs":
                state.record("log_read")
                lines = ["mock device log", *state.canaries]
                self._send(HTTPStatus.OK, "\n".join(lines) + "\n", content_type="text/plain")
                return
            if parsed.path == "/__mock/v1/health":
                self._send(
                    HTTPStatus.OK,
                    {"contract_version": 1, "process_state": state.process_state, "event_sequence": state.sequence},
                )
                return
            if parsed.path == "/__mock/v1/state":
                self._send(
                    HTTPStatus.OK,
                    {
                        "contract_version": 1,
                        "process_state": state.process_state,
                        "scenario": state.scenario,
                        "active_faults": sorted(state.faults.values(), key=lambda item: item["kind"]),
                        "device": state.public_device(),
                        "event_sequence": state.sequence,
                    },
                )
                return
            if parsed.path == "/__mock/v1/events":
                query = parse_qs(parsed.query)
                after = int(query.get("after", ["0"])[0])
                limit = int(query.get("limit", ["200"])[0])
                if after < 0 or not 1 <= limit <= 200:
                    raise ValueError("invalid event query")
                events = [event for event in state.events if event["sequence"] > after][:limit]
                self._send(HTTPStatus.OK, {"contract_version": 1, "events": events})
                return
            self._error(HTTPStatus.NOT_FOUND, "not_found", "unknown endpoint")
        except (ValueError, RuntimeError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, "invalid_request", str(exc))

    def do_PATCH(self) -> None:  # noqa: N802
        state = self.server.state
        try:
            if self.path != "/api/system":
                state.record("unsupported_operation", {"method": "PATCH"})
                self._error(HTTPStatus.CONFLICT, "unsupported_operation", "unsupported operation")
                return
            state.lifecycle_started = True
            if self._fault_response():
                return
            state.patch(self._body())
            self._send(HTTPStatus.OK, {"accepted": True})
        except PermissionError as exc:
            self._error(HTTPStatus.CONFLICT, "restore_rejected", str(exc))
        except OverflowError as exc:
            self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "payload_too_large", str(exc))
        except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, "invalid_request", str(exc))
        finally:
            state.mutating = False

    def do_POST(self) -> None:  # noqa: N802
        state = self.server.state
        try:
            if self.path == "/api/system/restart":
                state.lifecycle_started = True
                if self._fault_response():
                    return
                state.restart()
                self._send(HTTPStatus.OK, {"accepted": True})
                return
            if self.path == "/api/system/pause":
                state.lifecycle_started = True
                with state.lock:
                    state.device["miningPaused"] = True
                    state.device["hashRate"] = 0.0
                    state.record("pause")
                self._send(HTTPStatus.OK, {"accepted": True})
                return
            if self.path == "/api/system/resume":
                state.lifecycle_started = True
                with state.lock:
                    state.device["miningPaused"] = False
                    state.device["hashRate"] = 1000.0
                    state.record("resume")
                state.start_stratum()
                self._send(HTTPStatus.OK, {"accepted": True})
                return
            if self.path == "/__mock/v1/reset":
                if state.mutating:
                    self._error(HTTPStatus.CONFLICT, "mutation_active", "device mutation is active")
                    return
                body = self._body()
                if body.get("contract_version") != 1 or body.get("baseline") != "gamma-running":
                    raise ValueError("reset requires contract_version 1 and gamma-running baseline")
                canaries = body.get("privacy_canaries", [])
                if not isinstance(canaries, list):
                    raise ValueError("privacy_canaries must be an array")
                state.reset(str(body.get("scenario", "")), canaries)
                self._send(HTTPStatus.OK, {"contract_version": 1, "scenario": state.scenario})
                return
            state.record("unsupported_operation", {"method": "POST", "path": self.path[:100]})
            self._error(HTTPStatus.CONFLICT, "unsupported_operation", "unsupported operation")
        except OverflowError as exc:
            self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "payload_too_large", str(exc))
        except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, "invalid_request", str(exc))

    def do_PUT(self) -> None:  # noqa: N802
        state = self.server.state
        try:
            body = self._body()
            if body.get("contract_version") != 1:
                raise ValueError("control body requires contract_version 1")
            if self.path == "/__mock/v1/scenario":
                state.set_scenario(
                    str(body.get("scenario", "")),
                    body.get("transition_delay_ms", 50),
                )
                self._send(HTTPStatus.OK, {"contract_version": 1, "scenario": state.scenario})
                return
            if self.path == "/__mock/v1/faults":
                faults = body.get("faults")
                if not isinstance(faults, list):
                    raise ValueError("faults must be an array")
                state.set_faults(faults)
                self._send(
                    HTTPStatus.OK,
                    {"contract_version": 1, "active_faults": sorted(state.faults.values(), key=lambda item: item["kind"])},
                )
                return
            state.record("unsupported_operation", {"method": "PUT", "path": self.path[:100]})
            self._error(HTTPStatus.CONFLICT, "unsupported_operation", "unsupported operation")
        except PermissionError:
            self._error(HTTPStatus.CONFLICT, "scenario_active", "runner lifecycle already started")
        except OverflowError as exc:
            self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "payload_too_large", str(exc))
        except (TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, "invalid_request", str(exc))

    def do_DELETE(self) -> None:  # noqa: N802
        self.server.state.record("unsupported_operation", {"method": "DELETE", "path": self.path[:100]})
        self._error(HTTPStatus.CONFLICT, "unsupported_operation", "unsupported operation")


class MockServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], state: MockState) -> None:
        self.state = state
        super().__init__(address, MockHandler)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mining-qa-mock-device")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--state-file", required=True)
    parser.add_argument("--events-file", required=True)
    return parser


def _validated_path(value: str) -> Path:
    unresolved = Path(value).expanduser()
    absolute = unresolved.absolute()
    for candidate in (absolute, *absolute.parents):
        if candidate.exists() and candidate.is_symlink():
            raise ValueError(f"path must not contain a symlink: {candidate}")
    path = unresolved.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _validate_bind_host(host: str, port: int) -> None:
    addresses = {
        item[4][0]
        for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    }
    if not addresses or any(
        not ipaddress.ip_address(address).is_loopback for address in addresses
    ):
        raise ValueError("mock device host must resolve only to loopback")
    if not 0 <= port <= 65535:
        raise ValueError("mock device port must be from 0 through 65535")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        _validate_bind_host(args.host, args.port)
        state_file = _validated_path(args.state_file)
        events_file = _validated_path(args.events_file)
        if state_file.parent != events_file.parent:
            raise ValueError("state and event files must share one harness-owned directory")
        if state_file == events_file:
            raise ValueError("state and event files must be distinct")
        state = MockState(state_file, events_file)
        state.reset("pass", [])
        server = MockServer((args.host, args.port), state)
        selected_host, selected_port = server.server_address[:2]
        state.base_url = f"http://{selected_host}:{selected_port}"
        state.process_state = "ready"
        state.publish_state()

        def stop(_signum: int, _frame: object) -> None:
            state.stop_event.set()
            threading.Thread(target=server.shutdown, daemon=True).start()

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        server.serve_forever(poll_interval=0.1)
        state.process_state = "stopping"
        state.stop_stratum()
        state.record("stopped")
        state.process_state = "stopped"
        state.publish_state()
        server.server_close()
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"mining-qa-mock-device: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
