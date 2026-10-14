"""Ask a question against the Mosaic Intelligence Genie Space via the Genie Conversation API.

Usage:
    python query_genie.py "What is our overall Mosaic NPS?"
    python query_genie.py --space-id <other_space_id> "..."

Reads DATABRICKS_SERVER_HOSTNAME and DATABRICKS_TOKEN from the environment (same ones
backend/app/db/databricks_client.py uses for the SQL warehouse connection).
"""
import argparse
import os
import sys
import time

import requests

DEFAULT_SPACE_ID = "01f174e507061378bcc30e3d9244535b"
POLL_INTERVAL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 300


def _api(host: str, token: str, method: str, path: str, **kwargs):
    resp = requests.request(
        method,
        f"https://{host}/api/2.0/genie/{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        **kwargs,
    )
    resp.raise_for_status()
    return resp.json()


def ask(host: str, token: str, space_id: str, question: str) -> dict:
    started = _api(
        host, token, "POST", f"spaces/{space_id}/start-conversation",
        json={"content": question},
    )
    conversation_id = started["conversation_id"]
    message_id = started["message_id"] if "message_id" in started else started["message"]["id"]

    deadline = time.time() + POLL_TIMEOUT_SECONDS
    while time.time() < deadline:
        message = _api(
            host, token, "GET",
            f"spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}",
        )
        status = message.get("status")
        if status in ("COMPLETED", "FAILED", "CANCELED"):
            return message
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Genie did not finish within {POLL_TIMEOUT_SECONDS}s (last status={status!r})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--space-id", default=DEFAULT_SPACE_ID)
    args = parser.parse_args()

    host = os.environ["DATABRICKS_SERVER_HOSTNAME"]
    token = os.environ["DATABRICKS_TOKEN"]

    message = ask(host, token, args.space_id, args.question)

    if message["status"] != "COMPLETED":
        print(f"Status: {message['status']}", file=sys.stderr)
        print(message, file=sys.stderr)
        sys.exit(1)

    for attachment in message.get("attachments", []):
        if "text" in attachment:
            print(attachment["text"]["content"])
        elif "query" in attachment:
            query = attachment["query"]
            print(f"-- {query.get('description', '')}")
            print(query["query"])
            result = query.get("result")
            if result:
                print(result)


if __name__ == "__main__":
    main()
