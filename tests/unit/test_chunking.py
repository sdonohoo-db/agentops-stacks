"""
Unit Tests: Document Chunking
Tests the chunking strategies without requiring a Databricks connection.
"""

import pytest
from framework.data_preparation.chunking import RecursiveCharacterChunker, SemanticChunker


class TestRecursiveCharacterChunker:
    def setup_method(self):
        self.chunker = RecursiveCharacterChunker(chunk_size=100, chunk_overlap=20)

    def test_short_text_returns_single_chunk(self):
        text = "This is a short sentence."
        chunks = self.chunker.chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_splits_into_multiple_chunks(self):
        text = "A" * 250
        chunks = self.chunker.chunk_text(text)
        assert len(chunks) > 1

    def test_chunks_do_not_exceed_size(self):
        text = " ".join(["word"] * 200)
        chunks = self.chunker.chunk_text(text)
        # Allow for overlap additions
        for chunk in chunks:
            assert len(chunk) <= self.chunker.chunk_size * 2  # generous bound for overlap

    def test_empty_text_returns_empty(self):
        assert self.chunker.chunk_text("") == []

    def test_paragraph_split_preference(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        chunker = RecursiveCharacterChunker(chunk_size=30, chunk_overlap=0)
        chunks = chunker.chunk_text(text)
        # Should split on paragraph boundaries
        assert len(chunks) >= 2

    def test_none_text_returns_empty(self):
        assert self.chunker.chunk_text(None) == []


class TestSemanticChunker:
    def setup_method(self):
        self.chunker = SemanticChunker(target_chunk_words=10, max_chunk_words=15)

    def test_short_text_returns_single_chunk(self):
        text = "This is a short five word sentence."
        chunks = self.chunker.chunk_text(text)
        assert len(chunks) == 1

    def test_long_text_splits_on_sentences(self):
        text = (
            "First sentence is here. Second sentence follows. Third sentence ends. "
            "Fourth sentence is long. Fifth sentence is also here. Sixth sentence concludes."
        )
        chunker = SemanticChunker(target_chunk_words=5, max_chunk_words=8)
        chunks = chunker.chunk_text(text)
        assert len(chunks) > 1

    def test_empty_text_returns_empty(self):
        assert self.chunker.chunk_text("") == []

    def test_chunks_are_non_empty_strings(self):
        text = "Hello world. This is a test. Another sentence here."
        chunks = self.chunker.chunk_text(text)
        for chunk in chunks:
            assert isinstance(chunk, str)
            assert len(chunk.strip()) > 0
