"""
Unstructured Data Preparation
==============================
Final normalization step in the unstructured data pipeline.
Merges parsed and extracted data into the standard raw_documents schema
so it can flow into the chunking step alongside structured ingestion data.

Input:  extracted_documents table (from ai_query_extraction)
Output: raw_documents table (same schema as DeltaTableIngestion output)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, List, Optional

from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class PreparationResult:
    """Result from the unstructured data preparation step."""
    rows_prepared: int
    target_table: str
    errors: List[str]

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class UnstructuredDataPreparation:
    """
    Normalize extracted unstructured documents into the standard
    raw_documents schema for downstream chunking.

    Merges document content with extracted metadata (summary, topics,
    document_type, entities) into the `metadata` map column, enabling
    metadata-filtered vector search queries.

    Example:
        >>> prep = UnstructuredDataPreparation()
        >>> result = prep.run()
        >>> print(f"Prepared {result.rows_prepared} documents")
    """

    def __init__(
        self,
        source_table: Optional[str] = None,
        target_table: Optional[str] = None,
        merge_mode: str = "append",
        config: Optional[AgentOpsConfig] = None,
        spark: Optional[Any] = None,
    ) -> None:
        """
        Args:
            source_table: Extracted documents table.
                          Defaults to {active_catalog_schema}.extracted_documents
            target_table: Target raw_documents table (shared with structured ingestion).
                          Defaults to {active_catalog_schema}.raw_documents
            merge_mode:   "append" (add to existing) or "overwrite" (replace).
            config:       AgentOpsConfig instance.
            spark:        SparkSession.
        """
        self.config = config or get_config()
        self.source_table = source_table or f"{self.config.active_catalog_schema}.extracted_documents"
        self.target_table = target_table or f"{self.config.active_catalog_schema}.raw_documents"
        self.merge_mode = merge_mode
        self._spark = spark

    @property
    def spark(self) -> Any:
        if self._spark is None:
            from pyspark.sql import SparkSession
            self._spark = SparkSession.getActiveSession()
        return self._spark

    def run(self) -> PreparationResult:
        """
        Normalize extracted_documents → raw_documents schema.

        Returns:
            PreparationResult with row count and errors.
        """
        from pyspark.sql import functions as F

        logger.info("Preparing unstructured data %s → %s", self.source_table, self.target_table)

        try:
            df = self.spark.table(self.source_table)

            normalized = df.select(
                F.col("file_path").alias("id"),
                F.col("content"),
                F.create_map(
                    F.lit("source_path"), F.col("file_path"),
                    F.lit("parse_status"), F.col("parse_status"),
                    F.lit("summary"), F.coalesce(F.col("summary"), F.lit("")),
                    F.lit("key_topics"), F.coalesce(F.col("key_topics"), F.lit("")),
                    F.lit("document_type"), F.coalesce(F.col("document_type"), F.lit("unknown")),
                    F.lit("entities"), F.coalesce(F.col("entities"), F.lit("")),
                ).alias("metadata"),
            )

            normalized.write.format("delta").mode(self.merge_mode).saveAsTable(self.target_table)
            count = normalized.count()
            logger.info("Prepared %d unstructured documents → %s", count, self.target_table)

            return PreparationResult(
                rows_prepared=count,
                target_table=self.target_table,
                errors=[],
            )

        except Exception as e:
            logger.error("Data preparation failed: %s", e)
            return PreparationResult(
                rows_prepared=0,
                target_table=self.target_table,
                errors=[str(e)],
            )
