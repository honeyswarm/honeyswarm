"""Application configuration via environment variables.

Replaces the scattered ``os.environ.get`` calls in the old Flask app
(__init__.py / saltapi.py / subscriber.py) with a single typed settings object.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # General
    timezone: str = Field(default="Europe/London", alias="TIMEZONE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    manifests_dir: str = Field(default="/opt/honeyswarm/manifests", alias="MANIFESTS_DIR")
    public_url: str = Field(default="http://localhost:8080", alias="PUBLIC_URL")
    mqtt_public_host: str = Field(default="localhost", alias="MQTT_PUBLIC_HOST")
    # Published hive agent image referenced in the enrollment install command.
    agent_image: str = Field(default="ghcr.io/honeyswarm/honeyswarm-agent:latest", alias="AGENT_IMAGE")

    # Auth / JWT
    jwt_secret: str = Field(default="CHANGE_ME_I_AM_NOT_SECURE", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_ttl_minutes: int = Field(default=30, alias="ACCESS_TOKEN_TTL_MINUTES")
    refresh_token_ttl_days: int = Field(default=14, alias="REFRESH_TOKEN_TTL_DAYS")

    # Bootstrap admin (created on first startup if no users exist)
    admin_email: str = Field(default="admin@honeyswarm.local", alias="ADMIN_EMAIL")
    admin_password: str = Field(default="", alias="ADMIN_PASSWORD")

    # MongoDB
    mongodb_host: str = Field(default="mongo", alias="MONGODB_HOST")
    mongodb_port: int = Field(default=27017, alias="MONGODB_PORT")
    mongodb_username: str = Field(default="", alias="MONGODB_USERNAME")
    mongodb_password: str = Field(default="", alias="MONGODB_PASSWORD")
    mongodb_auth_source: str = Field(default="admin", alias="MONGODB_AUTH_SOURCE")
    mongodb_database: str = Field(default="honeyswarm", alias="MONGODB_DATABASE")

    # OpenSearch
    opensearch_host: str = Field(default="opensearch", alias="OPENSEARCH_HOST")
    opensearch_port: int = Field(default=9200, alias="OPENSEARCH_PORT")
    opensearch_user: str = Field(default="admin", alias="OPENSEARCH_USER")
    opensearch_password: str = Field(default="admin", alias="OPENSEARCH_PASSWORD")
    opensearch_use_ssl: bool = Field(default=False, alias="OPENSEARCH_USE_SSL")
    opensearch_verify_certs: bool = Field(default=False, alias="OPENSEARCH_VERIFY_CERTS")
    opensearch_event_index: str = Field(default="honeyswarm-events", alias="OPENSEARCH_EVENT_INDEX")

    # MQTT (TLS by default)
    mqtt_host: str = Field(default="mqtt", alias="MQTT_HOST")
    mqtt_port: int = Field(default=8883, alias="MQTT_PORT")
    mqtt_username: str = Field(default="honeyswarm", alias="MQTT_USERNAME")
    mqtt_password: str = Field(default="", alias="MQTT_PASSWORD")
    mqtt_use_tls: bool = Field(default=True, alias="MQTT_USE_TLS")
    mqtt_ca_cert: str = Field(default="/certs/ca.crt", alias="MQTT_CA_CERT")

    @property
    def mongodb_uri(self) -> str:
        if self.mongodb_username:
            auth = f"{self.mongodb_username}:{self.mongodb_password}@"
            suffix = f"?authSource={self.mongodb_auth_source}"
        else:
            auth = ""
            suffix = ""
        return f"mongodb://{auth}{self.mongodb_host}:{self.mongodb_port}/{suffix}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
