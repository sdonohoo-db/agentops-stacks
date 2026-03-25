"""
AI Query Extraction
===================
Wraps the Databricks `ai_query` built-in function to extract structured
information from parsed document text using an LLM.

This step transforms raw parsed text into structured fields useful for
metadata filtering and retrieval augmentation.

Example extraction schema:
    - summary:      1-2 sentence document summary
    - key_topics:   Comma-separated key topics
    - document_type: Classification (policy, procedure, FAQ, etc.)
    - entities:     Named entities (people, products, dates)

Reference:
    https://docs.databricks.com/en/sql/language-manual/functions/ai_query.html
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result from query extraction."""
    rows_extracted: int
    target_table: str
    errors: List[str]

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


# Default extraction prompt template
DEFAULT_EXTRACTION_PROMPT = """
Extract the following structured information from this document text.
Return a JSON object with these exact keys:
- summary: A 1-2 sentence summary of the document
- key_topics: 3-5 comma-separated key topics
- document_type: One of: policy, procedure, FAQ, report, guide, other
- entities: Comma-separated key named entities (people, products, systems, dates)

Document text:
{content}

Return only valid JSON, no explanation.
"""


class QueryExtractor:
    """
    Extract structured metadata from parsed documents using `ai_query`.

    The structured output enriches the chunks table with filterable
    metadata that agents can use to narrow retrieval (e.g., filter by
    document_type = "policy").

    Example:
        >>> extractor = QueryExtractor()
        >>> result = extractor.run()
        >>> print(f"Extracted metadata for {result.rows_extracted} documents")
    """

    def __init__(
        self,
        source_table: Optional[str] = None,
        target_table: Optional[str] = None,
        extraction_prompt: Optional[str] = None,
        llm_endpoint: Optional[str] = None,
        config: Optional[AgentOpsConfig] = None,
        spark: Optional[Any] = None,
    ) -> None:
        """
        Args:
            source_table:       Parsed documents table (output of DocumentParser).
                                Defaults to {active_catalog_schema}.parsed_documents
            target_table:       Enriched documents output table.
                                Defaults to {active_catalog_schema}.extracted_documents
            extraction_prompt:  Jinja-style prompt with {content} placeholder.
            llm_endpoint:       Databricks FM API endpoint for extraction.
                                Defaults to config.llm_endpoint.
            config:             AgentOpsConfig instance.
            spark:              SparkSession.
        """
        self.config = config or get_config()
        self.source_table = source_table or f"{self.config.active_catalog_schema}.parsed_documents"
        self.target_table = target_table or f"{self.config.active_catalog_schema}.extracted_documents"
        self.extraction_prompt = extraction_prompt or DEFAULT_EXTRACTION_PROMPT
        self.llm_endpoint = llm_endpoint or self.config.llm_endpoint
        self._spark = spark

    @property
    def spark(self) -> Any:
        if self._spark is None:
            from pyspark.sql import SparkSession
            self._spark = SparkSession.getActiveSession()
        return self._spark

    def run(self) -> ExtractionResult:
        """
        Run extraction on all documents in source_table.

        Returns:
            ExtractionResult with row count and errors.
        """
        from pyspark.sql import functions as F

        logger.info("Extracting metadata %s → %s", self.source_table, self.target_table)

        try:
            df = self.spark.table(self.source_table)

            # Build prompt column by replacing {content} in template
            # We use concat to build the prompt dynamically per row
            prompt_prefix = self.extraction_prompt.split("{content}")[0]
            prompt_suffix = self.extraction_prompt.split("{content}")[1] if "{content}" in self.extraction_prompt else ""

            prompt_col = F.concat(
                F.lit(prompt_prefix),
                F.col("content"),
                F.lit(prompt_suffix),
            )

            extracted_df = df.withColumn(
                "extraction_result",
                F.expr(f"ai_query('{self.llm_endpoint}', {prompt_col._jc.toString()})"),
            )

            # Parse JSON response and add as structured columns
            result_df = extracted_df.withColumn(
                "summary", F.get_json_object(F.col("extraction_result"), "$.summary")
            ).withColumn(
                "key_topics", F.get_json_object(F.col("extraction_result"), "$.key_topics")
            ).withColumn(
                "document_type", F.get_json_object(F.col("extraction_result"), "$.document_type")
            ).withColumn(
                "entities", F.get_json_object(F.col("extraction_result"), "$.entities")
            ).drop("extraction_result")

            result_df.write.format("delta").mode("overwrite").saveAsTable(self.target_table)
            count = result_df.count()
            logger.info("Extracted metadata for %d documents → %s", count, self.target_table)

            return ExtractionResult(
                rows_extracted=count,
                target_table=self.target_table,
                errors=[],
            )

        except Exception as e:
            logger.error("Extraction failed: %s", e)
            return ExtractionResult(
                rows_extracted=0,
                target_table=self.target_table,
                errors=[str(e)],
            )
