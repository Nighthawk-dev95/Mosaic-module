import os

# Databricks Apps injects DATABRICKS_CLIENT_ID/_SECRET automatically for the app's own
# service principal - its presence is how we tell "running as the deployed app" apart from
# "local dev", since the two modes authenticate to EDW completely differently (see
# app.db.databricks_client).
IN_DATABRICKS_APP = bool(os.environ.get("DATABRICKS_CLIENT_ID"))


class Settings:
    in_databricks_app: bool = IN_DATABRICKS_APP

    if IN_DATABRICKS_APP:
        # Hostname/auth come from the SDK's Config() (reads DATABRICKS_CLIENT_ID/_SECRET
        # itself); the warehouse id comes from the SQL warehouse resource bound to this app.
        databricks_warehouse_id: str = os.environ["DATABRICKS_WAREHOUSE_ID"]
    else:
        databricks_server_hostname: str = os.environ["DATABRICKS_SERVER_HOSTNAME"]
        databricks_http_path: str = os.environ["DATABRICKS_HTTP_PATH"]
        databricks_token: str = os.environ["DATABRICKS_TOKEN"]

    # app-25js08's service principal is granted SELECT/USE_SCHEMA on edw_prod.enterprise_analytics
    # ONLY (confirmed live via SHOW GRANTS) - edw_dev.bipa_analytics/mosaictechops and the raw
    # Dataverse schema are unreachable from the deployed app, so this is the real default now,
    # not just a local-dev convenience.
    catalog: str = os.environ.get("MOSAIC_CATALOG", "edw_prod")
    schema: str = os.environ.get("MOSAIC_SCHEMA", "enterprise_analytics")

    @property
    def qualified(self) -> str:
        return f"{self.catalog}.{self.schema}"

    # Foundation Model API endpoint for AI hover-context explanations (see
    # app/services/ai_context_service.py). The name itself is a fixed, workspace-wide moniker -
    # no env var needed to discover it, just to grant CAN_QUERY in production (see
    # resources/practice_command_bhargav.app.yml's serving_endpoint resource). Defaults to the
    # fastest/cheapest Foundation Model available (confirmed via `serving-endpoints list`),
    # right-sized for a short hover tooltip, not a chat-quality response.
    ai_context_serving_endpoint: str = os.environ.get(
        "AI_CONTEXT_SERVING_ENDPOINT", "databricks-claude-haiku-5-5"
    )

    # "Mosaic performance metrics" Genie Space (see app/services/genie_service.py) - an existing,
    # actively-maintained space purpose-built for this exact domain (Deployment/Volume/
    # Efficiency/Read-Times/Capacity via mv_mosaic_* metric views), confirmed live this session.
    # Unlike the serving endpoint above, Genie access is a workspace-object ACL on the space
    # itself (CAN_RUN), not something declared in the app's resources yaml - the deployed app's
    # service principal needs that grant explicitly, separate from its SQL-warehouse access.
    genie_space_id: str = os.environ.get(
        "GENIE_SPACE_ID", "01f174e507061378bcc30e3d9244535b"
    )


settings = Settings()
