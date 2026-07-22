"""Runtime configuration via pydantic-settings.

All API keys are OPTIONAL. Missing keys degrade gracefully with a clear log line
(spec: satellite/live paths are best-effort; the task relaxes the global
crash-on-misconfig rule for these). Secrets live only in `.env` (gitignored) and
GitHub Actions secrets. They never appear in lineage or logs.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def repo_root() -> Path:
    """Repository root: the ancestor of this file that holds `config/`."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config").is_dir():
            return parent
    # Fallback: pipeline/src/vayu/settings.py -> repo root is parents[3].
    return here.parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env", str(repo_root() / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Optional free keys (user is registering these). None => graceful degrade.
    # These names are the AUTHORITATIVE pydantic-settings schema; .env.example
    # (owned by vayu-ops) mirrors them.
    openaq_api_key: str | None = Field(default=None, alias="OPENAQ_API_KEY")
    datagov_api_key: str | None = Field(default=None, alias="DATA_GOV_IN_API_KEY")
    firms_map_key: str | None = Field(default=None, alias="FIRMS_MAP_KEY")
    earthdata_token: str | None = Field(default=None, alias="EARTHDATA_TOKEN")

    # NVIDIA NIM key for the agentic Action-Brief layer (spec 14, owner: vayu-agents).
    # Hosted Nemotron endpoint; pipeline-side only, never logged or published. Absent =>
    # the briefs stage degrades gracefully (keeps previous briefs, marks stale, exit 0).
    nvidia_api_key: str | None = Field(default=None, alias="NVIDIA_API_KEY")

    # GEE service account. Provide EITHER the JSON inline (raw or base64, for CI)
    # OR a path to the key file (local dev). The service-account email is read
    # from the JSON's client_email; the explicit override is optional.
    gee_service_account_json: str | None = Field(
        default=None, alias="GEE_SERVICE_ACCOUNT_JSON"
    )
    gee_service_account_json_path: str | None = Field(
        default=None, alias="GEE_SERVICE_ACCOUNT_JSON_PATH"
    )
    gee_service_account_email: str | None = Field(
        default=None, alias="GEE_SERVICE_ACCOUNT_EMAIL"
    )
    gee_project: str | None = Field(default=None, alias="GEE_PROJECT")

    log_level: str = Field(default="info", alias="LOG_LEVEL")

    # Feature-store + raw root (pipeline-internal, gitignored). Default <repo>/data.
    data_dir: Path | None = Field(default=None, alias="VAYU_DATA_DIR")
    # Published web JSON + wards root. Default <repo>/web/public/data.
    web_data_dir: Path | None = Field(default=None, alias="VAYU_WEB_DATA_DIR")

    @property
    def resolved_data_dir(self) -> Path:
        return self.data_dir or (repo_root() / "data")

    @property
    def resolved_web_data_dir(self) -> Path:
        return self.web_data_dir or (repo_root() / "web" / "public" / "data")

    @property
    def raw_dir(self) -> Path:
        return self.resolved_data_dir / "raw"

    @property
    def feature_store_dir(self) -> Path:
        return self.resolved_data_dir / "feature-store"

    def has(self, key: str) -> bool:
        return bool(getattr(self, key, None))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
