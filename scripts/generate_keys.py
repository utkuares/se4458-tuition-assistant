
import sys

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


KEYS_DIR = Path(__file__).resolve().parents[1] / "keys"

def main() -> None:
    KEYS_DIR.mkdir(exist_ok=True)

    priv_path = KEYS_DIR / "jwt_private.pem"
    pub_path = KEYS_DIR / "jwt_public.pem"

    if priv_path.exists() and "--force" not in sys.argv:
        print(f"Anahtarlar zaten var: {KEYS_DIR}. Üzerine yazmak için --force kullan.")

        return

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    priv_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    priv_path.chmod(0o600)

    pub_path.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"Oluşturuldu: {priv_path} ve {pub_path}")

if __name__ == "__main__":
    main()