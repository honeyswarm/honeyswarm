"""Shared MQTT TLS configuration for the API's broker connections."""
import ssl

import aiomqtt

from app.core.config import settings


def tls_params() -> aiomqtt.TLSParameters | None:
    """Return TLS parameters for connecting to the broker, or None if disabled.

    Uses the self-signed CA to verify the broker (server-authenticated TLS).
    """
    if not settings.mqtt_use_tls:
        return None
    return aiomqtt.TLSParameters(
        ca_certs=settings.mqtt_ca_cert,
        cert_reqs=ssl.CERT_REQUIRED,
    )
