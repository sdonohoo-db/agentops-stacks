"""
Document Chunking
=================
Split ingested documents into chunks suitable for vector search indexing.

Chunks are written to the Dev Catalog as a Delta table with a consistent
schema that the Vector Search indexing step consumes.

Output schema (chunks table):
    chunk_id    STRING  : Globally unique chunk ID (doc_id + "_" + chunk_index)
    doc_id      STRING  : Parent document ID (from ingestion)
    content     STRING  : Chunk text content
    chunk_index INT     : Position of this chunk within its parent document
    metadata    MAP<STRING,STRING>: Inherited from parent document
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional

from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class ChunkingResult:
    """Result from a chunking run."""
    chunks_produced: int
    target_table: str
    errors: List[str]

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class ChunkerBase(ABC):
    """
    Abstract base for document chunking strategies.

    Subclass to implement custom chunking logic. All chunkers read from
    a raw documents Delta table and write a chunks Delta table.
    """

    def __init__(
        self,
        source_table: Optional[str] = None,
        target_table: Optional[str] = None,
        config: Optional[AgentOpsConfig] = None,
        spark: Optional[Any] = None,
    ) -> None:
        self.config = config or get_config()
        self.source_table = source_table or f"{self.config.active_catalog_schema}.raw_documents"
        self.target_table = target_table or self.config.chunks_table_name
        self._spark = spark

    @property
    def spark(self) -> Any:
        if self._spark is None:
            from pyspark.sql import SparkSession
            self._spark = SparkSession.getActiveSession()
        return self._spark

    @abstractmethod
    def chunk_text(self, text: str) -> List[str]:
        """Split a single text string into a list of chunk strings."""
        ...

    def run(self) -> ChunkingResult:
        """
        Read source_table, chunk each document, write to target_table.

        Returns:
            ChunkingResult with chunk count and any errors.
        """
        from pyspark.sql import functions as F
        from pyspark.sql.types import ArrayType, StringType

        logger.info("Chunking %s → %s", self.source_table, self.target_table)

        chunk_udf = F.udf(self.chunk_text, ArrayType(StringType()))

        try:
            df = self.spark.table(self.source_table)

            chunked = (
                df.withColumn("chunks", chunk_udf(F.col("content")))
                .withColumn("chunk_with_index", F.posexplode(F.col("chunks")))
                .select(
                    F.concat_ws("_", F.col("id"), F.col("chunk_with_index.pos").cast("string"))
                    .alias("chunk_id"),
                    F.col("id").alias("doc_id"),
                    F.col("chunk_with_index.col").alias("content"),
                    F.col("chunk_with_index.pos").alias("chunk_index"),
                    F.col("metadata"),
                )
            )

            chunked.write.format("delta").mode("overwrite").saveAsTable(self.target_table)
            count = chunked.count()
            logger.info("Produced %d chunks in %s", count, self.target_table)
            return ChunkingResult(chunks_produced=count, target_table=self.target_table, errors=[])

        except Exception as e:
            logger.error("Chunking failed: %s", e)
            return ChunkingResult(chunks_produced=0, target_table=self.target_table, errors=[str(e)])


class RecursiveCharacterChunker(ChunkerBase):
    """
    Recursive character-based text splitter.

    Splits on paragraph breaks (\\n\\n), then newlines (\\n),
    then sentences (". "), then words (" "), respecting chunk_size
    and chunk_overlap boundaries.

    This is the recommended default for most document types.

    Args:
        chunk_size:     Max characters per chunk (default: 1000).
        chunk_overlap:  Character overlap between adjacent chunks (default: 200).

    Example:
        >>> chunker = RecursiveCharacterChunker(chunk_size=1000, chunk_overlap=200)
        >>> result = chunker.run()
        >>> print(f"Produced {result.chunks_produced} chunks")
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
        source_table: Optional[str] = None,
        target_table: Optional[str] = None,
        config: Optional[AgentOpsConfig] = None,
        spark: Optional[Any] = None,
    ) -> None:
        super().__init__(source_table=source_table, target_table=target_table, config=config, spark=spark)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def chunk_text(self, text: str) -> List[str]:
        if not text:
            return []
        return self._split_recursive(text, self.separators)

    def _split_recursive(self, text: str, separators: List[str]) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        separator = separators[0] if separators else ""
        remaining_separators = separators[1:] if len(separators) > 1 else []

        if separator and separator in text:
            parts = text.split(separator)
        else:
            if remaining_separators:
                return self._split_recursive(text, remaining_separators)
            # Hard split at chunk_size
            return [
                text[i : i + self.chunk_size]
                for i in range(0, len(text), self.chunk_size - self.chunk_overlap)
            ]

        chunks: List[str] = []
        current = ""
        for part in parts:
            candidate = current + separator + part if current else part
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(part) > self.chunk_size and remaining_separators:
                    chunks.extend(self._split_recursive(part, remaining_separators))
                else:
                    current = part

        if current:
            chunks.append(current)

        # Apply overlap by appending the start of the next chunk to the end of the previous
        if self.chunk_overlap > 0 and len(chunks) > 1:
            overlapped: List[str] = [chunks[0]]
            for i in range(1, len(chunks)):
                tail = chunks[i - 1][-self.chunk_overlap :]
                overlapped.append(tail + chunks[i])
            return overlapped

        return chunks


class SemanticChunker(ChunkerBase):
    """
    Sentence-boundary-aware chunker that groups sentences into chunks
    targeting a specific token count, measured by approximate word count.

    Better than fixed-character chunking for documents with natural
    sentence structure (prose, documentation, Q&A).

    Args:
        target_chunk_words:  Target words per chunk (default: 200).
        max_chunk_words:     Hard maximum words per chunk (default: 300).

    Example:
        >>> chunker = SemanticChunker(target_chunk_words=200)
        >>> result = chunker.run()
    """

    def __init__(
        self,
        target_chunk_words: int = 200,
        max_chunk_words: int = 300,
        source_table: Optional[str] = None,
        target_table: Optional[str] = None,
        config: Optional[AgentOpsConfig] = None,
        spark: Optional[Any] = None,
    ) -> None:
        super().__init__(source_table=source_table, target_table=target_table, config=config, spark=spark)
        self.target_chunk_words = target_chunk_words
        self.max_chunk_words = max_chunk_words

    def chunk_text(self, text: str) -> List[str]:
        if not text:
            return []

        # Simple sentence split on ". ", "? ", "! "
        import re
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())

        chunks: List[str] = []
        current_words: List[str] = []

        for sentence in sentences:
            sentence_words = sentence.split()
            if (
                len(current_words) + len(sentence_words) > self.max_chunk_words
                and current_words
            ):
                chunks.append(" ".join(current_words))
                current_words = sentence_words
            else:
                current_words.extend(sentence_words)
                if len(current_words) >= self.target_chunk_words:
                    chunks.append(" ".join(current_words))
                    current_words = []

        if current_words:
            chunks.append(" ".join(current_words))

        return [c for c in chunks if c.strip()]
