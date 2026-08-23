from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Iterable, Mapping

_ADDRESS = re.compile(
    rb"(?i)\b(?:bc1|tb1|npub1)[a-z0-9]{20,}(?:\.[A-Za-z0-9_-]+)?"
)
_KEYED_SECRET = re.compile(
    rb"(?i)(stratum(?:user|password)|pool(?:user|password)|"
    rb"wifi(?:ssid|password)|ssid|macAddr|ipv4|ipv6|password|passwd|"
    rb"token|authorization|api[_-]?key|secret)"
    rb"([\"'=:, ]{1,8})([^\s\"',}]+)"
)
_MAC_ADDRESS = re.compile(rb"(?i)\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b")
_PRIVATE_IPV4 = re.compile(
    rb"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
    rb"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"
)
_LOCAL_PATH = re.compile(
    rb"(?<![A-Za-z0-9])/(?:home|Users|tmp|private|var|dev|usr|opt|etc|run)/"
    rb"(?:[^\s\"'<>])+"
)
_TEXT_SUFFIXES = frozenset({".html", ".json", ".jsonl", ".log", ".txt", ".xml"})
_MAX_RAW_LOG_BYTES = 10 * 1024 * 1024


def _assert_public_log_safe(
    data: bytes,
    *,
    replacements: Mapping[str, str] | None = None,
) -> None:
    scanners = (
        (_ADDRESS, "pool or payout identity"),
        (_MAC_ADDRESS, "MAC address"),
        (_PRIVATE_IPV4, "private IP address"),
        (_LOCAL_PATH, "local path"),
    )
    for pattern, label in scanners:
        if pattern.search(data):
            raise ValueError(f"sanitized runner log still contains a {label}")
    for match in _KEYED_SECRET.finditer(data):
        if match.group(3) != b"<redacted>":
            raise ValueError("sanitized runner log still contains a keyed secret")
    for private in (replacements or {}):
        if private and private.encode("utf-8") in data:
            raise ValueError("sanitized runner log still contains a private replacement key")


def redact_bytes(
    data: bytes,
    *,
    project_root: Path | None = None,
    artifact_root: Path | None = None,
    replacements: Mapping[str, str] | None = None,
) -> bytes:
    path_replacements: list[tuple[Path | None, bytes]] = [
        (artifact_root, b"<artifacts>"),
        (project_root, b""),
    ]
    for root, replacement in path_replacements:
        if root is None:
            continue
        resolved = str(root.resolve()).encode()
        data = data.replace(resolved + b"/", replacement + (b"/" if replacement else b""))
        data = data.replace(resolved, replacement or b".")
    for private, public in sorted(
        (replacements or {}).items(), key=lambda item: len(item[0]), reverse=True
    ):
        if private and private != public:
            pattern = re.compile(
                rb"(?<![A-Za-z0-9])" + re.escape(private.encode()) + rb"(?![A-Za-z0-9])"
            )
            data = pattern.sub(public.encode(), data)
    data = _ADDRESS.sub(b"<redacted-pool-identity>", data)
    data = _KEYED_SECRET.sub(
        lambda match: match.group(1) + match.group(2) + b"<redacted>", data
    )
    data = _MAC_ADDRESS.sub(b"<redacted-mac>", data)
    data = _PRIVATE_IPV4.sub(b"<redacted-private-ip>", data)
    return _LOCAL_PATH.sub(b"<local-path>", data)


def redact_text(
    value: str,
    *,
    project_root: Path | None = None,
    artifact_root: Path | None = None,
    replacements: Mapping[str, str] | None = None,
) -> str:
    return redact_bytes(
        value.encode("utf-8", errors="replace"),
        project_root=project_root,
        artifact_root=artifact_root,
        replacements=replacements,
    ).decode(
        "utf-8", errors="replace"
    )


def redact_file(
    path: Path,
    *,
    project_root: Path | None = None,
    artifact_root: Path | None = None,
    replacements: Mapping[str, str] | None = None,
) -> None:
    if not path.is_file():
        return
    original = path.read_bytes()
    redacted = redact_bytes(
        original,
        project_root=project_root,
        artifact_root=artifact_root,
        replacements=replacements,
    )
    if redacted != original:
        path.write_bytes(redacted)


def sanitize_artifacts(
    root: Path,
    *,
    project_root: Path,
    extra_suffixes: Iterable[str] = (),
    replacements: Mapping[str, str] | None = None,
) -> None:
    suffixes = _TEXT_SUFFIXES.union(extra_suffixes)
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in suffixes:
            redact_file(
                path,
                project_root=project_root,
                artifact_root=root,
                replacements=replacements,
            )


def publish_sanitized_log(
    raw_path: Path,
    public_root: Path,
    *,
    project_root: Path,
    replacements: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Create and independently verify the only runner log eligible for publication."""
    with raw_path.open("rb") as stream:
        raw = stream.read(_MAX_RAW_LOG_BYTES + 1)
    if len(raw) > _MAX_RAW_LOG_BYTES:
        raise ValueError("raw runner log exceeds 10 MiB")
    sanitized = redact_bytes(
        raw,
        project_root=project_root,
        artifact_root=public_root,
        replacements=replacements,
    )
    # A second redaction pass must be a no-op. This is deliberately independent
    # of whether the first pass happened to change the input.
    if redact_bytes(
        sanitized,
        project_root=project_root,
        artifact_root=public_root,
        replacements=replacements,
    ) != sanitized:
        raise ValueError("sanitized runner log failed the independent privacy scan")
    _assert_public_log_safe(sanitized, replacements=replacements)
    digest = hashlib.sha256(sanitized).hexdigest()
    log_path = public_root / "public-logs" / f"{digest}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{digest}.",
            suffix=".tmp",
            dir=log_path.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(sanitized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, log_path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    log_path.chmod(0o600)
    # Keep the stable compatibility filename as a byte-for-byte copy of the
    # digest-addressed public artifact; the private raw file remains elsewhere.
    compatibility = public_root / "runner.log"
    compatibility.write_bytes(sanitized)
    compatibility.chmod(0o600)
    descriptor: dict[str, object] = {
        "version": 1,
        "path": log_path.relative_to(public_root).as_posix(),
        "size_bytes": len(sanitized),
        "sha256": digest,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "redaction_profile": "mining-qa-v1",
    }
    descriptor_path = public_root / "sanitized-log.json"
    descriptor_path.write_text(
        json.dumps(descriptor, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    descriptor_path.chmod(0o600)
    return descriptor


class PrivacyFormatter(logging.Formatter):
    def __init__(
        self,
        fmt: str,
        *,
        project_root: Path,
        artifact_root: Path,
        replacements: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(fmt)
        self.project_root = project_root
        self.artifact_root = artifact_root
        self.replacements = replacements

    def format(self, record: logging.LogRecord) -> str:
        return redact_text(
            super().format(record),
            project_root=self.project_root,
            artifact_root=self.artifact_root,
            replacements=self.replacements,
        )
