"""Posts an EDW Mosaic Health alert to the Teams webhook configured via the Workflows
"Send webhook alerts to a channel" template.

That template requires the POST body to be an Adaptive Card or legacy MessageCard
payload (confirmed from its own setup page) - a plain {"text": ...} body is rejected.
Uses the legacy MessageCard format here since it's simpler than a full Adaptive Card
schema and the template explicitly supports both.

Reads the webhook URL from the TEAMS_WEBHOOK_URL environment variable - never hardcoded,
never logged, never committed. If that variable isn't set, this exits without erroring
loudly (so the scheduled task's other work isn't blocked by Teams delivery not being
configured yet).

Reads it from the Windows user-environment registry store directly (via winreg), not
just os.environ - confirmed this session that a long-running parent process (this app)
does not pick up a setx'd variable until it itself restarts, so any child process it
spawns inherits a stale environment indefinitely. Querying the registry directly makes
this robust regardless of how old the calling process is. Falls back to os.environ for
portability (e.g. if ever run somewhere winreg isn't available or the var was exported
some other way).

Usage: python post_to_teams.py "<title>" "<message text, markdown-ish>" ["<hex color, no #>"]
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request


def _get_webhook_url() -> str | None:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, "TEAMS_WEBHOOK_URL")
            if value:
                return value
    except (ImportError, FileNotFoundError, OSError):
        pass
    return os.environ.get("TEAMS_WEBHOOK_URL")


def post(title: str, text: str, color: str = "D03B3B") -> None:
    webhook_url = _get_webhook_url()
    if not webhook_url:
        print("[post_to_teams] TEAMS_WEBHOOK_URL not set - skipping Teams post.")
        return

    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "summary": title,
        "themeColor": color,
        "title": title,
        "text": text,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"[post_to_teams] posted, status {resp.status}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: post_to_teams.py <title> <text> [color]")
        sys.exit(1)
    title_arg = sys.argv[1]
    text_arg = sys.argv[2]
    color_arg = sys.argv[3] if len(sys.argv) > 3 else "D03B3B"
    post(title_arg, text_arg, color_arg)
