"""
Data Ingestion
==============
Abstract base class and concrete implementations for ingesting raw data
into the AgentOps data pipeline. Ingested data is written to the Dev
Catalog as Delta tables for downstream chunking and indexing.

Ingestion reads from the Prod Catalog (read-only) or external sources,
never writing back to prod. This enforces the architectural constraint
that dev workflows cannot corrupt production data.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result from a data ingestion run."""
    rows_ingested: int
    target_table: str
    source: str
    errors: List[str]

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class DataIngestionBase(ABC):
    """
    Abstract base for all AgentOps data ingestion sources.

    Subclass this to add new data sources. Each subclass must implement
    `ingest()`, which reads source data and writes a Delta table to the
    dev catalog with columns: [id STRING, content STRING, metadata MAP<STRING,STRING>].

    The schema contract ensures all downstream chunking and indexing
    components work uniformly regardless of source.
    """

    def __init__(
        self,
        target_table: str,
        config: Optional[AgentOpsConfig] = None,
        spark: Optional[Any] = None,
    ) -> None:
        """
        Args:
            target_table: Fully qualified Delta table name to write to.
                          e.g., "agentops_dev.agentops.raw_documents"
                          Defaults to {config.active_catalog_schema}.raw_documents
            config:       AgentOpsConfig instance.
            spark:        SparkSession. If None, uses active session.
        """
        self.config = config or get_config()
        self.target_table = target_table or f"{self.config.active_catalog_schema}.raw_documents"
        self._spark = spark

    @property
    def spark(self) -> Any:
        if self._spark is None:
            from pyspark.sql import SparkSession
            self._spark = SparkSession.getActiveSession()
        return self._spark

    @abstractmethod
    def ingest(self) -> IngestionResult:
        """
        Read from source and write normalized records to self.target_table.

        Must write a Delta table with columns:
            - id       STRING  : Unique document identifier
            - content  STRING  : Full text content of the document
            - metadata MAP<STRING,STRING>: Source metadata (title, url, date, etc.)

        Returns:
            IngestionResult with row count and any errors encountered.
        """
        ...

    def _write_to_delta(self, df: Any, mode: str = "overwrite") -> int:
        """Write a Spark DataFrame to the target Delta table."""
        df.write.format("delta").mode(mode).saveAsTable(self.target_table)
        count = df.count()
        logger.info("Wrote %d rows to %s (mode=%s)", count, self.target_table, mode)
        return count


class DeltaTableIngestion(DataIngestionBase):
    """
    Ingest from an existing Delta table (typically the Prod Catalog).

    This is the most common ingestion pattern: copy a subset of production
    data into the dev catalog for agent development and testing.

    Example:
        >>> ingestion = DeltaTableIngestion(
        ...     source_table="agentops_prod.agentops.knowledge_base",
        ...     id_column="doc_id",
        ...     content_column="document_text",
        ...     metadata_columns=["title", "source_url", "last_updated"],
        ... )
        >>> result = ingestion.ingest()
        >>> print(f"Ingested {result.rows_ingested} documents")
    """

    def __init__(
        self,
        source_table: str,
        id_column: str = "id",
        content_column: str = "content",
        metadata_columns: Optional[List[str]] = None,
        filter_expr: Optional[str] = None,
        target_table: Optional[str] = None,
        config: Optional[AgentOpsConfig] = None,
        spark: Optional[Any] = None,
    ) -> None:
        cfg = config or get_config()
        super().__init__(
            target_table=target_table or f"{cfg.active_catalog_schema}.raw_documents",
            config=cfg,
            spark=spark,
        )
        self.source_table = source_table
        self.id_column = id_column
        self.content_column = content_column
        self.metadata_columns = metadata_columns or []
        self.filter_expr = filter_expr

    def ingest(self) -> IngestionResult:
        from pyspark.sql import functions as F

        logger.info("Ingesting from %s → %s", self.source_table, self.target_table)

        df = self.spark.table(self.source_table)
        if self.filter_expr:
            df = df.filter(self.filter_expr)

        # Build metadata map from specified columns
        if self.metadata_columns:
            meta_pairs = []
            for col in self.metadata_columns:
                meta_pairs.extend([F.lit(col), F.col(col).cast("string")])
            metadata_col = F.create_map(*meta_pairs)
        else:
            metadata_col = F.create_map().cast("map<string,string>")

        normalized = df.select(
            F.col(self.id_column).cast("string").alias("id"),
            F.col(self.content_column).cast("string").alias("content"),
            metadata_col.alias("metadata"),
        )

        try:
            count = self._write_to_delta(normalized)
            return IngestionResult(
                rows_ingested=count,
                target_table=self.target_table,
                source=self.source_table,
                errors=[],
            )
        except Exception as e:
            logger.error("Ingestion failed: %s", e)
            return IngestionResult(
                rows_ingested=0,
                target_table=self.target_table,
                source=self.source_table,
                errors=[str(e)],
            )


class FileIngestion(DataIngestionBase):
    """
    Ingest documents from DBFS or Unity Catalog Volumes.

    Reads text files (.txt, .md, .pdf parsed to text) from a Volume path
    and writes them to a Delta table for downstream processing.

    Example:
        >>> ingestion = FileIngestion(
        ...     source_path="/Volumes/agentops_dev/agentops/documents/",
        ...     file_extension=".txt",
        ... )
        >>> result = ingestion.ingest()
    """

    def __init__(
        self,
        source_path: str,
        file_extension: str = ".txt",
        target_table: Optional[str] = None,
        config: Optional[AgentOpsConfig] = None,
        spark: Optional[Any] = None,
    ) -> None:
        cfg = config or get_config()
        super().__init__(
            target_table=target_table or f"{cfg.active_catalog_schema}.raw_documents",
            config=cfg,
            spark=spark,
        )
        self.source_path = source_path
        self.file_extension = file_extension

    def ingest(self) -> IngestionResult:
        from pyspark.sql import functions as F

        logger.info("Ingesting files from %s → %s", self.source_path, self.target_table)

        try:
            df = (
                self.spark.read.format("text")
                .option("wholetext", "true")
                .load(f"{self.source_path}*{self.file_extension}")
            )

            normalized = df.select(
                F.monotonically_increasing_id().cast("string").alias("id"),
                F.col("value").alias("content"),
                F.create_map(
                    F.lit("source_path"), F.input_file_name()
                ).alias("metadata"),
            )

            count = self._write_to_delta(normalized)
            return IngestionResult(
                rows_ingested=count,
                target_table=self.target_table,
                source=self.source_path,
                errors=[],
            )
        except Exception as e:
            logger.error("File ingestion failed: %s", e)
            return IngestionResult(
                rows_ingested=0,
                target_table=self.target_table,
                source=self.source_path,
                errors=[str(e)],
            )
