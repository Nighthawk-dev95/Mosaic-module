"""Governed metric registry - the single declaration of what each Mosaic metric means.

See registry.py. Nothing in this package queries EDW; it only composes SQL and carries
metadata, so it is importable from tests without a Databricks connection.
"""
