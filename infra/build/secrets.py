"""irl.coop secrets — two-tier (see AGENTS.md "Key operational facts").

Tier 1 — DERIVED keys (HKDF-SHA256 from one master key), for secrets WE
generate. One master secret per instance:

    key(name) = HKDF-SHA256(ikm=master, salt=domain, info="irlcoop/" + name)

The master lives at <instance>/secrets/master.key (0600, gitignored, never in
the repo). Recreate master → rotate the whole stack. Pure crypto (HKDF),
portable, auditable: the derivation is 20 lines, the master is the only secret.

Tier 2 — VAULT secrets, for external keys we CANNOT derive (social OAuth
client ids/secrets, third-party API keys). These live in the ansible vault
(infra/ansible/inventory/group_vars/all/vault.yml — committable AES256
ciphertext; password derived from master.key as secret `vaultpass`, materialized
at <instance>/secrets/vault-pass, 0600). Specs reference them as
${VAULT:<name>} (dots navigate nested keys); the generator decrypts the vault
once at emit time and substitutes the value into gitignored infra/out/.

Usage in app specs: env values may reference ${SECRET:<name>} (derived) or
${VAULT:<name>} (vault) — the generator substitutes both at emit time into
gitignored infra/out/, so the tree carries references only. Secret names are
free-form but SHOULD follow <service>.<purpose> (postgres.irlcoop, minio.root,
onlyoffice.jwt, postiz.linkedin_secret, ...).
"""

import hashlib
import hmac
import os
import secrets as pysecrets
import subprocess
from pathlib import Path

import yaml

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


# --- Tier 2: vault-backed external secrets ---------------------------------


def load_vault(vault_path: Path, vault_pass_file: Path) -> dict:
    """Decrypt the ansible vault into a dict (external secrets we cannot derive).

    Shells out to `ansible-vault view` (the canonical decryptor) so the vault
    ciphertext is never parsed here. Returns {} when the vault file is absent so
    instances with no external secrets never require ansible-vault. Raises on a
    real decrypt failure (wrong password, missing binary) — a ${VAULT:…}
    reference must not silently emit an empty value.
    """
    if not vault_path.exists():
        return {}
    proc = subprocess.run(
        [
            "ansible-vault",
            "view",
            "--vault-password-file",
            str(vault_pass_file),
            str(vault_path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"ansible-vault view {vault_path} failed: {proc.stderr.strip()}"
        )
    return yaml.safe_load(proc.stdout) or {}


def _vault_lookup(vault: dict, name: str) -> str | None:
    """Resolve a (possibly dotted) key against the vault; None if absent."""
    node = vault
    for part in name.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    if not isinstance(node, str):
        raise ValueError(
            f"vault key {name!r} resolves to non-string ({type(node).__name__}); "
            "env values must be strings"
        )
    return node


def substitute_vault(obj, vault: dict):
    """Replace ${VAULT:<name>} (dots navigate nested keys) with vault values.

    Missing keys raise KeyError — a referenced secret that isn't in the vault is
    a configuration error, never a silent empty env value. The lambda replacement
    form is used so vault values are never treated as re.sub templates.
    """
    import re

    if isinstance(obj, str):
        if "${VAULT:" in obj:
            def _rep(m: "re.Match[str]") -> str:
                name = m.group(1)
                val = _vault_lookup(vault, name)
                if val is None:
                    raise KeyError(f"${{VAULT:{name}}} not found in ansible vault")
                return val

            return re.sub(r"\$\{VAULT:([a-zA-Z0-9._-]+)\}", _rep, obj)
        return obj
    if isinstance(obj, dict):
        return {k: substitute_vault(v, vault) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute_vault(v, vault) for v in obj]
    return obj
