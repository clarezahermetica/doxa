"""Real loopback API lifecycle for streaming tests; no graphical client or assets."""

import socket
import threading
import time

import uvicorn

from doxa.api.app import create_app
from doxa.core.config import Settings


class LocalApiServer:
    def __init__(self, data_dir):
        self.app = create_app(Settings(data_dir=data_dir))
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.url = f"http://127.0.0.1:{self.socket.getsockname()[1]}"
        self.server = uvicorn.Server(
            uvicorn.Config(
                self.app, log_level="error", access_log=False, timeout_graceful_shutdown=3
            )
        )
        self.thread = threading.Thread(
            target=self.server.run, kwargs={"sockets": [self.socket]}, daemon=True
        )

    def start(self):
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started:
            if not self.thread.is_alive() or time.monotonic() > deadline:
                self.stop()
                raise RuntimeError("Test API server failed to start")
            time.sleep(0.01)

    def stop(self):
        self.app.state.closing = True
        self.server.should_exit = True
        self.thread.join(5)
        self.socket.close()
        assert not self.thread.is_alive()
