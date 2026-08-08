#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
from pathlib import Path

from cryptography.hazmat.primitives.serialization import load_pem_public_key


def public_key_bytes(path: Path) -> bytes:
    return load_pem_public_key(path.read_bytes()).public_bytes_raw()


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the legacy agent update chain")
    parser.add_argument("--legacy-ed25519-key", type=Path, required=True)
    parser.add_argument("--current-ed25519-key", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--signature", type=Path, required=True)
    args = parser.parse_args()

    legacy_key = load_pem_public_key(args.legacy_ed25519_key.read_bytes())
    current_bytes = public_key_bytes(args.current_ed25519_key)
    legacy_bytes = legacy_key.public_bytes_raw()
    if legacy_bytes != current_bytes:
        raise ValueError("Ed25519 trust anchor changed; old agents cannot update")

    signature = base64.b64decode(args.signature.read_bytes().strip(), validate=True)
    legacy_key.verify(signature, args.manifest.read_bytes())
    print("Legacy agent trust anchor accepts the current signed manifest.")


if __name__ == "__main__":
    main()
