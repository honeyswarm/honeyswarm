"""Application configuration via environment variables.

Replaces the scattered ``os.environ.get`` calls in the old Flask app
(__init__.py / saltapi.py / subscriber.py) with a single typed settings object.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# The secret shipped in .env.example. The app refuses to start with this value
# (or anything too short) so a forgotten override can't leave JWTs forgeable.
DEFAULT_JWT_SECRET = "CHANGE_ME_I_AM_NOT_SECURE"
MIN_JWT_SECRET_LEN = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # General
    timezone: str = Field(default="Europe/London", alias="TIMEZONE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    manifests_dir: str = Field(default="/opt/honeyswarm/manifests", alias="MANIFESTS_DIR")
    # Public base URL agents use to enroll. Goes through the Caddy edge (HTTPS),
    # NOT the API's internal :8080 — that port is no longer published to the host.
    public_url: str = Field(default="https://localhost", alias="PUBLIC_URL")
    mqtt_public_host: str = Field(default="localhost", alias="MQTT_PUBLIC_HOST")
    # Whether agents verify the controller's TLS cert during enrollment. Default
    # off because the edge ships a self-signed cert out of the box; set true once
    # PUBLIC_URL points at a domain with a trusted (Let's Encrypt) cert.
    agent_tls_verify: bool = Field(default=False, alias="AGENT_TLS_VERIFY")
    # Published hive agent image referenced in the enrollment install command.
    agent_image: str = Field(default="ghcr.io/honeyswarm/honeyswarm-agent:latest", alias="AGENT_IMAGE")

    # Auth / JWT
    jwt_secret: str = Field(default=DEFAULT_JWT_SECRET, alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    # Escape hatch for throwaway local dev ONLY: lets the app boot with the
    # default/short secret. Never set this in any shared or internet-facing deploy.
    allow_insecure_jwt_secret: bool = Field(default=False, alias="ALLOW_INSECURE_JWT_SECRET")
    access_token_ttl_minutes: int = Field(default=30, alias="ACCESS_TOKEN_TTL_MINUTES")
    refresh_token_ttl_days: int = Field(default=14, alias="REFRESH_TOKEN_TTL_DAYS")
    # SSO cookie for the Dashboards reverse proxy (forward_auth). Longer-lived
    # than the access token so opening Dashboards mid-session just works.
    dashboards_token_ttl_minutes: int = Field(default=480, alias="DASHBOARDS_TOKEN_TTL_MINUTES")
    dashboards_cookie_name: str = Field(default="hs_dash", alias="DASHBOARDS_COOKIE_NAME")
    # Set the Secure flag on the cookie (requires HTTPS at the edge; default on).
    cookie_secure: bool = Field(default=True, alias="COOKIE_SECURE")

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
    # OpenSearch Dashboards (saved-objects API) for auto-provisioning the events
    # index pattern so Discover works out of the box on a fresh install. The
    # ``/dashboards`` suffix matches Dashboards' SERVER_BASEPATH (it is served
    # under that prefix behind the Caddy basic-auth proxy). This is an internal
    # container-to-container call, so it bypasses the proxy's basic auth.
    opensearch_dashboards_url: str = Field(
        default="http://opensearch-dashboards:5601/dashboards", alias="OPENSEARCH_DASHBOARDS_URL"
    )

    # MQTT (mutual TLS by default)
    mqtt_host: str = Field(default="mqtt", alias="MQTT_HOST")
    mqtt_port: int = Field(default=8883, alias="MQTT_PORT")
    # Controller identity. The broker derives the MQTT username from the client
    # cert CN (use_identity_as_username); this must match the ACL's controller
    # user. mqtt_password is retained for back-compat but unused under mTLS.
    mqtt_username: str = Field(default="honeyswarm", alias="MQTT_USERNAME")
    mqtt_password: str = Field(default="", alias="MQTT_PASSWORD")
    mqtt_use_tls: bool = Field(default=True, alias="MQTT_USE_TLS")
    mqtt_ca_cert: str = Field(default="/secrets/ca.crt", alias="MQTT_CA_CERT")
    # CA private key (used to mint per-hive client certs) + the controller's own
    # client cert/key, all generated into the mqtt_secrets volume by mqtt/init.sh.
    mqtt_ca_key: str = Field(default="/secrets/ca.key", alias="MQTT_CA_KEY")
    mqtt_client_cert: str = Field(
        default="/secrets/client-honeyswarm.crt", alias="MQTT_CLIENT_CERT"
    )
    mqtt_client_key: str = Field(
        default="/secrets/client-honeyswarm.key", alias="MQTT_CLIENT_KEY"
    )

    @property
    def mongodb_uri(self) -> str:
        if self.mongodb_username:
            auth = f"{self.mongodb_username}:{self.mongodb_password}@"
            suffix = f"?authSource={self.mongodb_auth_source}"
        else:
            auth = ""
            suffix = ""
        return f"mongodb://{auth}{self.mongodb_host}:{self.mongodb_port}/{suffix}"

    def assert_secure(self) -> None:
        """Fail fast on an insecure JWT secret.

        Called at application startup (not import time, so unit tests are
        unaffected). With the shipped default or a too-short secret, anyone can
        forge an admin token — so refuse to boot unless explicitly overridden for
        local dev via ALLOW_INSECURE_JWT_SECRET.
        """
        if self.allow_insecure_jwt_secret:
            return
        if self.jwt_secret == DEFAULT_JWT_SECRET or len(self.jwt_secret) < MIN_JWT_SECRET_LEN:
            raise RuntimeError(
                "Refusing to start: JWT_SECRET is unset, the shipped default, or "
                f"shorter than {MIN_JWT_SECRET_LEN} chars. Set a strong random "
                "JWT_SECRET in .env (e.g. `openssl rand -hex 32`). For throwaway "
                "local dev only, set ALLOW_INSECURE_JWT_SECRET=true."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
