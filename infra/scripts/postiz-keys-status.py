#!/usr/bin/env python3
"""Postiz integration-key status — what app_ids/secrets you still need.

The *acquisition* of OAuth app credentials is manual (each platform's developer
console, no public "create app" API) — this script automates everything AROUND
it: it enumerates the app-level env vars Postiz reads (per provider), which ones
are already in the ansible vault, which are referenced in postiz.yaml, and the
exact redirect URI to register on each platform.

Run:  uv run --with pyyaml python infra/scripts/postiz-keys-status.py
Never prints secret VALUES — only key names and presence.

The PROVIDERS table is derived from the Postiz fork source
(libraries/nestjs-libraries/src/integrations/social/*.provider.ts +
integration.manager.ts). Re-check it against a fork rebase.
"""

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / "ansible" / "inventory" / "group_vars" / "all" / "vault.yml"
VAULT_PASS = ROOT / "instances" / "dev" / "secrets" / "vault-pass"
POSTIZ_YAML = ROOT / "instances" / "dev" / "apps" / "postiz.yaml"
DOMAIN = "irl.coop"

# provider -> (env var, vault key) pairs. vault key = postiz.<env lowercased>.
# redirect = the callback URI to register on that platform (None for token-style
# integrations that don't use an OAuth redirect).
PROVIDERS = [
    ("X / Twitter", "x", [
        ("X_API_KEY", "postiz.x_api_key"),
        ("X_API_SECRET", "postiz.x_api_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/x"),
    ("LinkedIn", "linkedin", [
        ("LINKEDIN_CLIENT_ID", "postiz.linkedin_client_id"),
        ("LINKEDIN_CLIENT_SECRET", "postiz.linkedin_client_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/linkedin"),
    ("Facebook", "facebook", [
        ("FACEBOOK_APP_ID", "postiz.facebook_app_id"),
        ("FACEBOOK_APP_SECRET", "postiz.facebook_app_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/facebook"),
    ("Instagram", "instagram", [
        ("INSTAGRAM_APP_ID", "postiz.instagram_app_id"),
        ("INSTAGRAM_APP_SECRET", "postiz.instagram_app_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/instagram"),
    ("Threads", "threads", [
        ("THREADS_APP_ID", "postiz.threads_app_id"),
        ("THREADS_APP_SECRET", "postiz.threads_app_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/threads"),
    ("YouTube", "youtube", [
        ("YOUTUBE_CLIENT_ID", "postiz.youtube_client_id"),
        ("YOUTUBE_CLIENT_SECRET", "postiz.youtube_client_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/youtube"),
    ("Google Business", "gmb", [
        ("GOOGLE_GMB_CLIENT_ID", "postiz.google_gmb_client_id"),
        ("GOOGLE_GMB_CLIENT_SECRET", "postiz.google_gmb_client_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/gmb"),
    ("TikTok", "tiktok", [
        ("TIKTOK_CLIENT_ID", "postiz.tiktok_client_id"),
        ("TIKTOK_CLIENT_SECRET", "postiz.tiktok_client_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/tiktok"),
    ("TikTok Business", "tiktok-business", [
        ("TIKTOK_BUSINESS_CLIENT_ID", "postiz.tiktok_business_client_id"),
        ("TIKTOK_BUSINESS_CLIENT_SECRET", "postiz.tiktok_business_client_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/tiktok-business"),
    ("Pinterest", "pinterest", [
        ("PINTEREST_CLIENT_ID", "postiz.pinterest_client_id"),
        ("PINTEREST_CLIENT_SECRET", "postiz.pinterest_client_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/pinterest"),
    ("Reddit", "reddit", [
        ("REDDIT_CLIENT_ID", "postiz.reddit_client_id"),
        ("REDDIT_CLIENT_SECRET", "postiz.reddit_client_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/reddit"),
    ("Discord", "discord", [
        ("DISCORD_CLIENT_ID", "postiz.discord_client_id"),
        ("DISCORD_CLIENT_SECRET", "postiz.discord_client_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/discord"),
    ("Slack", "slack", [
        ("SLACK_ID", "postiz.slack_id"),
        ("SLACK_SECRET", "postiz.slack_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/slack"),
    ("Mastodon", "mastodon", [
        ("MASTODON_CLIENT_ID", "postiz.mastodon_client_id"),
        ("MASTODON_CLIENT_SECRET", "postiz.mastodon_client_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/mastodon"),
    ("Twitch", "twitch", [
        ("TWITCH_CLIENT_ID", "postiz.twitch_client_id"),
        ("TWITCH_CLIENT_SECRET", "postiz.twitch_client_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/twitch"),
    ("Tumblr", "tumblr", [
        ("TUMBLR_CLIENT_ID", "postiz.tumblr_client_id"),
        ("TUMBLR_CLIENT_SECRET", "postiz.tumblr_client_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/tumblr"),
    ("Dribbble", "dribbble", [
        ("DRIBBBLE_CLIENT_ID", "postiz.dribbble_client_id"),
        ("DRIBBBLE_CLIENT_SECRET", "postiz.dribbble_client_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/dribbble"),
    ("Kick", "kick", [
        ("KICK_CLIENT_ID", "postiz.kick_client_id"),
        ("KICK_SECRET", "postiz.kick_secret"),
    ], f"https://postiz.{DOMAIN}/integrations/social/kick"),
    # Token-style (no OAuth redirect; the "secret" is a bot/API key):
    ("Telegram", "telegram", [("TELEGRAM_TOKEN", "postiz.telegram_token")], None),
    ("Farcaster (Neynar)", "farcaster", [
        ("NEYNAR_CLIENT_ID", "postiz.neynar_client_id"),
        ("NEYNAR_SECRET_KEY", "postiz.neynar_secret_key"),
    ], None),
    ("MeWe", "mewe", [
        ("MEWE_APP_ID", "postiz.mewe_app_id"),
        ("MEWE_API_KEY", "postiz.mewe_api_key"),
    ], None),
    ("Whop", "whop", [("WHOP_CLIENT_ID", "postiz.whop_client_id")], None),
]

# Per-user auth — no shared app_id to create (members bring their own account):
PER_USER = [
    "bluesky", "dev.to", "hashnode", "medium", "lemmy", "nostr",
    "wordpress", "listmonk", "moltbook", "skool",
]


def load_vault():
    if not VAULT.exists():
        return {}
    p = subprocess.run(
        ["ansible-vault", "view", "--vault-password-file", str(VAULT_PASS), str(VAULT)],
        capture_output=True, text=True,
    )
    if p.returncode != 0:
        print(f"WARN: could not decrypt vault ({p.stderr.strip()})")
        return {}
    return yaml.safe_load(p.stdout) or {}


def flatten(d, prefix=""):
    out = set()
    for k, v in d.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out |= flatten(v, full)
        else:
            out.add(full)
    return out


def main():
    vault_keys = flatten(load_vault())
    spec = POSTIZ_YAML.read_text() if POSTIZ_YAML.exists() else ""

    configured, missing, in_vault_only = [], [], []
    for platform, ident, envs, redirect in PROVIDERS:
        keys = [vk for _, vk in envs]
        have = [vk for vk in keys if vk in vault_keys]
        referenced = [vk for vk in keys if vk in spec]
        if len(have) == len(keys) and all(referenced):
            configured.append((platform, redirect))
        elif len(have) == len(keys):
            in_vault_only.append((platform, redirect))
        else:
            missing.append((platform, envs, redirect))

    print("=== Postiz integration keys — status ===\n")
    print(f"Configured (in vault + referenced in postiz.yaml): {len(configured)}")
    for platform, _ in configured:
        print(f"  ✓ {platform}")
    print(f"\nIn vault, but NOT referenced in postiz.yaml: {len(in_vault_only)}")
    for platform, _ in in_vault_only:
        print(f"  ◐ {platform}")
    print(f"\nMissing — go create these apps and add to the vault: {len(missing)}\n")
    for platform, envs, redirect in missing:
        print(f"  • {platform}")
        for env, vk in envs:
            print(f"      {env:28s} -> {vk}")
        if redirect:
            print(f"      redirect URI: {redirect}")
    print("\nPer-user auth (no shared app_id to create):")
    print("  " + ", ".join(PER_USER))
    print("\nAdd a key: ansible-vault edit --vault-password-file "
          "infra/instances/dev/secrets/vault-pass "
          "infra/ansible/inventory/group_vars/all/vault.yml")


if __name__ == "__main__":
    main()
