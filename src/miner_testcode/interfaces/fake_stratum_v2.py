from __future__ import annotations

import asyncio
import hashlib
import hmac
import inspect
import json
import math
import secrets
import struct
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from .fake_stratum import STANDARD_COINBASE_1, STANDARD_COINBASE_2


SV2_FRAME_HEADER_SIZE = 6
SV2_MAX_PLAINTEXT_PAYLOAD_SIZE = 2_048
SV2_CHANNEL_MESSAGE = 0x8000

SV2_MSG_SETUP_CONNECTION = 0x00
SV2_MSG_SETUP_CONNECTION_SUCCESS = 0x01
SV2_MSG_OPEN_STANDARD_MINING_CHANNEL = 0x10
SV2_MSG_OPEN_STANDARD_MINING_CHANNEL_SUCCESS = 0x11
SV2_MSG_OPEN_EXTENDED_MINING_CHANNEL = 0x13
SV2_MSG_OPEN_EXTENDED_MINING_CHANNEL_SUCCESS = 0x14
SV2_MSG_NEW_MINING_JOB = 0x15
SV2_MSG_SUBMIT_SHARES_STANDARD = 0x1A
SV2_MSG_SUBMIT_SHARES_EXTENDED = 0x1B
SV2_MSG_SUBMIT_SHARES_SUCCESS = 0x1C
SV2_MSG_SUBMIT_SHARES_ERROR = 0x1D
SV2_MSG_NEW_EXTENDED_MINING_JOB = 0x1F
SV2_MSG_SET_NEW_PREV_HASH = 0x20
SV2_MSG_SET_TARGET = 0x21

_MESSAGE_NAMES = {
    SV2_MSG_SETUP_CONNECTION: "SetupConnection",
    SV2_MSG_SETUP_CONNECTION_SUCCESS: "SetupConnection.Success",
    SV2_MSG_OPEN_STANDARD_MINING_CHANNEL: "OpenStandardMiningChannel",
    SV2_MSG_OPEN_STANDARD_MINING_CHANNEL_SUCCESS: (
        "OpenStandardMiningChannel.Success"
    ),
    SV2_MSG_OPEN_EXTENDED_MINING_CHANNEL: "OpenExtendedMiningChannel",
    SV2_MSG_OPEN_EXTENDED_MINING_CHANNEL_SUCCESS: (
        "OpenExtendedMiningChannel.Success"
    ),
    SV2_MSG_NEW_MINING_JOB: "NewMiningJob",
    SV2_MSG_NEW_EXTENDED_MINING_JOB: "NewExtendedMiningJob",
    SV2_MSG_SUBMIT_SHARES_STANDARD: "SubmitSharesStandard",
    SV2_MSG_SUBMIT_SHARES_EXTENDED: "SubmitSharesExtended",
    SV2_MSG_SUBMIT_SHARES_SUCCESS: "SubmitShares.Success",
    SV2_MSG_SUBMIT_SHARES_ERROR: "SubmitShares.Error",
    SV2_MSG_SET_NEW_PREV_HASH: "SetNewPrevHash",
    SV2_MSG_SET_TARGET: "SetTarget",
}

_NOISE_PROTOCOL_NAME = b"Noise_NX_Secp256k1+EllSwift_ChaChaPoly_SHA256"
_SECP256K1_FIELD = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_SECP256K1_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_DIFFICULTY_ONE_TARGET = int(
    "00000000ffff0000000000000000000000000000000000000000000000000000", 16
)
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

_STANDARD_EXTRANONCE_PREFIX = bytes.fromhex("0102030405060708090a0b0c0d0e0f")
_EXTENDED_EXTRANONCE_PREFIX = _STANDARD_EXTRANONCE_PREFIX[:7]
_EXTENDED_EXTRANONCE_SIZE = 8
_COINBASE_PREFIX = bytes.fromhex(STANDARD_COINBASE_1)
_COINBASE_SUFFIX = bytes.fromhex(STANDARD_COINBASE_2)
_STANDARD_MERKLE_ROOT = hashlib.sha256(
    hashlib.sha256(
        _COINBASE_PREFIX + _STANDARD_EXTRANONCE_PREFIX + _COINBASE_SUFFIX
    ).digest()
).digest()


class Sv2ProtocolError(ValueError):
    """A malformed, unauthenticated, or unexpected SV2 message."""


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _tagged_hash(tag: bytes, data: bytes) -> bytes:
    tag_hash = _sha256(tag)
    return _sha256(tag_hash + tag_hash + data)


def _hkdf2(chaining_key: bytes, input_key_material: bytes) -> tuple[bytes, bytes]:
    temporary = hmac.new(
        chaining_key, input_key_material, hashlib.sha256
    ).digest()
    first = hmac.new(temporary, b"\x01", hashlib.sha256).digest()
    second = hmac.new(temporary, first + b"\x02", hashlib.sha256).digest()
    return first, second


def _mix_hash(current: bytes, data: bytes) -> bytes:
    return _sha256(current + data)


def _field_inverse(value: int) -> int:
    value %= _SECP256K1_FIELD
    if value == 0:
        raise Sv2ProtocolError("EllSwift field division by zero")
    return pow(value, -1, _SECP256K1_FIELD)


def _field_divide(numerator: int, denominator: int) -> int:
    return numerator * _field_inverse(denominator) % _SECP256K1_FIELD


def _field_sqrt(value: int) -> int | None:
    value %= _SECP256K1_FIELD
    root = pow(value, (_SECP256K1_FIELD + 1) // 4, _SECP256K1_FIELD)
    return root if root * root % _SECP256K1_FIELD == value else None


def _valid_x(value: int) -> bool:
    return _field_sqrt(pow(value, 3, _SECP256K1_FIELD) + 7) is not None


_MINUS_THREE_SQRT = _field_sqrt(-3)
assert _MINUS_THREE_SQRT is not None


def _ellswift_decode(encoded: bytes) -> int:
    """Decode a BIP324 EllSwift encoding to a secp256k1 X coordinate."""
    if len(encoded) != 64:
        raise Sv2ProtocolError("EllSwift public key must be 64 bytes")
    u = int.from_bytes(encoded[:32], "big") % _SECP256K1_FIELD or 1
    t = int.from_bytes(encoded[32:], "big") % _SECP256K1_FIELD or 1
    if (pow(u, 3, _SECP256K1_FIELD) + t * t + 7) % _SECP256K1_FIELD == 0:
        t = 2 * t % _SECP256K1_FIELD
    x_value = _field_divide(
        pow(u, 3, _SECP256K1_FIELD) + 7 - t * t,
        2 * t,
    )
    y_value = _field_divide(
        x_value + t,
        int(_MINUS_THREE_SQRT) * u,
    )
    candidates = (
        u + 4 * y_value * y_value,
        _field_divide(-_field_divide(x_value, y_value) - u, 2),
        _field_divide(_field_divide(x_value, y_value) - u, 2),
    )
    for candidate in candidates:
        candidate %= _SECP256K1_FIELD
        if _valid_x(candidate):
            return candidate
    raise Sv2ProtocolError("EllSwift public key does not decode")


def _ellswift_inverse(x_value: int, u: int, case: int) -> int | None:
    """Find one EllSwift encoding component using the BIP324 inverse map."""
    p = _SECP256K1_FIELD
    x_value %= p
    u %= p
    if case & 2 == 0:
        if _valid_x(-x_value - u):
            return None
        v = x_value
        denominator = (u * u + u * v + v * v) % p
        if denominator == 0:
            return None
        s_value = _field_divide(-(pow(u, 3, p) + 7), denominator)
    else:
        s_value = (x_value - u) % p
        if s_value == 0:
            return None
        radicand = (
            -s_value
            * (4 * (pow(u, 3, p) + 7) + 3 * s_value * u * u)
        ) % p
        root = _field_sqrt(radicand)
        if root is None or (case & 1 and root == 0):
            return None
        v = _field_divide(-u + _field_divide(root, s_value), 2)
    w_value = _field_sqrt(s_value)
    if w_value is None:
        return None
    minus_three_sqrt = int(_MINUS_THREE_SQRT)
    if case & 5 == 0:
        return -w_value * (_field_divide(u * (1 - minus_three_sqrt), 2) + v) % p
    if case & 5 == 1:
        return w_value * (_field_divide(u * (1 + minus_three_sqrt), 2) + v) % p
    if case & 5 == 4:
        return w_value * (_field_divide(u * (1 - minus_three_sqrt), 2) + v) % p
    return -w_value * (_field_divide(u * (1 + minus_three_sqrt), 2) + v) % p


@dataclass(frozen=True, slots=True)
class _EllSwiftKey:
    private_key: ec.EllipticCurvePrivateKey
    encoded_public_key: bytes


def _generate_ellswift_key() -> _EllSwiftKey:
    private_value = secrets.randbelow(_SECP256K1_ORDER - 1) + 1
    private_key = ec.derive_private_key(private_value, ec.SECP256K1())
    x_value = private_key.public_key().public_numbers().x
    for _ in range(1_024):
        u = secrets.randbelow(_SECP256K1_FIELD - 1) + 1
        case = secrets.randbelow(8)
        t = _ellswift_inverse(x_value, u, case)
        if t is None:
            continue
        encoded = u.to_bytes(32, "big") + t.to_bytes(32, "big")
        if _ellswift_decode(encoded) == x_value:
            return _EllSwiftKey(private_key, encoded)
    raise RuntimeError("failed to create EllSwift public key within attempt bound")


def _ellswift_xdh(
    private_key: ec.EllipticCurvePrivateKey,
    initiator_key: bytes,
    responder_key: bytes,
    *,
    responder: bool,
) -> bytes:
    remote_encoded = initiator_key if responder else responder_key
    remote_x = _ellswift_decode(remote_encoded)
    remote_y = _field_sqrt(pow(remote_x, 3, _SECP256K1_FIELD) + 7)
    if remote_y is None:
        raise Sv2ProtocolError("EllSwift key does not map to secp256k1")
    remote_key = ec.EllipticCurvePublicNumbers(
        remote_x, remote_y, ec.SECP256K1()
    ).public_key()
    shared_x = private_key.exchange(ec.ECDH(), remote_key)
    material = initiator_key + responder_key + shared_x
    return _tagged_hash(b"bip324_ellswift_xonly_ecdh", material)


def _schnorr_sign(private_key: ec.EllipticCurvePrivateKey, message: bytes) -> bytes:
    if len(message) != 32:
        raise ValueError("BIP340 messages must be 32 bytes")
    private_value = private_key.private_numbers().private_value
    public_numbers = private_key.public_key().public_numbers()
    if public_numbers.y & 1:
        private_value = _SECP256K1_ORDER - private_value
    public_x = public_numbers.x.to_bytes(32, "big")
    auxiliary = secrets.token_bytes(32)
    masked = bytes(
        left ^ right
        for left, right in zip(
            private_value.to_bytes(32, "big"),
            _tagged_hash(b"BIP0340/aux", auxiliary),
            strict=True,
        )
    )
    nonce = int.from_bytes(
        _tagged_hash(b"BIP0340/nonce", masked + public_x + message), "big"
    ) % _SECP256K1_ORDER
    if nonce == 0:
        raise RuntimeError("BIP340 nonce generation produced zero")
    nonce_public = ec.derive_private_key(nonce, ec.SECP256K1()).public_key()
    nonce_numbers = nonce_public.public_numbers()
    if nonce_numbers.y & 1:
        nonce = _SECP256K1_ORDER - nonce
    nonce_x = nonce_numbers.x.to_bytes(32, "big")
    challenge = int.from_bytes(
        _tagged_hash(b"BIP0340/challenge", nonce_x + public_x + message), "big"
    ) % _SECP256K1_ORDER
    signature_s = (nonce + challenge * private_value) % _SECP256K1_ORDER
    return nonce_x + signature_s.to_bytes(32, "big")


_SECP256K1_GENERATOR = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)


def _point_add(
    left: tuple[int, int] | None, right: tuple[int, int] | None
) -> tuple[int, int] | None:
    if left is None:
        return right
    if right is None:
        return left
    left_x, left_y = left
    right_x, right_y = right
    if left_x == right_x:
        if (left_y + right_y) % _SECP256K1_FIELD == 0:
            return None
        slope = _field_divide(3 * left_x * left_x, 2 * left_y)
    else:
        slope = _field_divide(right_y - left_y, right_x - left_x)
    result_x = (slope * slope - left_x - right_x) % _SECP256K1_FIELD
    result_y = (slope * (left_x - result_x) - left_y) % _SECP256K1_FIELD
    return result_x, result_y


def _point_multiply(
    scalar: int, point: tuple[int, int]
) -> tuple[int, int] | None:
    result = None
    addend: tuple[int, int] | None = point
    scalar %= _SECP256K1_ORDER
    while scalar:
        if scalar & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        scalar >>= 1
    return result


def _schnorr_verify(public_x: bytes, message: bytes, signature: bytes) -> bool:
    if len(public_x) != 32 or len(message) != 32 or len(signature) != 64:
        return False
    public_value = int.from_bytes(public_x, "big")
    r_value = int.from_bytes(signature[:32], "big")
    s_value = int.from_bytes(signature[32:], "big")
    if (
        public_value >= _SECP256K1_FIELD
        or r_value >= _SECP256K1_FIELD
        or s_value >= _SECP256K1_ORDER
    ):
        return False
    public_y = _field_sqrt(pow(public_value, 3, _SECP256K1_FIELD) + 7)
    if public_y is None:
        return False
    if public_y & 1:
        public_y = _SECP256K1_FIELD - public_y
    challenge = int.from_bytes(
        _tagged_hash(
            b"BIP0340/challenge", signature[:32] + public_x + message
        ),
        "big",
    ) % _SECP256K1_ORDER
    result = _point_add(
        _point_multiply(s_value, _SECP256K1_GENERATOR),
        _point_multiply(
            _SECP256K1_ORDER - challenge, (public_value, public_y)
        ),
    )
    return result is not None and result[1] & 1 == 0 and result[0] == r_value


def _base58check_authority(public_key: bytes) -> str:
    payload = b"\x01\x00" + public_key
    encoded = payload + _sha256(_sha256(payload))[:4]
    value = int.from_bytes(encoded, "big")
    characters = ""
    while value:
        value, remainder = divmod(value, 58)
        characters = _BASE58_ALPHABET[remainder] + characters
    leading_zeroes = len(encoded) - len(encoded.lstrip(b"\x00"))
    return _BASE58_ALPHABET[0] * leading_zeroes + (characters or "1")


def difficulty_to_target(difficulty: float) -> bytes:
    if not math.isfinite(difficulty) or difficulty <= 0:
        raise ValueError("difficulty must be finite and positive")
    target = int(_DIFFICULTY_ONE_TARGET / difficulty)
    target = max(1, min(target, (1 << 256) - 1))
    return target.to_bytes(32, "little")


def target_to_difficulty(target: bytes) -> float:
    if len(target) != 32:
        raise ValueError("target must be 32 bytes")
    value = int.from_bytes(target, "little")
    if value == 0:
        return float(2**32 - 1)
    return _DIFFICULTY_ONE_TARGET / value


def encode_frame(extension_type: int, message_type: int, payload: bytes) -> bytes:
    if not 0 <= extension_type <= 0xFFFF:
        raise ValueError("extension_type must fit U16")
    if not 0 <= message_type <= 0xFF:
        raise ValueError("message_type must fit U8")
    if len(payload) > 0xFFFFFF:
        raise ValueError("SV2 payload exceeds U24")
    length = len(payload)
    return (
        extension_type.to_bytes(2, "little")
        + bytes([message_type])
        + length.to_bytes(3, "little")
        + payload
    )


@dataclass(frozen=True, slots=True)
class Sv2WireFrame:
    extension_type: int
    message_type: int
    payload: bytes

    @property
    def message_name(self) -> str:
        return _MESSAGE_NAMES.get(
            self.message_type, f"unknown-0x{self.message_type:02x}"
        )


class _NoiseTransport:
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        send_key: bytes,
        receive_key: bytes,
        max_payload_size: int,
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.send_key = send_key
        self.receive_key = receive_key
        self.send_nonce = 0
        self.receive_nonce = 0
        self.max_payload_size = max_payload_size
        self._send_lock = asyncio.Lock()

    @staticmethod
    def _nonce(value: int) -> bytes:
        if not 0 <= value < (1 << 64) - 1:
            raise Sv2ProtocolError("Noise nonce exhausted")
        return b"\x00" * 4 + value.to_bytes(8, "little")

    def _encrypt(self, plaintext: bytes) -> bytes:
        ciphertext = ChaCha20Poly1305(self.send_key).encrypt(
            self._nonce(self.send_nonce), plaintext, b""
        )
        self.send_nonce += 1
        return ciphertext

    def _decrypt(self, ciphertext: bytes) -> bytes:
        try:
            plaintext = ChaCha20Poly1305(self.receive_key).decrypt(
                self._nonce(self.receive_nonce), ciphertext, b""
            )
        except Exception as exc:
            raise Sv2ProtocolError("Noise authentication failed") from exc
        self.receive_nonce += 1
        return plaintext

    async def send_frame(
        self,
        extension_type: int,
        message_type: int,
        payload: bytes,
        *,
        fragment_sizes: Sequence[int] | None = None,
    ) -> None:
        if len(payload) > self.max_payload_size:
            raise ValueError("SV2 payload exceeds configured maximum")
        plaintext_header = encode_frame(extension_type, message_type, b"")[:3]
        plaintext_header += len(payload).to_bytes(3, "little")
        async with self._send_lock:
            wire = self._encrypt(plaintext_header)
            if payload:
                wire += self._encrypt(payload)
            if not fragment_sizes:
                self.writer.write(wire)
                await self.writer.drain()
                return
            offset = 0
            for requested_size in fragment_sizes:
                if requested_size <= 0:
                    raise ValueError("fragment sizes must be positive")
                if offset >= len(wire):
                    break
                end = min(offset + requested_size, len(wire))
                self.writer.write(wire[offset:end])
                await self.writer.drain()
                offset = end
            if offset < len(wire):
                self.writer.write(wire[offset:])
                await self.writer.drain()

    async def receive_frame(self) -> Sv2WireFrame:
        encrypted_header = await self.reader.readexactly(SV2_FRAME_HEADER_SIZE + 16)
        header = self._decrypt(encrypted_header)
        if len(header) != SV2_FRAME_HEADER_SIZE:
            raise Sv2ProtocolError("invalid decrypted SV2 header size")
        extension_type = int.from_bytes(header[:2], "little")
        message_type = header[2]
        payload_size = int.from_bytes(header[3:6], "little")
        if payload_size > self.max_payload_size:
            raise Sv2ProtocolError(
                f"SV2 payload length {payload_size} exceeds {self.max_payload_size}"
            )
        payload = b""
        if payload_size:
            encrypted_payload = await self.reader.readexactly(payload_size + 16)
            payload = self._decrypt(encrypted_payload)
        return Sv2WireFrame(extension_type, message_type, payload)


class _PayloadReader:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.offset = 0

    def take(self, length: int) -> bytes:
        if length < 0 or self.offset + length > len(self.payload):
            raise Sv2ProtocolError("truncated SV2 payload")
        result = self.payload[self.offset : self.offset + length]
        self.offset += length
        return result

    def u8(self) -> int:
        return self.take(1)[0]

    def u16(self) -> int:
        return int.from_bytes(self.take(2), "little")

    def u32(self) -> int:
        return int.from_bytes(self.take(4), "little")

    def f32(self) -> float:
        return struct.unpack("<f", self.take(4))[0]

    def string(self) -> str:
        length = self.u8()
        try:
            return self.take(length).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise Sv2ProtocolError("SV2 string is not UTF-8") from exc

    def finish(self) -> None:
        if self.offset != len(self.payload):
            raise Sv2ProtocolError("SV2 payload contains trailing bytes")


@dataclass(frozen=True, slots=True)
class SetupConnection:
    protocol: int
    min_version: int
    max_version: int
    flags: int
    endpoint_host: str
    endpoint_port: int
    vendor: str
    hardware_version: str
    firmware: str
    device_id: str

    @classmethod
    def from_payload(cls, payload: bytes) -> SetupConnection:
        reader = _PayloadReader(payload)
        result = cls(
            protocol=reader.u8(),
            min_version=reader.u16(),
            max_version=reader.u16(),
            flags=reader.u32(),
            endpoint_host=reader.string(),
            endpoint_port=reader.u16(),
            vendor=reader.string(),
            hardware_version=reader.string(),
            firmware=reader.string(),
            device_id=reader.string(),
        )
        reader.finish()
        return result


@dataclass(frozen=True, slots=True)
class OpenMiningChannel:
    channel_type: str
    request_id: int
    user_identity: str
    nominal_hash_rate: float
    maximum_target: bytes
    minimum_extranonce_size: int | None

    @classmethod
    def from_payload(cls, channel_type: str, payload: bytes) -> OpenMiningChannel:
        reader = _PayloadReader(payload)
        request_id = reader.u32()
        user_identity = reader.string()
        nominal_hash_rate = reader.f32()
        maximum_target = reader.take(32)
        minimum_extranonce_size = (
            reader.u16() if channel_type == "extended" else None
        )
        reader.finish()
        if not math.isfinite(nominal_hash_rate) or nominal_hash_rate < 0:
            raise Sv2ProtocolError("invalid nominal hash rate")
        return cls(
            channel_type=channel_type,
            request_id=request_id,
            user_identity=user_identity,
            nominal_hash_rate=nominal_hash_rate,
            maximum_target=maximum_target,
            minimum_extranonce_size=minimum_extranonce_size,
        )


@dataclass(frozen=True, slots=True)
class Sv2ShareSubmission:
    sequence: int
    connection_id: int
    channel_id: int
    sequence_number: int
    job_id: int
    nonce: int
    ntime: int
    version: int
    extranonce: bytes | None


@dataclass(frozen=True, slots=True)
class Sv2MiningJob:
    job_id: int
    prev_hash: bytes = b"\x00" * 32
    version: int = 0x20000000
    nbits: int = 0x1D00FFFF
    ntime: int = 0
    merkle_root: bytes = _STANDARD_MERKLE_ROOT
    coinbase_prefix: bytes = _COINBASE_PREFIX
    coinbase_suffix: bytes = _COINBASE_SUFFIX

    @classmethod
    def standard(cls, job_id: int) -> Sv2MiningJob:
        return cls(job_id=job_id, ntime=int(time.time()) & 0xFFFFFFFF)

    def __post_init__(self) -> None:
        if not 0 <= self.job_id <= 0xFFFFFFFF:
            raise ValueError("job_id must fit U32")
        if len(self.prev_hash) != 32 or len(self.merkle_root) != 32:
            raise ValueError("SV2 hashes must be 32 bytes")
        if len(self.coinbase_prefix) > 0xFFFF or len(self.coinbase_suffix) > 0xFFFF:
            raise ValueError("SV2 coinbase parts must fit B0_64K")


@dataclass(frozen=True, slots=True)
class Sv2FrameRecord:
    sequence: int
    connection_id: int
    received_at: float
    extension_type: int
    message_type: int
    decoded: Mapping[str, Any]

    @property
    def message_name(self) -> str:
        return _MESSAGE_NAMES.get(
            self.message_type, f"unknown-0x{self.message_type:02x}"
        )


@dataclass(frozen=True, slots=True)
class StratumV2Handshake:
    connection_id: int
    setup: SetupConnection
    open_channel: OpenMiningChannel
    channel_id: int


@dataclass(slots=True)
class StratumV2Session:
    connection_id: int
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    connected_at: float
    noise: _NoiseTransport | None = None
    setup: SetupConnection | None = None
    open_channel: OpenMiningChannel | None = None
    channel_id: int | None = None
    current_difficulty: float = 0.0
    closed_at: float | None = None

    @property
    def connected(self) -> bool:
        return self.closed_at is None and not self.writer.is_closing()


SubmissionPolicy = Callable[[Sv2ShareSubmission], bool | Awaitable[bool]]


class FakeStratumV2Server:
    """Bounded encrypted Stratum V2 server for deterministic miner tests."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        initial_difficulty: float = 256.0,
        accept_submissions: bool = True,
        submission_policy: SubmissionPolicy | None = None,
        max_payload_size: int = SV2_MAX_PLAINTEXT_PAYLOAD_SIZE,
        max_events: int = 5_000,
        max_sessions: int = 8,
        handshake_timeout: float = 10.0,
    ) -> None:
        if not 1 <= max_payload_size <= 65_519:
            raise ValueError("max_payload_size must be between 1 and 65519")
        if not 1 <= max_events <= 100_000:
            raise ValueError("max_events must be between 1 and 100000")
        if not 1 <= max_sessions <= 64:
            raise ValueError("max_sessions must be between 1 and 64")
        if handshake_timeout <= 0:
            raise ValueError("handshake_timeout must be positive")
        difficulty_to_target(initial_difficulty)

        self.host = host
        self.requested_port = port
        self.initial_difficulty = initial_difficulty
        self.accept_submissions = accept_submissions
        self.submission_policy = submission_policy
        self.max_payload_size = max_payload_size
        self.max_events = max_events
        self.max_sessions = max_sessions
        self.handshake_timeout = handshake_timeout

        self._authority_private = ec.generate_private_key(ec.SECP256K1())
        authority_x = self._authority_private.public_key().public_numbers().x
        self.authority_public_key = authority_x.to_bytes(32, "big")
        self.authority_public_key_base58 = _base58check_authority(
            self.authority_public_key
        )
        self._static_key = _generate_ellswift_key()
        now = int(time.time())
        certificate_prefix = struct.pack("<HII", 0, max(0, now - 60), now + 86_400)
        static_x = self._static_key.private_key.public_key().public_numbers().x
        signature_hash = _sha256(
            certificate_prefix + static_x.to_bytes(32, "big")
        )
        self._certificate = certificate_prefix + _schnorr_sign(
            self._authority_private, signature_hash
        )

        self._server: asyncio.AbstractServer | None = None
        self._sessions: dict[int, StratumV2Session] = {}
        self._frames: list[Sv2FrameRecord] = []
        self._submissions: list[Sv2ShareSubmission] = []
        self._events: list[dict[str, Any]] = []
        self._condition = asyncio.Condition()
        self._next_connection_id = 1
        self._next_sequence = 1
        self._client_tasks: set[asyncio.Task[None]] = set()

    async def __aenter__(self) -> FakeStratumV2Server:
        await self.start()
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.close()

    @property
    def port(self) -> int:
        if self._server is None or not self._server.sockets:
            raise RuntimeError("fake Stratum V2 server is not running")
        return int(self._server.sockets[0].getsockname()[1])

    @property
    def frames(self) -> tuple[Sv2FrameRecord, ...]:
        return tuple(self._frames)

    @property
    def submissions(self) -> tuple[Sv2ShareSubmission, ...]:
        return tuple(self._submissions)

    @property
    def sessions(self) -> tuple[StratumV2Session, ...]:
        return tuple(self._sessions.values())

    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = await asyncio.start_server(
            self._client_connected, self.host, self.requested_port
        )
        await self._record_event("server_started")

    async def close(self) -> None:
        server, self._server = self._server, None
        if server is not None:
            server.close()
        for session in self._sessions.values():
            session.writer.close()
        tasks = list(self._client_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if server is not None:
            await server.wait_closed()

    def _client_connected(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        if len(self._sessions) >= self.max_sessions:
            writer.close()
            return
        task = asyncio.create_task(
            self._serve_client(reader, writer), name="fake-stratum-v2-client"
        )
        self._client_tasks.add(task)
        task.add_done_callback(self._client_tasks.discard)

    async def _serve_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        connection_id = self._next_connection_id
        self._next_connection_id += 1
        session = StratumV2Session(
            connection_id=connection_id,
            reader=reader,
            writer=writer,
            connected_at=time.time(),
            current_difficulty=self.initial_difficulty,
        )
        self._sessions[connection_id] = session
        await self._record_event("client_connected", connection_id=connection_id)
        try:
            async with asyncio.timeout(self.handshake_timeout):
                session.noise = await self._noise_handshake(reader, writer)
                await self._record_event(
                    "noise_handshake_complete", connection_id=connection_id
                )
                setup_frame = await session.noise.receive_frame()
                if (
                    setup_frame.extension_type != 0
                    or setup_frame.message_type != SV2_MSG_SETUP_CONNECTION
                ):
                    raise Sv2ProtocolError("expected SetupConnection")
                setup = SetupConnection.from_payload(setup_frame.payload)
                if (
                    setup.protocol != 0
                    or not setup.min_version <= 2 <= setup.max_version
                ):
                    raise Sv2ProtocolError("unsupported SV2 mining protocol version")
                session.setup = setup
                await self._record_frame(
                    session, setup_frame, self._setup_fields(setup)
                )
                await self._send_message(
                    session,
                    0,
                    SV2_MSG_SETUP_CONNECTION_SUCCESS,
                    struct.pack("<HI", 2, 0),
                    fields={"used_version": 2, "flags": 0},
                )

                open_frame = await session.noise.receive_frame()
                if open_frame.extension_type != 0:
                    raise Sv2ProtocolError(
                        "open mining channel must not be a channel message"
                    )
                if open_frame.message_type == SV2_MSG_OPEN_STANDARD_MINING_CHANNEL:
                    channel_type = "standard"
                elif open_frame.message_type == SV2_MSG_OPEN_EXTENDED_MINING_CHANNEL:
                    channel_type = "extended"
                else:
                    raise Sv2ProtocolError("expected an open mining channel request")
                opened = OpenMiningChannel.from_payload(
                    channel_type, open_frame.payload
                )
                session.open_channel = opened
                session.channel_id = (connection_id << 16) | 1
                await self._record_frame(
                    session, open_frame, self._open_channel_fields(opened)
                )
                await self._send_open_success(session)
                async with self._condition:
                    self._condition.notify_all()

            while True:
                assert session.noise is not None
                frame = await session.noise.receive_frame()
                await self._handle_frame(session, frame)
        except asyncio.CancelledError:
            raise
        except asyncio.IncompleteReadError:
            pass
        except (ConnectionError, BrokenPipeError):
            pass
        except Exception as exc:
            try:
                await self._record_event(
                    "client_error",
                    connection_id=connection_id,
                    error=type(exc).__name__,
                )
            except RuntimeError:
                pass
        finally:
            session.closed_at = time.time()
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=1.0)
            except (ConnectionError, TimeoutError):
                pass
            try:
                await self._record_event(
                    "client_disconnected", connection_id=connection_id
                )
            except RuntimeError:
                pass

    async def _noise_handshake(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> _NoiseTransport:
        handshake_hash = _sha256(_NOISE_PROTOCOL_NAME)
        chaining_key = handshake_hash
        handshake_hash = _mix_hash(handshake_hash, b"")
        initiator_key = await reader.readexactly(64)
        _ellswift_decode(initiator_key)
        handshake_hash = _mix_hash(handshake_hash, initiator_key)
        handshake_hash = _mix_hash(handshake_hash, b"")

        ephemeral = _generate_ellswift_key()
        response = ephemeral.encoded_public_key
        handshake_hash = _mix_hash(handshake_hash, ephemeral.encoded_public_key)
        shared_ephemeral = _ellswift_xdh(
            ephemeral.private_key,
            initiator_key,
            ephemeral.encoded_public_key,
            responder=True,
        )
        chaining_key, temporary_key = _hkdf2(
            chaining_key, shared_ephemeral
        )
        encrypted_static = ChaCha20Poly1305(temporary_key).encrypt(
            b"\x00" * 12,
            self._static_key.encoded_public_key,
            handshake_hash,
        )
        response += encrypted_static
        handshake_hash = _mix_hash(handshake_hash, encrypted_static)
        shared_static = _ellswift_xdh(
            self._static_key.private_key,
            initiator_key,
            self._static_key.encoded_public_key,
            responder=True,
        )
        chaining_key, temporary_key = _hkdf2(chaining_key, shared_static)
        response += ChaCha20Poly1305(temporary_key).encrypt(
            b"\x00" * 12, self._certificate, handshake_hash
        )
        if len(response) != 234:
            raise RuntimeError("invalid Noise responder act size")
        writer.write(response)
        await writer.drain()
        initiator_to_responder, responder_to_initiator = _hkdf2(
            chaining_key, b""
        )
        return _NoiseTransport(
            reader,
            writer,
            send_key=responder_to_initiator,
            receive_key=initiator_to_responder,
            max_payload_size=self.max_payload_size,
        )

    async def _send_open_success(self, session: StratumV2Session) -> None:
        opened = session.open_channel
        channel_id = session.channel_id
        assert opened is not None and channel_id is not None
        target = difficulty_to_target(session.current_difficulty)
        if opened.channel_type == "standard":
            payload = (
                struct.pack("<II", opened.request_id, channel_id)
                + target
                + bytes([len(_STANDARD_EXTRANONCE_PREFIX)])
                + _STANDARD_EXTRANONCE_PREFIX
                + struct.pack("<I", 0)
            )
            message_type = SV2_MSG_OPEN_STANDARD_MINING_CHANNEL_SUCCESS
        else:
            if (
                opened.minimum_extranonce_size is not None
                and opened.minimum_extranonce_size > _EXTENDED_EXTRANONCE_SIZE
            ):
                raise Sv2ProtocolError("requested extranonce exceeds test server bound")
            payload = (
                struct.pack("<II", opened.request_id, channel_id)
                + target
                + struct.pack("<H", _EXTENDED_EXTRANONCE_SIZE)
                + bytes([len(_EXTENDED_EXTRANONCE_PREFIX)])
                + _EXTENDED_EXTRANONCE_PREFIX
                + struct.pack("<I", 0)
            )
            message_type = SV2_MSG_OPEN_EXTENDED_MINING_CHANNEL_SUCCESS
        await self._send_message(
            session,
            0,
            message_type,
            payload,
            fields={
                "request_id": opened.request_id,
                "channel_id": channel_id,
                "difficulty": session.current_difficulty,
                "channel_type": opened.channel_type,
            },
        )

    async def _handle_frame(
        self, session: StratumV2Session, frame: Sv2WireFrame
    ) -> None:
        if frame.message_type not in {
            SV2_MSG_SUBMIT_SHARES_STANDARD,
            SV2_MSG_SUBMIT_SHARES_EXTENDED,
        }:
            await self._record_frame(session, frame, {})
            return
        if frame.extension_type != SV2_CHANNEL_MESSAGE:
            raise Sv2ProtocolError("share submission must be a channel message")
        submission = self._parse_submission(session, frame)
        await self._record_frame(
            session,
            frame,
            {
                "channel_id": submission.channel_id,
                "sequence_number": submission.sequence_number,
                "job_id": submission.job_id,
                "nonce": submission.nonce,
                "ntime": submission.ntime,
                "version": submission.version,
                "extranonce_size": (
                    len(submission.extranonce)
                    if submission.extranonce is not None
                    else None
                ),
            },
        )
        async with self._condition:
            self._submissions.append(submission)
            self._condition.notify_all()
        accepted = self.accept_submissions
        if self.submission_policy is not None:
            decision = self.submission_policy(submission)
            accepted = bool(
                await decision if inspect.isawaitable(decision) else decision
            )
        if accepted:
            payload = struct.pack(
                "<IIIQ",
                submission.channel_id,
                submission.sequence_number,
                1,
                max(1, int(round(session.current_difficulty))),
            )
            await self._send_message(
                session,
                SV2_CHANNEL_MESSAGE,
                SV2_MSG_SUBMIT_SHARES_SUCCESS,
                payload,
                fields={
                    "channel_id": submission.channel_id,
                    "last_sequence_number": submission.sequence_number,
                    "accepted_count": 1,
                },
            )
        else:
            error_code = b"low-difficulty-share"
            payload = (
                struct.pack(
                    "<II", submission.channel_id, submission.sequence_number
                )
                + bytes([len(error_code)])
                + error_code
            )
            await self._send_message(
                session,
                SV2_CHANNEL_MESSAGE,
                SV2_MSG_SUBMIT_SHARES_ERROR,
                payload,
                fields={
                    "channel_id": submission.channel_id,
                    "sequence_number": submission.sequence_number,
                    "error_code": error_code.decode(),
                },
            )

    def _parse_submission(
        self, session: StratumV2Session, frame: Sv2WireFrame
    ) -> Sv2ShareSubmission:
        opened = session.open_channel
        if opened is None:
            raise Sv2ProtocolError("share submitted before channel open")
        expected_type = (
            SV2_MSG_SUBMIT_SHARES_STANDARD
            if opened.channel_type == "standard"
            else SV2_MSG_SUBMIT_SHARES_EXTENDED
        )
        if frame.message_type != expected_type:
            raise Sv2ProtocolError("share type does not match opened channel")
        reader = _PayloadReader(frame.payload)
        channel_id = reader.u32()
        sequence_number = reader.u32()
        job_id = reader.u32()
        nonce = reader.u32()
        ntime = reader.u32()
        version = reader.u32()
        extranonce = None
        if opened.channel_type == "extended":
            extranonce = reader.take(reader.u8())
            if len(extranonce) != _EXTENDED_EXTRANONCE_SIZE:
                raise Sv2ProtocolError("invalid submitted extranonce size")
        reader.finish()
        if channel_id != session.channel_id:
            raise Sv2ProtocolError("submission uses unknown channel")
        return Sv2ShareSubmission(
            sequence=self._next_sequence,
            connection_id=session.connection_id,
            channel_id=channel_id,
            sequence_number=sequence_number,
            job_id=job_id,
            nonce=nonce,
            ntime=ntime,
            version=version,
            extranonce=extranonce,
        )

    async def send_target(
        self,
        difficulty: float,
        *,
        session: StratumV2Session | int | None = None,
        fragment_sizes: Sequence[int] | None = None,
    ) -> None:
        target_session = self._resolve_session(session)
        assert target_session.channel_id is not None
        target = difficulty_to_target(difficulty)
        target_session.current_difficulty = difficulty
        await self._send_message(
            target_session,
            SV2_CHANNEL_MESSAGE,
            SV2_MSG_SET_TARGET,
            struct.pack("<I", target_session.channel_id) + target,
            fields={
                "channel_id": target_session.channel_id,
                "difficulty": difficulty,
            },
            fragment_sizes=fragment_sizes,
        )

    async def send_job(
        self,
        job: Sv2MiningJob,
        *,
        difficulty: float | None = None,
        session: StratumV2Session | int | None = None,
        fragment_sizes: Sequence[int] | None = None,
    ) -> None:
        target_session = self._resolve_session(session)
        opened = target_session.open_channel
        channel_id = target_session.channel_id
        assert opened is not None and channel_id is not None
        if difficulty is not None:
            await self.send_target(difficulty, session=target_session)
        if opened.channel_type == "standard":
            payload = (
                struct.pack("<II", channel_id, job.job_id)
                + b"\x00"
                + struct.pack("<I", job.version)
                + job.merkle_root
            )
            message_type = SV2_MSG_NEW_MINING_JOB
        else:
            payload = (
                struct.pack("<II", channel_id, job.job_id)
                + b"\x00"
                + struct.pack("<I", job.version)
                + b"\x01"
                + b"\x00"
                + struct.pack("<H", len(job.coinbase_prefix))
                + job.coinbase_prefix
                + struct.pack("<H", len(job.coinbase_suffix))
                + job.coinbase_suffix
            )
            message_type = SV2_MSG_NEW_EXTENDED_MINING_JOB
        await self._send_message(
            target_session,
            SV2_CHANNEL_MESSAGE,
            message_type,
            payload,
            fields={
                "channel_id": channel_id,
                "job_id": job.job_id,
                "future": True,
            },
            fragment_sizes=fragment_sizes,
        )
        prev_hash_payload = (
            struct.pack("<II", channel_id, job.job_id)
            + job.prev_hash
            + struct.pack("<II", job.ntime, job.nbits)
        )
        await self._send_message(
            target_session,
            SV2_CHANNEL_MESSAGE,
            SV2_MSG_SET_NEW_PREV_HASH,
            prev_hash_payload,
            fields={
                "channel_id": channel_id,
                "job_id": job.job_id,
                "ntime": job.ntime,
                "nbits": job.nbits,
            },
        )

    async def disconnect(
        self, session: StratumV2Session | int | None = None
    ) -> None:
        target = self._resolve_session(session)
        target.writer.close()
        await asyncio.gather(target.writer.wait_closed(), return_exceptions=True)

    async def wait_for_connection(
        self, *, after_connection_id: int = 0, timeout: float = 10.0
    ) -> StratumV2Session:
        async with asyncio.timeout(timeout):
            async with self._condition:
                while True:
                    candidates = [
                        item
                        for item in self._sessions.values()
                        if item.connection_id > after_connection_id
                    ]
                    if candidates:
                        return min(candidates, key=lambda item: item.connection_id)
                    await self._condition.wait()

    async def wait_for_noise_handshake(
        self, *, connection_id: int | None = None, timeout: float = 10.0
    ) -> StratumV2Session:
        async with asyncio.timeout(timeout):
            async with self._condition:
                while True:
                    candidates = [
                        item
                        for item in self._sessions.values()
                        if item.noise is not None
                        and (
                            connection_id is None
                            or item.connection_id == connection_id
                        )
                    ]
                    if candidates:
                        return max(candidates, key=lambda item: item.connection_id)
                    await self._condition.wait()

    async def wait_for_frame(
        self,
        message_type: int,
        *,
        connection_id: int | None = None,
        after_sequence: int = 0,
        timeout: float = 10.0,
    ) -> Sv2FrameRecord:
        async with asyncio.timeout(timeout):
            async with self._condition:
                while True:
                    for frame in self._frames:
                        if frame.sequence <= after_sequence:
                            continue
                        if frame.message_type != message_type:
                            continue
                        if (
                            connection_id is not None
                            and frame.connection_id != connection_id
                        ):
                            continue
                        return frame
                    await self._condition.wait()

    async def wait_for_handshake(
        self,
        *,
        connection_id: int | None = None,
        after_connection_id: int = 0,
        timeout: float = 15.0,
    ) -> StratumV2Handshake:
        async with asyncio.timeout(timeout):
            async with self._condition:
                while True:
                    for session in self._sessions.values():
                        if session.connection_id <= after_connection_id:
                            continue
                        if (
                            connection_id is not None
                            and session.connection_id != connection_id
                        ):
                            continue
                        if (
                            session.setup is not None
                            and session.open_channel is not None
                            and session.channel_id is not None
                        ):
                            return StratumV2Handshake(
                                connection_id=session.connection_id,
                                setup=session.setup,
                                open_channel=session.open_channel,
                                channel_id=session.channel_id,
                            )
                    await self._condition.wait()

    async def wait_for_submission(
        self,
        *,
        job_id: int | None = None,
        connection_id: int | None = None,
        after_sequence: int = 0,
        timeout: float = 30.0,
    ) -> Sv2ShareSubmission:
        async with asyncio.timeout(timeout):
            async with self._condition:
                while True:
                    for submission in self._submissions:
                        if submission.sequence <= after_sequence:
                            continue
                        if job_id is not None and submission.job_id != job_id:
                            continue
                        if (
                            connection_id is not None
                            and submission.connection_id != connection_id
                        ):
                            continue
                        return submission
                    await self._condition.wait()

    async def assert_no_submission(
        self,
        *,
        job_id: int,
        after_sequence: int = 0,
        duration: float = 1.0,
    ) -> None:
        try:
            submission = await self.wait_for_submission(
                job_id=job_id,
                after_sequence=after_sequence,
                timeout=duration,
            )
        except TimeoutError:
            return
        raise AssertionError(
            f"unexpected SV2 submission for job {submission.job_id}"
        )

    def write_transcript(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            "".join(
                json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
                for event in self._events
            ),
            encoding="utf-8",
        )

    def _resolve_session(
        self, session: StratumV2Session | int | None
    ) -> StratumV2Session:
        if isinstance(session, StratumV2Session):
            target = session
        elif isinstance(session, int):
            target = self._sessions.get(session)
            if target is None:
                raise LookupError(f"unknown Stratum V2 connection {session}")
        else:
            connected = [item for item in self._sessions.values() if item.connected]
            if not connected:
                raise RuntimeError("no connected Stratum V2 client")
            target = max(connected, key=lambda item: item.connection_id)
        if not target.connected or target.noise is None or target.channel_id is None:
            raise ConnectionError(
                f"Stratum V2 connection {target.connection_id} is not ready"
            )
        return target

    async def _send_message(
        self,
        session: StratumV2Session,
        extension_type: int,
        message_type: int,
        payload: bytes,
        *,
        fields: Mapping[str, Any],
        fragment_sizes: Sequence[int] | None = None,
    ) -> None:
        if session.noise is None:
            raise ConnectionError("Noise handshake is not complete")
        await session.noise.send_frame(
            extension_type,
            message_type,
            payload,
            fragment_sizes=fragment_sizes,
        )
        await self._record_event(
            "server_sent",
            connection_id=session.connection_id,
            message=_MESSAGE_NAMES.get(message_type, f"unknown-0x{message_type:02x}"),
            extension_type=extension_type,
            payload=dict(fields),
            size=len(payload),
        )

    async def _record_frame(
        self,
        session: StratumV2Session,
        frame: Sv2WireFrame,
        decoded: Mapping[str, Any],
    ) -> Sv2FrameRecord:
        sequence = self._next_sequence
        self._next_sequence += 1
        record = Sv2FrameRecord(
            sequence=sequence,
            connection_id=session.connection_id,
            received_at=time.time(),
            extension_type=frame.extension_type,
            message_type=frame.message_type,
            decoded=dict(decoded),
        )
        async with self._condition:
            if len(self._events) >= self.max_events:
                raise RuntimeError("fake Stratum V2 event limit reached")
            self._frames.append(record)
            self._events.append(
                {
                    "at": record.received_at,
                    "event": "client_message",
                    "sequence": sequence,
                    "connection_id": session.connection_id,
                    "extension_type": frame.extension_type,
                    "message": record.message_name,
                    "size": len(frame.payload),
                    "payload": self._sanitize_fields(decoded),
                }
            )
            self._condition.notify_all()
        return record

    async def _record_event(self, event: str, **fields: Any) -> None:
        async with self._condition:
            if len(self._events) >= self.max_events:
                raise RuntimeError("fake Stratum V2 event limit reached")
            self._events.append({"at": time.time(), "event": event, **fields})
            self._condition.notify_all()

    @staticmethod
    def _setup_fields(setup: SetupConnection) -> dict[str, Any]:
        return {
            "protocol": setup.protocol,
            "min_version": setup.min_version,
            "max_version": setup.max_version,
            "flags": setup.flags,
            "endpoint_host": setup.endpoint_host,
            "endpoint_port": setup.endpoint_port,
            "vendor": setup.vendor,
            "hardware_version": setup.hardware_version,
            "firmware": setup.firmware,
            "device_id": setup.device_id,
        }

    @staticmethod
    def _open_channel_fields(opened: OpenMiningChannel) -> dict[str, Any]:
        return {
            "channel_type": opened.channel_type,
            "request_id": opened.request_id,
            "user_identity": opened.user_identity,
            "nominal_hash_rate": opened.nominal_hash_rate,
            "minimum_extranonce_size": opened.minimum_extranonce_size,
        }

    @staticmethod
    def _sanitize_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
        private = {"endpoint_host", "endpoint_port", "user_identity", "device_id"}
        return {
            key: "<redacted>" if key in private else value
            for key, value in fields.items()
        }
