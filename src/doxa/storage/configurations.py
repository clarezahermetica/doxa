from pathlib import Path
from typing import Literal

from doxa.core.profiles import AgentDefinition, CouncilConfig, ModelProfile
from doxa.core.secrets import reject_secrets
from doxa.storage.database import connection


class ConfigurationStore:
    def __init__(self, path: Path):
        self.path = path

    def save(self, config: CouncilConfig) -> None:
        reject_secrets(
            config.model_dump_json(),
            directory=self.path.parent,
            credential_names=tuple(profile.credential_env for profile in config.profiles),
        )
        with connection(self.path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            for kind, records in (("profile", config.profiles), ("agent", config.agents)):
                for record in records:
                    body = record.model_dump_json()
                    key = (kind, str(record.id), record.version)
                    row = db.execute(
                        "SELECT body FROM configurations WHERE kind=? AND id=? AND version=?",
                        key,
                    ).fetchone()
                    if row:
                        model = ModelProfile if kind == "profile" else AgentDefinition
                        if model.model_validate_json(row[0]) != record:
                            raise ValueError(
                                "Configuration version is immutable; increment version"
                            )
                    else:
                        db.execute("INSERT INTO configurations VALUES (?,?,?,?)", (*key, body))
            for agent in config.agents:
                if agent.model_profile_id:
                    row = db.execute(
                        """SELECT 1 FROM configurations
                        WHERE kind='profile' AND id=? AND version=?""",
                        (agent.model_profile_id, agent.model_profile_version),
                    ).fetchone()
                    if not row:
                        raise ValueError("Agent refers to an unknown model profile version")
                    # Resolve the pinned version, not the latest profile with this ID.
                    profile_row = db.execute(
                        "SELECT body FROM configurations WHERE kind='profile' "
                        "AND id=? AND version=?",
                        (agent.model_profile_id, agent.model_profile_version),
                    ).fetchone()
                    profile = ModelProfile.model_validate_json(profile_row[0])
                    if any(
                        tool not in {"web_search", "web_fetch"}
                        for tool in agent.agent.permissions.allowed_tools
                    ) and profile.capabilities.tool_calling in {"unknown", "unavailable"}:
                        raise ValueError(
                            "Agent tool permissions require a declared compatible profile"
                        )

    def get(
        self, kind: Literal["profile", "agent"], identity: str, version: int | None = None
    ) -> ModelProfile | AgentDefinition:
        with connection(self.path) as db:
            row = db.execute(
                """SELECT body FROM configurations WHERE kind=? AND id=?
                AND (? IS NULL OR version=?) ORDER BY version DESC LIMIT 1""",
                (kind, identity, version, version),
            ).fetchone()
        if row is None:
            raise KeyError(identity)
        model = ModelProfile if kind == "profile" else AgentDefinition
        return model.model_validate_json(row[0])

    def list(self) -> CouncilConfig:
        with connection(self.path) as db:
            rows = db.execute("""SELECT c.kind,c.body FROM configurations c
                WHERE c.version=(SELECT MAX(d.version) FROM configurations d
                WHERE c.kind=d.kind AND c.id=d.id) ORDER BY c.kind,c.id""").fetchall()
        return CouncilConfig(
            profiles=tuple(ModelProfile.model_validate_json(b) for k, b in rows if k == "profile"),
            agents=tuple(AgentDefinition.model_validate_json(b) for k, b in rows if k == "agent"),
        )
