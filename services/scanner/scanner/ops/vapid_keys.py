"""Make a VAPID key pair for web push (spec 11). Run it once per environment and copy the two
values into the Railway variables; they are printed, never stored.

    uv run python -m scanner.ops.vapid_keys
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def generate() -> tuple[str, str]:
    """(public, private): the public key as the browser wants it (uncompressed point) and the
    private key as the raw 32-byte scalar, both base64url without padding."""
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    private = key.private_numbers().private_value.to_bytes(32, "big")
    return _b64url(public), _b64url(private)


def main() -> None:
    public, private = generate()
    print(f"VAPID_PUBLIC_KEY={public}")
    print(f"VAPID_PRIVATE_KEY={private}")
    print("Put the public key on web and scanner, the private key on scanner only.")


if __name__ == "__main__":
    main()
