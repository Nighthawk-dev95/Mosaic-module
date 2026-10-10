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


settings = Settings()
