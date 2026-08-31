import os


class Settings:
    databricks_server_hostname: str = os.environ["DATABRICKS_SERVER_HOSTNAME"]
    databricks_http_path: str = os.environ["DATABRICKS_HTTP_PATH"]
    databricks_token: str = os.environ["DATABRICKS_TOKEN"]
    catalog: str = os.environ.get("MOSAIC_CATALOG", "edw_dev")
    schema: str = os.environ.get("MOSAIC_SCHEMA", "mosaictechops")

    @property
    def qualified(self) -> str:
        return f"{self.catalog}.{self.schema}"


settings = Settings()
