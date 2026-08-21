from __future__ import annotations

import argparse
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a SiteProof Ed25519 development signing key.")
    parser.add_argument("--private-key", default=".secrets/siteproof-signing-private.pem")
    parser.add_argument("--public-key", default=".secrets/siteproof-signing-public.pem")
    args = parser.parse_args()
    private_path = Path(args.private_key)
    public_path = Path(args.public_key)
    for path in (private_path, public_path):
        if path.exists():
            raise SystemExit(f"Refusing to overwrite existing key: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    private_path.write_bytes(key.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption()))
    os.chmod(private_path, 0o600)
    public_path.write_bytes(key.public_key().public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo))
    print(f"Private key: {private_path} (mode 0600)")
    print(f"Public key:  {public_path}")
    print("Keep the private key secret and never commit it to Git.")


if __name__ == "__main__":
    main()
