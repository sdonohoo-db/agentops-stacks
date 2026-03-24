"""
Eval Dataset Management
=======================
Load, validate, and persist evaluation datasets for agent quality gates.

Eval datasets are the foundation of evaluation-driven development:
  1. Define expected behavior BEFORE building the agent
  2. Use datasets to measure quality consistently across iterations
  3. Persist datasets in Delta tables for version tracking
  4. Reuse datasets across dev, staging, and validation test tiers

Dataset schema:
    request           STRING  : User input (question or instruction)
    expected_response STRING  : Ground-truth answer (optional but recommended)
    retrieved_context STRING  : Expected retrieval context (optional, for RAG agents)
    metadata          MAP<STRING,STRING>: Dataset and sample metadata
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {"request"}
OPTIONAL_COLUMNS = {"expected_response", "retrieved_context", "metadata"}


def load_eval_dataset(
    source: Union[str, Path, List[Dict]],
    spark: Optional[Any] = None,
) -> pd.DataFrame:
    """
    Load an evaluation dataset from JSONL, JSON, Delta table, or list of dicts.

    Args:
        source: One of:
                - Path to .jsonl file
                - Path to .json file
                - Delta table name (e.g., "agentops_dev.agentops.eval_datasets")
                - List of dicts with at least a "request" key
        spark:  SparkSession (needed only for Delta table sources).

    Returns:
        pandas DataFrame with at minimum a "request" column.

    Raises:
        ValueError: If the dataset is missing required columns.

    Example:
        >>> df = load_eval_dataset("reference_agent/eval/eval_dataset.jsonl")
        >>> print(f"Loaded {len(df)} eval samples")
    """
    if isinstance(source, pd.DataFrame):
        df = source
    elif isinstance(source, list):
        df = pd.DataFrame(source)
    elif isinstance(source, (str, Path)):
        source = str(source)
        if source.endswith(".jsonl"):
            rows = []
            with open(source) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
            df = pd.DataFrame(rows)
        elif source.endswith(".json"):
            with open(source) as f:
                data = json.load(f)
            df = pd.DataFrame(data if isinstance(data, list) else [data])
        else:
            # Assume Delta table
            if spark is None:
                from pyspark.sql import SparkSession
                spark = SparkSession.getActiveSession()
            df = spark.table(source).toPandas()
    else:
        raise ValueError(f"Unsupported source type: {type(source)}")

    _validate_dataset(df, source)
    return df


def _validate_dataset(df: pd.DataFrame, source: str) -> None:
    """Validate that the dataset has required columns and is non-empty."""
    if df.empty:
        raise ValueError(f"Eval dataset from '{source}' is empty.")

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Eval dataset missing required columns: {missing}. "
            f"Got columns: {list(df.columns)}"
        )


def save_eval_dataset_to_delta(
    df: pd.DataFrame,
    dataset_name: str,
    table_name: Optional[str] = None,
    mode: str = "overwrite",
    config: Optional[AgentOpsConfig] = None,
    spark: Optional[Any] = None,
) -> str:
    """
    Persist an evaluation dataset to a Delta table in the active catalog.

    This makes the eval dataset versioned and auditable, and allows the
    staging validation tests to reference the same dataset as dev evaluation.

    Args:
        df:           pandas DataFrame to save.
        dataset_name: Short name for this dataset (e.g., "rag_agent_v1").
        table_name:   Full Delta table name override. Defaults to
                      {active_catalog_schema}.eval_dataset_{dataset_name}
        mode:         "overwrite" or "append".
        config:       AgentOpsConfig instance.
        spark:        SparkSession.

    Returns:
        The Delta table name the dataset was written to.

    Example:
        >>> table = save_eval_dataset_to_delta(df, "rag_agent_v1")
        >>> print(f"Saved to {table}")
    """
    cfg = config or get_config()
    table = table_name or f"{cfg.active_catalog_schema}.eval_dataset_{dataset_name}"

    if spark is None:
        from pyspark.sql import SparkSession
        spark = SparkSession.getActiveSession()

    spark_df = spark.createDataFrame(df)
    spark_df.write.format("delta").mode(mode).saveAsTable(table)
    logger.info("Saved eval dataset '%s' to %s (%d rows)", dataset_name, table, len(df))
    return table


def sample_eval_dataset(
    df: pd.DataFrame,
    n: int = 20,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    Sample a subset of an eval dataset for quick iteration.

    Useful during development when running full evaluation is too slow.

    Args:
        df:           Full eval dataset DataFrame.
        n:            Number of samples to return.
        random_state: Random seed for reproducibility.

    Returns:
        Sampled DataFrame.
    """
    if len(df) <= n:
        return df
    return df.sample(n=n, random_state=random_state).reset_index(drop=True)
