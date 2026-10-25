"""Thin wrapper around the Databricks Genie Conversation API, scoped to one existing, already-
maintained Genie Space - "Mosaic performance metrics" (space_id in app.config.settings), which
already covers Deployment/Volume/Efficiency/Read-Times/Capacity via its own mv_mosaic_* metric
views. No new Genie Space or metric views are created here.

Response times are real (30s simple, 60-120s+ complex, confirmed live) - every call here is
non-blocking: start/continue a conversation and return its ids immediately, poll status
separately. Never call the SDK's *_and_wait variants or wait_get_message_genie_completed here.

Unlike the AI-context serving endpoint (an App resource declared in the resources yaml), Genie
access is a workspace-object ACL (CAN_RUN) on the space itself - the deployed app's service
principal needs that grant made directly on the space, separate from anything in app.yaml.
"""
import threading

from app.config import settings

_lock = threading.Lock()
_client = None


def _get_client():
    global _client
    if _client is None:
        from databricks.sdk import WorkspaceClient

        if settings.in_databricks_app:
            _client = WorkspaceClient()
        else:
            from databricks.sdk.core import Config

            _client = WorkspaceClient(
                config=Config(
                    host=f"https://{settings.databricks_server_hostname}",
                    token=settings.databricks_token,
                )
            )
    return _client


def ask(question: str, conversation_id: str | None) -> dict:
    """Starts a new conversation, or continues an existing one, and returns immediately
    (no polling here) - {conversation_id, message_id}. Follow-ups reuse conversation_id, per
    Genie's own "same topic" guidance; a new question with conversation_id=None always starts
    a fresh conversation."""
    client = _get_client()
    if conversation_id:
        wait = client.genie.create_message(space_id=settings.genie_space_id, conversation_id=conversation_id, content=question)
    else:
        wait = client.genie.start_conversation(space_id=settings.genie_space_id, content=question)
    return {"conversation_id": wait.conversation_id, "message_id": wait.message_id}


def get_message(conversation_id: str, message_id: str) -> dict:
    """Current state of one message - status, any text reply, the generated SQL, suggested
    follow-up questions, and (once COMPLETED with a query attachment) a small result preview.
    Never raises for a Genie-side failure - that's reported via the `error` field, same
    fail-closed contract as ai_context_service, since this is read by a UI panel that must
    never crash on a transient Genie error."""
    client = _get_client()
    try:
        message = client.genie.get_message(space_id=settings.genie_space_id, conversation_id=conversation_id, message_id=message_id)
    except Exception as exc:  # noqa: BLE001 - surfaced to the panel as a normal error state, not a 500
        return {
            "status": "FAILED",
            "text": None,
            "sql": None,
            "error": str(exc),
            "suggested_questions": [],
            "result": None,
        }

    text = None
    sql = None
    suggested_questions: list[str] = []
    attachment_id = None
    for attachment in message.attachments or []:
        if attachment.text and attachment.text.content:
            text = attachment.text.content
        if attachment.query:
            sql = attachment.query.query
            attachment_id = attachment.attachment_id
        if attachment.suggested_questions and attachment.suggested_questions.questions:
            suggested_questions = list(attachment.suggested_questions.questions)

    status = message.status.value if message.status else "FAILED"
    error = message.error.error if message.error else None

    result = None
    if status == "COMPLETED" and attachment_id:
        try:
            query_result = client.genie.get_message_attachment_query_result(
                space_id=settings.genie_space_id,
                conversation_id=conversation_id,
                message_id=message_id,
                attachment_id=attachment_id,
            )
            stmt = query_result.statement_response
            if stmt and stmt.manifest and stmt.result:
                columns = [c.name for c in (stmt.manifest.schema.columns or [])]
                rows = (stmt.result.data_array or [])[:50]
                result = {"columns": columns, "rows": rows}
        except Exception as exc:  # noqa: BLE001 - the text answer still stands without the table
            print(f"[genie] failed to fetch result rows for {conversation_id}/{message_id}: {exc}", flush=True)

    return {
        "status": status,
        "text": text,
        "sql": sql,
        "error": error,
        "suggested_questions": suggested_questions,
        "result": result,
    }
