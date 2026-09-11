"""Authenticated SV2 endpoints for the shared pool-fallback scenarios."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .errors import DeviceError
from .interfaces.fake_stratum_v2 import (
    FakeStratumV2Server, Sv2MiningJob, SV2_MSG_SUBMIT_SHARES_SUCCESS,
)


@dataclass(frozen=True)
class MiningSubmission:
    sequence: int
    connection_id: int
    job_id: int
    username: str


class WorkingV2Pool(FakeStratumV2Server):
    """Supply fresh work and preserve authenticated sessions through silence."""

    def __init__(self, label: str, host: str, difficulty: int, *, port: int = 0) -> None:
        super().__init__(host=host, port=port, initial_difficulty=difficulty,
                         max_sessions=64, max_events=20000, handshake_timeout=1200)
        self.label, self.difficulty = label, difficulty
        self.available = False
        self.silent = False
        self.silent_requests = 0
        self.job_counter = 0
        self.jobs: dict[int, int] = {}
        self.refresh: asyncio.Task | None = None
        self.limit_error: str | None = None
        self._acknowledged: set[tuple[int, int]] = set()

    @property
    def requests(self):
        return self.frames

    @property
    def mining_submissions(self) -> tuple[MiningSubmission, ...]:
        # SV2 submits carry a channel, not a worker. Resolve that channel's
        # authenticated OpenMiningChannel identity and require a sent ACK.
        result = []
        for share in self.submissions:
            session = self._sessions[share.connection_id]
            if ((share.connection_id, share.sequence_number) in self._acknowledged and
                    session.open_channel is not None and share.channel_id == session.channel_id):
                result.append(MiningSubmission(share.sequence, share.connection_id,
                                               share.job_id, session.open_channel.user_identity))
        return tuple(result)

    def _client_connected(self, reader, writer) -> None:
        if self._next_connection_id + len(self._client_tasks) > self.max_sessions:
            self.limit_error = "fallback SV2 connection limit exceeded"
            writer.close()
            return
        super()._client_connected(reader, writer)

    async def _record_event(self, event, **fields) -> None:
        if len(self._events) >= self.max_events:
            self.limit_error = "fallback SV2 event limit exceeded"
        await super()._record_event(event, **fields)

    async def _record_frame(self, session, frame, decoded):
        if len(self._events) >= self.max_events:
            self.limit_error = "fallback SV2 event limit exceeded"
        return await super()._record_frame(session, frame, decoded)

    async def start(self) -> None:
        await super().start()
        self.requested_port = self.port
        self.available = True
        if self.refresh is None:
            self.refresh = asyncio.create_task(self._refresh(), name=f"fallback-v2-work-{self.label}")

    async def set_available(self, available: bool) -> None:
        self.available = available
        if available:
            await self.start()
        else:
            await super().close()

    async def _noise_handshake(self, reader, writer):
        # Silence applies to reconnects and recovery probes too. The outer
        # handshake bound exceeds the scenario budget: the miner must time out.
        while self.silent:
            await asyncio.sleep(.1)
        return await super()._noise_handshake(reader, writer)

    async def _handle_frame(self, session, frame) -> None:
        if self.silent:
            self.silent_requests += 1
        await super()._handle_frame(session, frame)

    async def _send_message(self, session, extension_type, message_type, payload, **kwargs) -> None:
        if self.silent:
            return  # Do not advance the outbound Noise nonce for unsent frames.
        await super()._send_message(session, extension_type, message_type, payload, **kwargs)
        if message_type == SV2_MSG_SUBMIT_SHARES_SUCCESS:
            self._acknowledged.add((session.connection_id, kwargs["fields"]["last_sequence_number"]))

    async def _send_work(self, session) -> None:
        if self.job_counter >= 4096:
            self.limit_error = "fallback SV2 job limit exceeded"
            raise ConnectionError(self.limit_error)
        self.job_counter += 1
        prefix = 0x10000000 if self.label == "primary" else 0x20000000
        job = Sv2MiningJob.standard(prefix + self.job_counter)
        await self.send_job(job, difficulty=self.difficulty, session=session)
        self.jobs[job.job_id] = self.job_counter

    async def publish_work(self) -> None:
        if not self.available or self.silent:
            return
        for session in self.sessions:
            if session.connected and session.open_channel is not None:
                try:
                    await self._send_work(session)
                except (ConnectionError, BrokenPipeError):
                    pass

    async def _refresh(self) -> None:
        while True:
            await asyncio.sleep(2)
            self.check_limits()
            await self.publish_work()

    def check_limits(self) -> None:
        if self.limit_error:
            raise DeviceError(self.limit_error)
        if self.refresh is not None and self.refresh.done():
            self.refresh.result()

    async def close(self) -> None:
        self.available = False
        if self.refresh is not None:
            self.refresh.cancel()
            await asyncio.gather(self.refresh, return_exceptions=True)
            self.refresh = None
        await super().close()
