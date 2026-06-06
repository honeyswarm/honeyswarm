"""Shared MQTT TLS configuration for the API's broker connections."""
import ssl

import aiomqtt

from app.core.config import settings


def tls_params() -> aiomqtt.TLSParameters | None:
    """Return TLS parameters for connecting to the broker, or None if disabled.

    Mutual TLS: verifies the broker with the CA and presents the controller's
    client certificate (CN ``honeyswarm``), from which the broker derives the
    MQTT username for ACL matching.
    """
    if not settings.mqtt_use_tls:
        return None
    return aiomqtt.TLSParameters(
        ca_certs=settings.mqtt_ca_cert,
        certfile=settings.mqtt_client_cert,
        keyfile=settings.mqtt_client_key,
        cert_reqs=ssl.CERT_REQUIRED,
    )
