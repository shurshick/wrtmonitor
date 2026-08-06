#!/usr/bin/env python3
import argparse
import base64
import sys
from pathlib import Path
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519, padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key

def sign_ed25519(private_key_path: Path, data: bytes) -> bytes:
    with open(private_key_path, "rb") as f:
        private_key = load_pem_private_key(f.read(), password=None)
    
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise ValueError("Key is not an Ed25519 private key")
    
    signature = private_key.sign(data)
    return base64.b64encode(signature)

def sign_rsa(private_key_path: Path, data: bytes) -> bytes:
    with open(private_key_path, "rb") as f:
        private_key = load_pem_private_key(f.read(), password=None)
    
    signature = private_key.sign(
        data,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    return base64.b64encode(signature)

def main():
    parser = argparse.ArgumentParser(description="Sign WrtMonitor agent updates")
    parser.add_argument("manifest", type=Path, help="Path to SHA256SUMS.txt")
    parser.add_argument("--ed25519-key", type=Path, help="Path to Ed25519 private key")
    parser.add_argument("--rsa-key", type=Path, help="Path to RSA private key")
    
    args = parser.parse_args()
    
    if not args.ed25519_key and not args.rsa_key:
        print("Error: Must provide at least one private key (--ed25519-key or --rsa-key)", file=sys.stderr)
        sys.exit(1)
        
    if not args.manifest.is_file():
        print(f"Error: Manifest file {args.manifest} not found", file=sys.stderr)
        sys.exit(1)
        
    with open(args.manifest, "rb") as f:
        data = f.read()
        
    if args.ed25519_key:
        sig = sign_ed25519(args.ed25519_key, data)
        sig_path = args.manifest.with_name("SHA256SUMS.sig")
        with open(sig_path, "wb") as f:
            f.write(sig)
            f.write(b"\n")
        print(f"Generated Ed25519 signature: {sig_path}")
        
    if args.rsa_key:
        sig = sign_rsa(args.rsa_key, data)
        sig_path = args.manifest.with_name("SHA256SUMS.rsa.sig")
        with open(sig_path, "wb") as f:
            f.write(sig)
            f.write(b"\n")
        print(f"Generated RSA signature: {sig_path}")

if __name__ == "__main__":
    main()
