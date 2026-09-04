from __future__ import annotations

import asyncio
import hashlib
import json
import struct
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from miner_testcode.interfaces.fake_stratum_v2 import (
    SV2_CHANNEL_MESSAGE,
    SV2_FRAME_HEADER_SIZE,
    SV2_MSG_NEW_EXTENDED_MINING_JOB,
    SV2_MSG_NEW_MINING_JOB,
    SV2_MSG_OPEN_EXTENDED_MINING_CHANNEL,
    SV2_MSG_OPEN_EXTENDED_MINING_CHANNEL_SUCCESS,
    SV2_MSG_OPEN_STANDARD_MINING_CHANNEL,
    SV2_MSG_OPEN_STANDARD_MINING_CHANNEL_SUCCESS,
    SV2_MSG_SET_NEW_PREV_HASH,
    SV2_MSG_SET_TARGET,
    SV2_MSG_SETUP_CONNECTION,
    SV2_MSG_SETUP_CONNECTION_SUCCESS,
    SV2_MSG_SUBMIT_SHARES_ERROR,
    SV2_MSG_SUBMIT_SHARES_EXTENDED,
    SV2_MSG_SUBMIT_SHARES_STANDARD,
    SV2_MSG_SUBMIT_SHARES_SUCCESS,
    FakeStratumV2Server,
    Sv2MiningJob,
    _generate_ellswift_key,
    _hkdf2,
    _ellswift_decode,
    _ellswift_xdh,
    _mix_hash,
    _NoiseTransport,
    _NOISE_PROTOCOL_NAME,
    _schnorr_verify,
    _sha256,
    difficulty_to_target,
    encode_frame,
    target_to_difficulty,
)


def _string(value: str) -> bytes:
    encoded = value.encode()
    return bytes([len(encoded)]) + encoded


@dataclass(slots=True)
class _TestClient:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    noise: _NoiseTransport
    channel_id: int
    channel_type: str

    async def close(self) -> None:
        self.writer.close()
        await asyncio.gather(self.writer.wait_closed(), return_exceptions=True)


async def _connect_test_client(
    server: FakeStratumV2Server,
    channel_type: str,
    *,
    identity: str = "private-regression.worker",
    endpoint: str = "private-device.local",
    device_id: str = "private-device-id",
) -> _TestClient:
    reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
    initiator = _generate_ellswift_key()
    handshake_hash = _sha256(_NOISE_PROTOCOL_NAME)
    chaining_key = handshake_hash
    handshake_hash = _mix_hash(handshake_hash, b"")
    handshake_hash = _mix_hash(handshake_hash, initiator.encoded_public_key)
    handshake_hash = _mix_hash(handshake_hash, b"")
    writer.write(initiator.encoded_public_key)
    await writer.drain()

    response = await asyncio.wait_for(reader.readexactly(234), timeout=2)
    responder_ephemeral = response[:64]
    handshake_hash = _mix_hash(handshake_hash, responder_ephemeral)
    shared_ephemeral = _ellswift_xdh(
        initiator.private_key,
        initiator.encoded_public_key,
        responder_ephemeral,
        responder=False,
    )
    chaining_key, temporary_key = _hkdf2(chaining_key, shared_ephemeral)
    static_ciphertext = response[64:144]
    responder_static = ChaCha20Poly1305(temporary_key).decrypt(
        b"\x00" * 12, static_ciphertext, handshake_hash
    )
    handshake_hash = _mix_hash(handshake_hash, static_ciphertext)
    shared_static = _ellswift_xdh(
        initiator.private_key,
        initiator.encoded_public_key,
        responder_static,
        responder=False,
    )
    chaining_key, temporary_key = _hkdf2(chaining_key, shared_static)
    certificate = ChaCha20Poly1305(temporary_key).decrypt(
        b"\x00" * 12, response[144:], handshake_hash
    )
    static_x = _ellswift_decode(responder_static).to_bytes(32, "big")
    signature_hash = _sha256(certificate[:10] + static_x)
    if not _schnorr_verify(
        server.authority_public_key, signature_hash, certificate[10:]
    ):
        raise AssertionError("fake server authority certificate did not verify")

    send_key, receive_key = _hkdf2(chaining_key, b"")
    noise = _NoiseTransport(
        reader,
        writer,
        send_key=send_key,
        receive_key=receive_key,
        max_payload_size=server.max_payload_size,
    )
    setup_payload = (
        b"\x00"
        + struct.pack("<HHI", 2, 2, 1 if channel_type == "standard" else 0)
        + _string(endpoint)
        + struct.pack("<H", server.port)
        + _string("bitaxe")
        + _string("BM1370")
        + _string("v-test")
        + _string(device_id)
    )
    await noise.send_frame(0, SV2_MSG_SETUP_CONNECTION, setup_payload)
    setup_success = await asyncio.wait_for(noise.receive_frame(), timeout=2)
    if setup_success.message_type != SV2_MSG_SETUP_CONNECTION_SUCCESS:
        raise AssertionError("server did not accept SetupConnection")

    open_payload = (
        struct.pack("<I", 7)
        + _string(identity)
        + struct.pack("<f", 1.0e12)
        + b"\xff" * 32
    )
    if channel_type == "extended":
        open_payload += struct.pack("<H", 2)
        open_type = SV2_MSG_OPEN_EXTENDED_MINING_CHANNEL
        success_type = SV2_MSG_OPEN_EXTENDED_MINING_CHANNEL_SUCCESS
    else:
        open_type = SV2_MSG_OPEN_STANDARD_MINING_CHANNEL
        success_type = SV2_MSG_OPEN_STANDARD_MINING_CHANNEL_SUCCESS
    await noise.send_frame(0, open_type, open_payload)
    open_success = await asyncio.wait_for(noise.receive_frame(), timeout=2)
    if open_success.message_type != success_type:
        raise AssertionError("server did not accept channel open")
    channel_id = int.from_bytes(open_success.payload[4:8], "little")
    return _TestClient(reader, writer, noise, channel_id, channel_type)


class Sv2PrimitiveTest(unittest.TestCase):
    def test_official_ellswift_decode_vector(self) -> None:
        encoded = bytes(64)
        expected = (
            "edd1fd3e327ce90cc7a3542614289aee9682003e9cf7dcc9cf2ca9743be5aa0c"
        )
        self.assertEqual(_ellswift_decode(encoded).to_bytes(32, "big").hex(), expected)

    def test_official_bip340_verification_vector(self) -> None:
        public_key = bytes.fromhex(
            "F9308A019258C31049344F85F89D5229B531C845836F99B08601F113BCE036F9"
        )
        signature = bytes.fromhex(
            "E907831F80848D1069A5371B402410364BDF1C5F8307B0084C55F1CE2DCA821"
            "525F66A4A85EA8B71E482A74F382D2CE5EBEEE8FDB2172F477DF4900D310536C0"
        )
        self.assertTrue(_schnorr_verify(public_key, bytes(32), signature))
        self.assertFalse(_schnorr_verify(public_key, b"\x01" + bytes(31), signature))

    def test_frame_and_difficulty_bounds(self) -> None:
        payload = b"payload"
        frame = encode_frame(SV2_CHANNEL_MESSAGE, SV2_MSG_SET_TARGET, payload)
        self.assertEqual(len(frame), SV2_FRAME_HEADER_SIZE + len(payload))
        self.assertEqual(frame[:2], b"\x00\x80")
        self.assertEqual(frame[2], SV2_MSG_SET_TARGET)
        self.assertEqual(frame[3:6], len(payload).to_bytes(3, "little"))
        for difficulty in (1, 64, 256, 1_000_000):
            self.assertAlmostEqual(
                target_to_difficulty(difficulty_to_target(difficulty)),
                difficulty,
                delta=difficulty * 1e-10,
            )
        with self.assertRaisesRegex(ValueError, "difficulty"):
            difficulty_to_target(0)
        with self.assertRaisesRegex(ValueError, "max_payload_size"):
            FakeStratumV2Server(max_payload_size=0)

        server = FakeStratumV2Server()
        alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        decoded_value = 0
        for character in server.authority_public_key_base58:
            decoded_value = decoded_value * 58 + alphabet.index(character)
        decoded = decoded_value.to_bytes(38, "big")
        self.assertEqual(decoded[:2], b"\x01\x00")
        self.assertEqual(decoded[2:34], server.authority_public_key)
        checksum = hashlib.sha256(
            hashlib.sha256(decoded[:34]).digest()
        ).digest()[:4]
        self.assertEqual(
            decoded[34:], checksum
        )


class FakeStratumV2ServerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.server = FakeStratumV2Server(initial_difficulty=128)
        await self.server.start()
        self.clients: list[_TestClient] = []

    async def asyncTearDown(self) -> None:
        for client in self.clients:
            await client.close()
        await asyncio.wait_for(self.server.close(), timeout=2)

    async def _connect(self, channel_type: str) -> _TestClient:
        client = await _connect_test_client(self.server, channel_type)
        self.clients.append(client)
        return client

    async def test_standard_channel_job_target_and_accepted_share(self) -> None:
        client = await self._connect("standard")
        handshake = await self.server.wait_for_handshake(timeout=2)
        self.assertEqual(handshake.setup.protocol, 0)
        self.assertEqual(handshake.setup.min_version, 2)
        self.assertEqual(handshake.open_channel.channel_type, "standard")
        self.assertEqual(
            handshake.open_channel.user_identity, "private-regression.worker"
        )

        job = Sv2MiningJob.standard(101)
        await self.server.send_job(
            job,
            difficulty=64,
            session=handshake.connection_id,
            fragment_sizes=(1, 2, 3, 5, 8, 13),
        )
        messages = [
            await asyncio.wait_for(client.noise.receive_frame(), timeout=2)
            for _ in range(3)
        ]
        self.assertEqual(
            [message.message_type for message in messages],
            [SV2_MSG_SET_TARGET, SV2_MSG_NEW_MINING_JOB, SV2_MSG_SET_NEW_PREV_HASH],
        )

        submission_payload = struct.pack(
            "<IIIIII", client.channel_id, 0, job.job_id, 123, job.ntime, job.version
        )
        await client.noise.send_frame(
            SV2_CHANNEL_MESSAGE,
            SV2_MSG_SUBMIT_SHARES_STANDARD,
            submission_payload,
        )
        response = await asyncio.wait_for(client.noise.receive_frame(), timeout=2)
        submission = await self.server.wait_for_submission(job_id=job.job_id, timeout=2)
        self.assertEqual(response.message_type, SV2_MSG_SUBMIT_SHARES_SUCCESS)
        self.assertEqual(submission.sequence_number, 0)
        self.assertIsNone(submission.extranonce)

        with tempfile.TemporaryDirectory() as directory:
            transcript = Path(directory) / "sv2.jsonl"
            self.server.write_transcript(transcript)
            evidence = transcript.read_text(encoding="utf-8")
            events = [json.loads(line) for line in evidence.splitlines()]
        self.assertNotIn("private-regression.worker", evidence)
        self.assertNotIn("private-device.local", evidence)
        self.assertNotIn("private-device-id", evidence)
        self.assertIn("<redacted>", evidence)
        self.assertNotIn("ciphertext", evidence)
        server_started = next(
            event for event in events if event["event"] == "server_started"
        )
        self.assertNotIn("port", server_started)

    async def test_extended_channel_job_and_rejected_share(self) -> None:
        self.server.submission_policy = lambda _submission: False
        client = await self._connect("extended")
        handshake = await self.server.wait_for_handshake(timeout=2)
        self.assertEqual(handshake.open_channel.channel_type, "extended")
        self.assertEqual(handshake.open_channel.minimum_extranonce_size, 2)

        job = Sv2MiningJob.standard(202)
        await self.server.send_job(job, session=handshake.connection_id)
        first = await asyncio.wait_for(client.noise.receive_frame(), timeout=2)
        second = await asyncio.wait_for(client.noise.receive_frame(), timeout=2)
        self.assertEqual(first.message_type, SV2_MSG_NEW_EXTENDED_MINING_JOB)
        self.assertEqual(second.message_type, SV2_MSG_SET_NEW_PREV_HASH)

        submission_payload = (
            struct.pack(
                "<IIIIII",
                client.channel_id,
                0,
                job.job_id,
                456,
                job.ntime,
                job.version,
            )
            + b"\x08"
            + b"\x00" * 8
        )
        await client.noise.send_frame(
            SV2_CHANNEL_MESSAGE,
            SV2_MSG_SUBMIT_SHARES_EXTENDED,
            submission_payload,
        )
        response = await asyncio.wait_for(client.noise.receive_frame(), timeout=2)
        submission = await self.server.wait_for_submission(job_id=job.job_id, timeout=2)
        self.assertEqual(response.message_type, SV2_MSG_SUBMIT_SHARES_ERROR)
        self.assertEqual(submission.extranonce, bytes(8))
        self.assertIn(b"low-difficulty-share", response.payload)

    async def test_reconnect_and_oversized_frame_failure_are_bounded(self) -> None:
        first = await self._connect("standard")
        first_handshake = await self.server.wait_for_handshake(timeout=2)
        await first.close()
        second = await self._connect("standard")
        second_handshake = await self.server.wait_for_handshake(
            after_connection_id=first_handshake.connection_id,
            timeout=2,
        )
        self.assertGreater(
            second_handshake.connection_id, first_handshake.connection_id
        )

        oversized_header = (
            b"\x00\x80"
            + bytes([SV2_MSG_SET_TARGET])
            + (self.server.max_payload_size + 1).to_bytes(3, "little")
        )
        second.writer.write(second.noise._encrypt(oversized_header))
        await second.writer.drain()
        async with asyncio.timeout(2):
            while self.server.sessions[-1].closed_at is None:
                await asyncio.sleep(0.01)
        self.assertIsNotNone(self.server.sessions[-1].closed_at)

    async def test_close_does_not_wait_for_incomplete_noise_client(self) -> None:
        reader, writer = await asyncio.open_connection("127.0.0.1", self.server.port)
        del reader
        writer.write(b"incomplete")
        await writer.drain()
        await asyncio.wait_for(self.server.close(), timeout=2)
        writer.close()
        await asyncio.gather(writer.wait_closed(), return_exceptions=True)


if __name__ == "__main__":
    unittest.main()
