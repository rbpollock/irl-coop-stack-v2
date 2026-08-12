"""irl.coop derived-key secrets — HKDF-SHA256 from one master key.

Design (2026-08-10, Robbie): NO vault files. One master secret per instance,
every stack secret derived deterministically:

    key(name) = HKDF-SHA256(ikm=master, salt=domain, info="irlcoop/" + name)

The master lives at <instance>/secrets/master.key (0600, gitignored, never in
the repo). Recreate master → rotate the whole stack. Pure crypto (HKDF),
portable, auditable: the derivation is 20 lines, the master is the only secret.

Usage in app specs: env values may reference ${SECRET:<name>} — the generator
substitutes the derived value at emit time into gitignored infra/out/, so the
tree carries references only. Names are free-form but SHOULD follow
<service>.<purpose> (postgres.irlcoop, minio.root, onlyoffice.jwt, ...).
"""

import hashlib
import hmac
import os
import secrets as pysecrets
from pathlib import Path

HKDF_HASH = "sha256"
HKDF_LEN = 32  # 256-bit derived keys


def _hkdf(ikm: bytes, salt: bytes, info: bytes, length: int = HKDF_LEN) -> bytes:
    """RFC 5869 HKDF-SHA256: extract-then-expand."""
    # extract: PRK = HMAC(salt, ikm)
    prk = hmac.new(salt, ikm, HKDF_HASH).digest()
    # expand: T(i) = HMAC(PRK, T(i-1) || info || i)
    out = b""
    t = b""
    counter = 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([counter]), HKDF_HASH).digest()
        out += t
        counter += 1
    return out[:length]


def derive(secret_name: str, master_hex: str, domain: str = "irl.coop") -> str:
    """Derive a hex secret for <secret_name> from the master."""
    master = bytes.fromhex(master_hex)
    salt = domain.encode()
    info = f"irlcoop/{secret_name}".encode()
    return _hkdf(master, salt, info).hex()


def load_master(instance_dir: Path) -> str:
    """Load the master key; raise with a clear message if missing."""
    path = instance_dir / "secrets" / "master.key"
    if not path.exists():
        raise FileNotFoundError(
            f"master.key missing at {path} — run: "
            f"openssl rand -hex 32 > {path} && chmod 600 {path}"
        )
    return path.read_text().strip()


def ensure_master(instance_dir: Path) -> Path:
    """Create master.key if absent (idempotent), 0600, gitignored."""
    path = instance_dir / "secrets" / "master.key"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(pysecrets.token_hex(32))
        os.chmod(path, 0o600)
        # gitignore the whole secrets dir if not already covered
        gi = instance_dir / ".gitignore"
        if gi.exists():
            text = gi.read_text()
            if "secrets/" not in text:
                gi.write_text(text.rstrip() + "\nsecrets/\n")
    return path


def substitute(obj, master_hex: str, domain: str):
    """Replace ${SECRET:<name>} in any string of a nested structure."""
    if isinstance(obj, str):
        if "${SECRET:" in obj:
            import re
            return re.sub(
                r"\$\{SECRET:([a-zA-Z0-9._-]+)\}",
                lambda m: derive(m.group(1), master_hex, domain),
                obj,
            )
        return obj
    if isinstance(obj, dict):
        return {k: substitute(v, master_hex, domain) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute(v, master_hex, domain) for v in obj]
    return obj
