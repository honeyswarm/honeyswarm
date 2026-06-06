"""Tests for per-hive MQTT client certificate minting (C2 mTLS)."""
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from app.core.mqtt_certs import issue_client_cert


def _make_ca() -> tuple[bytes, bytes]:
    """Generate a throwaway CA cert/key (PEM) for signing in tests."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def test_issue_client_cert_cn_and_issuer():
    ca_cert_pem, ca_key_pem = _make_ca()
    cert_pem, key_pem = issue_client_cert(
        "507f1f77bcf86cd799439011", ca_cert_pem=ca_cert_pem, ca_key_pem=ca_key_pem
    )

    cert = x509.load_pem_x509_certificate(cert_pem.encode())
    ca_cert = x509.load_pem_x509_certificate(ca_cert_pem)

    # CN is the hive id (used by the broker as the MQTT username for ACL matching).
    cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    assert cn == "507f1f77bcf86cd799439011"
    # Issued by our CA.
    assert cert.issuer == ca_cert.subject
    # Carries the clientAuth EKU.
    eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    assert ExtendedKeyUsageOID.CLIENT_AUTH in eku
    # Not a CA cert.
    bc = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
    assert bc.ca is False
    # The returned key is a usable private key.
    assert serialization.load_pem_private_key(key_pem.encode(), password=None)


def test_issue_client_cert_signed_by_ca():
    ca_cert_pem, ca_key_pem = _make_ca()
    cert_pem, _ = issue_client_cert("hive-a", ca_cert_pem=ca_cert_pem, ca_key_pem=ca_key_pem)

    cert = x509.load_pem_x509_certificate(cert_pem.encode())
    ca_cert = x509.load_pem_x509_certificate(ca_cert_pem)
    # Verify the CA's public key actually signed this cert (raises on mismatch).
    ca_cert.public_key().verify(
        cert.signature,
        cert.tbs_certificate_bytes,
        padding.PKCS1v15(),
        cert.signature_hash_algorithm,
    )


def test_each_hive_gets_distinct_identity():
    ca_cert_pem, ca_key_pem = _make_ca()
    cert_a, key_a = issue_client_cert("hive-a", ca_cert_pem=ca_cert_pem, ca_key_pem=ca_key_pem)
    cert_b, key_b = issue_client_cert("hive-b", ca_cert_pem=ca_cert_pem, ca_key_pem=ca_key_pem)
    assert cert_a != cert_b
    assert key_a != key_b
