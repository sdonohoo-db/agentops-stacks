"""
AI Document Parser
==================
Wraps the Databricks `ai_parse_document` built-in function to extract
text from unstructured documents (PDFs, DOCX, HTML, images with OCR)
stored in Unity Catalog Volumes.

ai_parse_document returns a structured JSON result containing:
    - parsed_content: Extracted text
    - metadata: Document properties (page count, author, etc.)
    - status: "SUCCESS" or "ERROR"

Reference:
    https://docs.databricks.com/en/sql/language-manual/functions/ai_parse_document.html
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, List, Optional

from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Result from document parsing."""
    rows_parsed: int
    rows_failed: int
    target_table: str
    errors: List[str]

    @property
    def success(self) -> bool:
        return len(self.errors) == 0 and self.rows_failed == 0


class DocumentParser:
    """
    Parse unstructured documents from a Unity Catalog Volume using
    Databricks `ai_parse_document`.

    The parsed output is written to a Delta table that feeds the
    `ai_query_extraction` step.

    Example:
        >>> parser = DocumentParser(
        ...     source_path="/Volumes/agentops_dev/agentops/raw_pdfs/",
        ... )
        >>> result = parser.run()
        >>> print(f"Parsed {result.rows_parsed} documents")
    """

    def __init__(
        self,
        source_path: str,
        target_table: Optional[str] = None,
        file_format: str = "pdf",
        config: Optional[AgentOpsConfig] = None,
        spark: Optional[Any] = None,
    ) -> None:
        """
        Args:
            source_path:  Volume path containing documents to parse.
                          e.g., "/Volumes/agentops_dev/agentops/raw_docs/"
            target_table: Delta table to write parsed results.
                          Defaults to {active_catalog_schema}.parsed_documents
            file_format:  Document format hint: "pdf", "docx", "html" (default: "pdf").
            config:       AgentOpsConfig instance.
            spark:        SparkSession.
        """
        self.config = config or get_config()
        self.source_path = source_path
        self.target_table = target_table or f"{self.config.active_catalog_schema}.parsed_documents"
        self.file_format = file_format
        self._spark = spark

    @property
    def spark(self) -> Any:
        if self._spark is None:
            from pyspark.sql import SparkSession
            self._spark = SparkSession.getActiveSession()
        return self._spark

    def run(self) -> ParseResult:
        """
        List files in source_path and parse each using ai_parse_document.

        Returns:
            ParseResult with counts and errors.
        """
        from pyspark.sql import functions as F

        logger.info("Parsing documents from %s → %s", self.source_path, self.target_table)

        # List files in the volume
        files_df = self.spark.sql(f"LIST '{self.source_path}'")
        file_paths = [row.path for row in files_df.collect()]
        logger.info("Found %d files to parse", len(file_paths))

        if not file_paths:
            return ParseResult(rows_parsed=0, rows_failed=0, target_table=self.target_table, errors=[])

        # Create a DataFrame of file paths and parse with ai_parse_document
        paths_df = self.spark.createDataFrame(
            [(p,) for p in file_paths], ["file_path"]
        )

        parsed_df = paths_df.withColumn(
            "parse_result",
            F.expr(f"ai_parse_document(file_path)"),
        ).select(
            F.col("file_path"),
            F.col("parse_result.parsed_content").alias("content"),
            F.col("parse_result.metadata").alias("parse_metadata"),
            F.col("parse_result.status").alias("parse_status"),
        )

        # Filter and count results
        success_df = parsed_df.filter(F.col("parse_status") == "SUCCESS")
        failed_df = parsed_df.filter(F.col("parse_status") != "SUCCESS")

        rows_parsed = success_df.count()
        rows_failed = failed_df.count()

        if rows_failed > 0:
            failed_paths = [row.file_path for row in failed_df.select("file_path").collect()]
            logger.warning("Failed to parse %d files: %s", rows_failed, failed_paths[:5])

        success_df.write.format("delta").mode("overwrite").saveAsTable(self.target_table)
        logger.info("Wrote %d parsed documents to %s", rows_parsed, self.target_table)

        return ParseResult(
            rows_parsed=rows_parsed,
            rows_failed=rows_failed,
            target_table=self.target_table,
            errors=[f"Failed to parse: {p}" for p in (failed_df.select("file_path").collect() if rows_failed > 0 else [])],
        )
