from pathlib import Path
from typing import Literal

from pydantic import Field

from doxa.core.models import Contract
from doxa.core.workspaces import default_workspace


class Settings(Contract):
    data_dir: Path = Field(default_factory=default_workspace)
    development_studio: bool = False
    remote_inference_enabled: bool = False
    execution_enabled: bool = False
    api_host: Literal["127.0.0.1", "localhost", "::1"] = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1024, le=65535)

    @property
    def database_path(self) -> Path:
        return self.data_dir / "ledger.sqlite3"
