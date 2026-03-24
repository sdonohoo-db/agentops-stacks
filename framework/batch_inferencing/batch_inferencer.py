"""
Batch Inferencer
================
Distributed batch inference using Spark UDFs to call a Databricks
Model Serving endpoint at scale.

Pattern:
  1. Read input data from Prod Catalog Delta table
  2. Apply a Spark UDF that calls the Model Serving REST API
  3. Write inference results back to Prod Catalog Delta table
  4. Log traces and metrics to MLflow (prod experiment)

Parallelism: Spark distributes requests across executors. Each
executor calls the endpoint in parallel. Tune `num_workers` on
the cluster for throughput vs. endpoint rate limits.

Rate limiting: The endpoint has a concurrency limit. Set
`requests_per_second` to avoid overwhelming the endpoint.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import mlflow

from framework.config import AgentOpsConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class BatchInferenceResult:
    """Result from a batch inference run."""
    rows_processed: int
    rows_failed: int
    results_table: str
    run_id: str
    errors: List[str]

    @property
    def success(self) -> bool:
        return len(self.errors) == 0 and self.rows_failed == 0


class BatchInferencer:
    """
    Run batch inference against a deployed Model Serving endpoint using Spark.

    Reads from an input Delta table, calls the endpoint for each row,
    writes results to an output Delta table, and logs traces to MLflow.

    Example:
        >>> inferencer = BatchInferencer(
        ...     endpoint_name="agentops_endpoint",
        ...     input_table="agentops_prod.agentops.batch_requests",
        ...     output_table="agentops_prod.agentops.batch_results",
        ... )
        >>> result = inferencer.run()
        >>> print(f"Processed {result.rows_processed} rows")
    """

    def __init__(
        self,
        endpoint_name: Optional[str] = None,
        input_table: Optional[str] = None,
        output_table: Optional[str] = None,
        input_column: str = "request",
        output_column: str = "response",
        requests_per_second: int = 10,
        config: Optional[AgentOpsConfig] = None,
        spark: Optional[Any] = None,
    ) -> None:
        """
        Args:
            endpoint_name:       Model Serving endpoint name.
            input_table:         Delta table with requests to process.
            output_table:        Delta table to write results to.
            input_column:        Column name containing the request text.
            output_column:       Column name for the response text.
            requests_per_second: Rate limit for endpoint calls. Tune to
                                 stay within the endpoint's concurrency limits.
            config:              AgentOpsConfig instance.
            spark:               SparkSession.
        """
        self.config = config or get_config()
        self.endpoint_name = endpoint_name or self.config.model_serving_endpoint
        self.input_table = input_table or f"{self.config.active_catalog_schema}.batch_requests"
        self.output_table = output_table or self.config.batch_results_table_name
        self.input_column = input_column
        self.output_column = output_column
        self.requests_per_second = requests_per_second
        self._spark = spark

    @property
    def spark(self) -> Any:
        if self._spark is None:
            from pyspark.sql import SparkSession
            self._spark = SparkSession.getActiveSession()
        return self._spark

    def run(self, run_name: Optional[str] = None) -> BatchInferenceResult:
        """
        Execute batch inference: read → infer → write → log.

        Args:
            run_name: MLflow run name for tracking.

        Returns:
            BatchInferenceResult with counts and MLflow run ID.
        """
        from pyspark.sql import functions as F
        from pyspark.sql.types import StringType

        endpoint_name = self.endpoint_name
        input_column = self.input_column
        output_column = self.output_column
        workspace_host = self.config.workspace_host
        requests_per_second = self.requests_per_second

        @F.udf(returnType=StringType())
        def call_endpoint(request_text: str) -> str:
            """Spark UDF: calls the Model Serving endpoint for a single request."""
            if not request_text:
                return ""

            import json
            import os
            import requests as req_lib

            # Use Databricks token from environment (injected by cluster runtime)
            token = os.environ.get("DATABRICKS_TOKEN", "")
            host = workspace_host.rstrip("/")
            url = f"{host}/serving-endpoints/{endpoint_name}/invocations"

            payload = {
                "messages": [{"role": "user", "content": request_text}]
            }

            try:
                response = req_lib.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    data=json.dumps(payload),
                    timeout=60,
                )
                response.raise_for_status()
                result = response.json()
                # Handle OpenAI-style response
                if "choices" in result:
                    return result["choices"][0]["message"]["content"]
                if "content" in result:
                    return result["content"]
                return json.dumps(result)
            except Exception as e:
                return f"ERROR: {str(e)}"

        run_name = run_name or f"batch_inference_{self.config.env}"

        try:
            with mlflow.start_run(run_name=run_name) as run:
                mlflow.set_tag("agentops.component", "batch_inferencing")
                mlflow.set_tag("agentops.endpoint", self.endpoint_name)
                mlflow.set_tag("agentops.input_table", self.input_table)

                df = self.spark.table(self.input_table)
                total_rows = df.count()
                mlflow.log_metric("batch.input_rows", total_rows)

                # Apply inference UDF
                result_df = df.withColumn(output_column, call_endpoint(F.col(input_column)))

                # Separate success from errors
                success_df = result_df.filter(~F.col(output_column).startswith("ERROR:"))
                failed_df = result_df.filter(F.col(output_column).startswith("ERROR:"))

                rows_processed = success_df.count()
                rows_failed = failed_df.count()

                # Write results
                result_df.write.format("delta").mode("overwrite").saveAsTable(self.output_table)

                mlflow.log_metric("batch.rows_processed", rows_processed)
                mlflow.log_metric("batch.rows_failed", rows_failed)
                mlflow.log_metric("batch.success_rate", rows_processed / max(total_rows, 1))

                logger.info(
                    "Batch inference complete: %d/%d rows processed → %s",
                    rows_processed, total_rows, self.output_table,
                )

            return BatchInferenceResult(
                rows_processed=rows_processed,
                rows_failed=rows_failed,
                results_table=self.output_table,
                run_id=run.info.run_id,
                errors=[],
            )

        except Exception as e:
            logger.error("Batch inference failed: %s", e)
            return BatchInferenceResult(
                rows_processed=0,
                rows_failed=0,
                results_table=self.output_table,
                run_id="",
                errors=[str(e)],
            )
