"""Optional JSON-lines transport for a future librime helper process."""

from __future__ import annotations

import json
import subprocess
import threading
from typing import Optional

from .rime_protocol import CandidateState, command_message, parse_response, stroke_message


class SidecarBackend:
    """Synchronous backend for a helper speaking the JSON-lines protocol.

    The helper command is optional and deliberately injected by the caller;
    this class never starts a vendor executable or changes the user's Rime
    directory by itself.
    """

    def __init__(self, command, cwd: Optional[str] = None):
        self._process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._lock = threading.RLock()
        self.state = CandidateState()

    def _request(self, message: str) -> CandidateState:
        with self._lock:
            if self._process.poll() is not None:
                raise RuntimeError("Rime sidecar exited")
            assert self._process.stdin is not None
            assert self._process.stdout is not None
            self._process.stdin.write(message)
            self._process.stdin.flush()
            line = self._process.stdout.readline()
            if not line:
                raise RuntimeError("Rime sidecar returned no response")
            self.state = parse_response(line)
            return self.state

    def consume(self, stroke, engine) -> bool:
        self._request(stroke_message(stroke.rtfcre))
        # A backend that returns a committed string is responsible for sending
        # it through Plover's output object.  Candidate UI integration will add
        # that policy; for now a live sidecar consumes the stroke.
        if self.state.committed:
            engine._send_string(self.state.committed)
        return True

    def command(self, name, value=None) -> CandidateState:
        return self._request(command_message(name, value))

    def close(self):
        process = self._process
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
