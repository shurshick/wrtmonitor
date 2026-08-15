download_file() {
    url="$1"
    destination="$2"
    curl -fsS --connect-timeout 10 --max-time 60 -o "$destination" "$url"
}

checksum_for() {
    sha256sum "$1" | awk '{print $1}'
}

checksum_expected_for() {
    sums_file="$1"
    filename="$2"
    awk -v name="$filename" '$2 == name {print $1}' "$sums_file" | head -n 1
}

verify_checksum() {
    sums_file="$1"
    file_path="$2"
    filename="$3"
    expected="$(checksum_expected_for "$sums_file" "$filename")"
    if [ -z "$expected" ]; then
        return 1
    fi
    actual="$(checksum_for "$file_path")"
    [ "$actual" = "$expected" ]
}

write_update_public_key() {
    cat >"$1" <<'EOF'
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAbXo+FQit+3CFcc6Dwnww2gtXN5wOMlwxDdx/UIDth4A=
-----END PUBLIC KEY-----
EOF
}

write_update_rsa_public_key() {
    cat >"$1" <<'EOF'
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAw0Oa78bfYDUZQgtbeOt+
xLqjGAcJfMUz5n8Qg76kUj8PQO1/0NDy22lyUAfii9DLsTS4zeR0wgwuEAT3wUzB
Ca/EDwuHll/PlGB4OBDNnw8zTb/jPa6KJW+NR0fu1jovEofEP6aDSMb6lIheTIEF
EHfeMfNiSHHZemiQNNBBF8xEcjKQuUP/DuGFnBMFrY0296eWSu3HhDHbCsOxnkLU
n3/349a595GVxwCYU/+sF+qsATv5KigGYkaqxcHEQJxhc4dAp8ZEEXmaROM7lKQ0
yCIhswvVwjyFXTsDcmZVnQCWtPaJusyQV9HKmUaFHQwo/oVp9Y+uxsyzTmNppn67
LwIDAQAB
-----END PUBLIC KEY-----
EOF
}

write_update_legacy_rsa_public_key() {
    cat >"$1" <<'EOF'
-----BEGIN PUBLIC KEY-----
MIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEAnk2nhDg1rLY7XmxMRA81
ahLaHSD+SP3t0vaul5dnE9kKzFAMoOBWTkuhmECLJ+ZXgzHKpZCbC7K0uH1zJ/og
xQDj9ok4z4DIhyXSkvUY4WUe1MMTYpxFa6Ow6E6+ke0oBxUMOHGhOKBm/7QPcTxp
nbTSjxIHlwR2i7iyNDnjZ7xBZpep/b3FTX/O/ha1/5rGHeImd6SVRk8x2RCeCmQj
w7fprDRD//2Ko350oojyinicZmU1tp61RyW78fgrQURQJjm5p8FPEyqjvmWkjLbw
/cWDqGcZXiBsGwPCbxiXL4cYQR27FTjIDu1b30dyt4mJ80XQHuVVMqLHiwPcx1UV
uW9/XV0g6YUzHcJxXFT47R3cOCvU0qiZixxItEFc+3mNZ4fhiOudZOq7H04yZq0E
zgpi4sAWwz2IcbNj4sohxaV9hq8pPgnCzG6PYPRLpl6UmiKeLY6dmKGXFHx+GxcP
gU3H/CMcfRH8Os4zX9nhqWj3aV2wDXHkgABOGHsiNbTXAgMBAAE=
-----END PUBLIC KEY-----
EOF
}

verify_ed25519_manifest_signature() {
    tmp_dir="$1"
    public_key="$tmp_dir/update-public-key.pem"
    signature="$tmp_dir/SHA256SUMS.sig.bin"
    [ -r "$tmp_dir/SHA256SUMS.sig" ] || return 1
    write_update_public_key "$public_key"
    base64 -d <"$tmp_dir/SHA256SUMS.sig" >"$signature" 2>/dev/null || return 1
    openssl pkeyutl -verify -pubin -inkey "$public_key" -rawin \
        -in "$tmp_dir/SHA256SUMS.txt" -sigfile "$signature" >/dev/null 2>&1
}

verify_rsa_manifest_signature() {
    tmp_dir="$1"
    public_key="$tmp_dir/update-rsa-public-key.pem"
    signature="$tmp_dir/SHA256SUMS.rsa.sig.bin"
    [ -r "$tmp_dir/SHA256SUMS.rsa.sig" ] || return 1
    base64 -d <"$tmp_dir/SHA256SUMS.rsa.sig" >"$signature" 2>/dev/null || return 1
    write_update_rsa_public_key "$public_key"
    openssl dgst -sha256 -verify "$public_key" -signature "$signature" \
        "$tmp_dir/SHA256SUMS.txt" >/dev/null 2>&1 && return 0
    write_update_legacy_rsa_public_key "$public_key"
    openssl dgst -sha256 -verify "$public_key" -signature "$signature" \
        "$tmp_dir/SHA256SUMS.txt" >/dev/null 2>&1
}

verify_manifest_signature() {
    tmp_dir="$1"
    verify_ed25519_manifest_signature "$tmp_dir" && return 0
    verify_rsa_manifest_signature "$tmp_dir"
}

remote_version_from_tmp() {
    tr -d '\r\n' <"$1/agent-version.txt"
}
