from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

keys_dir = Path("keys")
keys_dir.mkdir(exist_ok=True)

private_key = Ed25519PrivateKey.generate()

private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
public_pem = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)

(keys_dir / "private.pem").write_bytes(private_pem)
(keys_dir / "public.pem").write_bytes(public_pem)
print("Wrote keys/private.pem and keys/public.pem")