#!/usr/local/bin/python3
"""irl.coop Synapse entrypoint — render ${SYNAPSE_*} env vars into the mounted
config files (homeserver.yaml + the appservice registration) and launch the
stock entrypoint on the rendered copies.

The generated configs carry only ${SYNAPSE_*} placeholders; the actual secrets
arrive as container env (the generator injects them from the derived-key
master). Nothing is ever baked into a config file.
"""
import os
import re


def render(src, dst):
    with open(src) as f:
        content = f.read()
    content = re.sub(
        r"\$\{([A-Z][A-Z0-9_]*)\}",
        lambda m: os.environ.get(m.group(1), ""),
        content,
    )
    with open(dst, "w") as f:
        f.write(content)


render("/config/homeserver.yaml", "/data/homeserver.yaml")

reg = "/config/coop-api-registration.yaml"
if os.path.exists(reg):
    render(reg, "/data/coop-api-registration.yaml")

os.environ["SYNAPSE_CONFIG_PATH"] = "/data/homeserver.yaml"
os.execv("/start.py", ["/start.py"])
