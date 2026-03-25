"""
DAB Entry Points
================
Console script entry points for all Databricks Asset Bundle python_wheel_task
tasks. Each function is registered in pyproject.toml [project.scripts] and
becomes an executable command when the wheel is installed.

DAB calls these as: <entry_point> [--arg value ...]
Arguments are passed via the `parameters` list in the workflow YAML.

Environment variables (injected by DAB at runtime):
  AGENTOPS_ENV          dev | staging | prod
  DATABRICKS_HOST       Workspace URL
  DATABRICKS_TOKEN      PAT or SP token
  AGENTOPS_DEV_CATALOG  Dev catalog name
  AGENTOPS_PROD_CATALOG Prod catalog name
"""

from __future__ import annotations

import argparse
import logging
import sys

import mlflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Preparation
# ---------------------------------------------------------------------------

def run_ingestion() -> None:
    """Entry point: data_ingestion task."""
    from framework.config import get_config
    from framework.data_preparation.ingestion import DeltaTableIngestion
    from pyspark.sql import SparkSession

    cfg = get_config()
    spark = SparkSession.builder.getOrCreate()
    logger.info("Running data ingestion (env=%s, catalog=%s)", cfg.env, cfg.active_catalog)

    ingester = DeltaTableIngestion(
        table_name=f"{cfg.prod_catalog}.raw.policy_documents",
        text_column="content",
        metadata_columns=["title", "category", "updated_at"],
        spark=spark,
    )
    documents = ingester.ingest()
    logger.info("Ingested %d documents.", len(documents))


def run_chunking() -> None:
    """Entry point: chunking task."""
    from framework.config import get_config
    from framework.data_preparation.chunking import RecursiveCharacterChunker

    cfg = get_config()
    logger.info("Running chunking (env=%s)", cfg.env)

    chunker = RecursiveCharacterChunker(
        chunk_size=512,
        chunk_overlap=64,
        source_table=f"{cfg.active_catalog_schema}.raw_documents",
        target_table=f"{cfg.active_catalog_schema}.document_chunks",
    )
    result = chunker.run()
    logger.info("Chunking complete: %d chunks → %s", result.chunks_produced, result.target_table)


def run_vector_search_indexing() -> None:
    """Entry point: vector_search_indexing task."""
    from framework.config import get_config
    from framework.data_preparation.vector_search_indexing import VectorSearchIndexer

    cfg = get_config()
    logger.info("Running vector search indexing (env=%s)", cfg.env)

    indexer = VectorSearchIndexer(
        endpoint_name=cfg.vector_search_endpoint,
        index_name=cfg.vector_search_index_name,
        source_table=f"{cfg.active_catalog_schema}.document_chunks",
        embedding_column="content",
        embedding_model_endpoint=cfg.embedding_endpoint,
    )
    indexer.create_or_sync()
    logger.info("Vector Search index synced: %s", cfg.vector_search_index_name)


def run_ai_parse_document() -> None:
    """Entry point: ai_parse_document task."""
    from framework.config import get_config
    from framework.data_preparation.unstructured.ai_parse_document import parse_documents
    from pyspark.sql import SparkSession

    cfg = get_config()
    spark = SparkSession.builder.getOrCreate()
    logger.info("Running AI document parsing (env=%s)", cfg.env)

    parse_documents(
        spark=spark,
        input_table=f"{cfg.active_catalog_schema}.raw_pdfs",
        output_table=f"{cfg.active_catalog_schema}.parsed_pdfs",
        file_column="file_path",
    )
    logger.info("AI document parsing complete.")


def run_ai_query_extraction() -> None:
    """Entry point: ai_query_extraction task."""
    from framework.config import get_config
    from framework.data_preparation.unstructured.ai_query_extraction import extract_fields
    from pyspark.sql import SparkSession

    cfg = get_config()
    spark = SparkSession.builder.getOrCreate()
    logger.info("Running AI query extraction (env=%s)", cfg.env)

    extract_fields(
        spark=spark,
        input_table=f"{cfg.active_catalog_schema}.parsed_pdfs",
        output_table=f"{cfg.active_catalog_schema}.extracted_fields",
        extraction_prompt="Extract: title, effective_date, policy_number, summary",
    )
    logger.info("AI query extraction complete.")


def run_unstructured_prep() -> None:
    """Entry point: unstructured_prep task."""
    from framework.config import get_config
    from framework.data_preparation.unstructured.data_preparation import normalize_unstructured
    from pyspark.sql import SparkSession

    cfg = get_config()
    spark = SparkSession.builder.getOrCreate()
    logger.info("Running unstructured data normalization (env=%s)", cfg.env)

    normalize_unstructured(
        spark=spark,
        input_table=f"{cfg.active_catalog_schema}.extracted_fields",
        output_table=f"{cfg.active_catalog_schema}.raw_documents",
    )
    logger.info("Unstructured prep complete.")


# ---------------------------------------------------------------------------
# Agent Development
# ---------------------------------------------------------------------------

def run_router_dev() -> None:
    """Entry point: agent_router_dev task."""
    from framework.config import get_config
    from reference_agent.router.router import build_router

    cfg = get_config()
    logger.info("Building multi-agent router (env=%s)", cfg.env)
    router = build_router()
    logger.info("Router built with %d agents.", len(router.agents))


def run_agent1_tools() -> None:
    """Entry point: agent1_tools task — registers Agent 1 UC tools."""
    from framework.config import get_config
    from reference_agent.agents.agent1.tools import register_agent1_tools

    cfg = get_config()
    logger.info("Registering Agent 1 tools (catalog=%s)", cfg.active_catalog)
    register_agent1_tools(config=cfg)
    logger.info("Agent 1 tools registered.")


def run_agent2_tools() -> None:
    """Entry point: agent2_tools task — registers Agent 2 UC tools."""
    from framework.config import get_config
    from reference_agent.agents.agent2.tools import register_agent2_tools

    cfg = get_config()
    logger.info("Registering Agent 2 tools (catalog=%s)", cfg.active_catalog)
    register_agent2_tools(config=cfg)
    logger.info("Agent 2 tools registered.")


def run_agent1_dev() -> None:
    """Entry point: agent1_dev task — builds, configures, and saves Agent 1."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--query-type", default="ann", choices=["ann", "hybrid"])
    parser.add_argument("--enable-reranking", default="false")
    parser.add_argument("--reranker-candidates", type=int, default=20)
    args = parser.parse_args()

    from framework.config import get_config
    from framework.utils.mlflow_utils import set_experiment_for_env
    from reference_agent.agents.agent1.agent import RAGAgent

    cfg = get_config()
    enable_reranking = args.enable_reranking.lower() == "true"
    set_experiment_for_env("rag_agent", cfg)

    logger.info(
        "Building Agent 1 (query_type=%s, reranking=%s, env=%s)",
        args.query_type, enable_reranking, cfg.env,
    )
    agent = RAGAgent(
        query_type=args.query_type,
        enable_reranking=enable_reranking,
        reranker_candidates=args.reranker_candidates,
        config=cfg,
    )
    with mlflow.start_run(run_name=f"rag_agent_{cfg.env}"):
        agent.save(
            artifact_path="rag_agent",
            registered_model_name=f"{cfg.active_catalog_schema}.rag_agent",
        )
    logger.info("Agent 1 saved and registered.")


def run_agent2_dev() -> None:
    """Entry point: agent2_dev task — builds and saves Agent 2."""
    from framework.config import get_config
    from framework.utils.mlflow_utils import set_experiment_for_env
    from reference_agent.agents.agent2.agent import SummarizationAgent

    cfg = get_config()
    set_experiment_for_env("summarization_agent", cfg)

    logger.info("Building Agent 2 (env=%s)", cfg.env)
    agent = SummarizationAgent(config=cfg)
    with mlflow.start_run(run_name=f"summarization_agent_{cfg.env}"):
        agent.save(
            artifact_path="summarization_agent",
            registered_model_name=f"{cfg.active_catalog_schema}.summarization_agent",
        )
    logger.info("Agent 2 saved and registered.")


def run_agent1_eval() -> None:
    """Entry point: agent1_eval task — evaluation gate for Agent 1."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-size", type=int, default=0)
    parser.add_argument("--strict", default="false")
    args = parser.parse_args()

    from framework.config import get_config
    from framework.evaluation.evaluator import AgentEvaluator, EvaluationThresholds
    from reference_agent.agents.agent1.agent import RAGAgent

    cfg = get_config()
    thresholds = EvaluationThresholds.strict() if args.strict.lower() == "true" else EvaluationThresholds()

    agent = RAGAgent(config=cfg)
    evaluator = AgentEvaluator(agent_name="rag_agent", thresholds=thresholds, config=cfg)

    eval_data = "reference_agent/eval/eval_dataset.jsonl"
    result = evaluator.run(agent=agent, eval_data=eval_data)

    logger.info(result.summary())
    if not result.passed():
        logger.error("Agent 1 evaluation FAILED. Blocking promotion.")
        sys.exit(1)
    logger.info("Agent 1 evaluation PASSED.")


def run_agent2_eval() -> None:
    """Entry point: agent2_eval task — evaluation gate for Agent 2."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-size", type=int, default=0)
    parser.add_argument("--strict", default="false")
    args = parser.parse_args()

    from framework.config import get_config
    from framework.evaluation.evaluator import AgentEvaluator, EvaluationThresholds
    from reference_agent.agents.agent2.agent import SummarizationAgent

    cfg = get_config()
    thresholds = EvaluationThresholds.strict() if args.strict.lower() == "true" else EvaluationThresholds()

    agent = SummarizationAgent(config=cfg)
    evaluator = AgentEvaluator(agent_name="summarization_agent", thresholds=thresholds, config=cfg)

    eval_data = "reference_agent/eval/eval_dataset.jsonl"
    result = evaluator.run(agent=agent, eval_data=eval_data)

    logger.info(result.summary())
    if not result.passed():
        logger.error("Agent 2 evaluation FAILED. Blocking promotion.")
        sys.exit(1)
    logger.info("Agent 2 evaluation PASSED.")


# ---------------------------------------------------------------------------
# App Deployment
# ---------------------------------------------------------------------------

def run_agent1_deploy() -> None:
    """Entry point: agent1_deploy task — registers Agent 1 in UC with @champion alias."""
    from framework.config import get_config
    from framework.deployment.deploy_agent import AgentDeployer

    cfg = get_config()
    logger.info("Deploying Agent 1 to UC (env=%s)", cfg.env)

    deployer = AgentDeployer(config=cfg)
    deployer.deploy(
        agent_module="reference_agent.agents.agent1.agent",
        agent_class="RAGAgent",
        model_name=f"{cfg.active_catalog_schema}.rag_agent",
    )
    logger.info("Agent 1 deployed with @champion alias.")


def run_agent2_deploy() -> None:
    """Entry point: agent2_deploy task — registers Agent 2 in UC with @champion alias."""
    from framework.config import get_config
    from framework.deployment.deploy_agent import AgentDeployer

    cfg = get_config()
    logger.info("Deploying Agent 2 to UC (env=%s)", cfg.env)

    deployer = AgentDeployer(config=cfg)
    deployer.deploy(
        agent_module="reference_agent.agents.agent2.agent",
        agent_class="SummarizationAgent",
        model_name=f"{cfg.active_catalog_schema}.summarization_agent",
    )
    logger.info("Agent 2 deployed with @champion alias.")


def run_app_deploy() -> None:
    """Entry point: app_deploy task — deploys the full multi-agent app to Model Serving.

    Accepts bundle variable values as CLI arguments so prod can enable guardrails
    and rate limiting without code changes:

        run_app_deploy --enable-guardrails true --rate-limit 120
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--enable-guardrails", default="false",
                        help="Attach AI Gateway guardrails (true/false)")
    parser.add_argument("--rate-limit", type=int, default=0,
                        help="Requests per minute (0 = disabled)")
    parser.add_argument("--scale-to-zero", default="true",
                        help="Allow endpoint to scale to zero when idle (true/false)")
    parser.add_argument("--workload-size", default="Small",
                        choices=["Small", "Medium", "Large"],
                        help="Endpoint workload size")
    args = parser.parse_args()

    from framework.config import get_config
    from framework.deployment.deploy_app import AppDeployer

    cfg = get_config()
    enable_guardrails = args.enable_guardrails.lower() == "true"
    scale_to_zero = args.scale_to_zero.lower() == "true"
    rate_limit = args.rate_limit if args.rate_limit > 0 else None

    logger.info(
        "Deploying app (env=%s, guardrails=%s, rate_limit=%s, scale_to_zero=%s, size=%s)",
        cfg.env, enable_guardrails, rate_limit, scale_to_zero, args.workload_size,
    )

    deployer = AppDeployer(config=cfg)
    result = deployer.deploy(
        model_name=f"{cfg.active_catalog_schema}.multi_agent_app",
        model_alias="champion",
        scale_to_zero=scale_to_zero,
        workload_size=args.workload_size,
        enable_guardrails=enable_guardrails,
        rate_limit_per_minute=rate_limit,
    )

    if not result.success:
        logger.error("App deployment FAILED: %s", result.errors)
        sys.exit(1)
    logger.info("App deployed: %s (state=%s)", result.endpoint_url, result.state)


# ---------------------------------------------------------------------------
# Batch Inferencing
# ---------------------------------------------------------------------------

def run_batch_inferencing() -> None:
    """Entry point: batch_inference task."""
    from framework.batch_inferencing.batch_inferencer import BatchInferencer
    from framework.config import get_config

    cfg = get_config()
    logger.info("Running batch inferencing (env=%s)", cfg.env)

    inferencer = BatchInferencer(config=cfg)
    result = inferencer.run()
    logger.info(
        "Batch inferencing complete: %d rows processed, %d errors.",
        result.rows_processed, result.errors,
    )


# ---------------------------------------------------------------------------
# Monitoring (Online Evaluation)
# ---------------------------------------------------------------------------

def run_online_evaluation() -> None:
    """Entry point: monitoring online evaluation tasks.

    CLI args (passed by monitoring_workflow.yml parameters):
        --agent-name   Name of agent to evaluate (e.g. "rag_agent")
        --sample-size  Number of recent production traces to evaluate
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-name", required=True,
                        help="Agent name (must match agentops.agent_name trace tag)")
    parser.add_argument("--sample-size", type=int, default=50,
                        help="Number of production traces to sample")
    args = parser.parse_args()

    from framework.config import get_config
    from framework.evaluation.online_evaluator import OnlineEvaluator

    cfg = get_config()
    logger.info(
        "Running online evaluation for '%s' (sample_size=%d, env=%s)",
        args.agent_name, args.sample_size, cfg.env,
    )

    evaluator = OnlineEvaluator(
        agent_name=args.agent_name,
        trace_sample_size=args.sample_size,
        config=cfg,
    )
    result, alerts = evaluator.run()
    logger.info(result.summary())

    for alert in alerts:
        logger.warning(alert.message())

    if alerts:
        # Non-zero exit so DAB marks the task as failed and sends alert email.
        # Safety failures (safety < 1.0) are always fatal; others are warnings.
        safety_alerts = [a for a in alerts if a.metric_name == "safety"]
        if safety_alerts:
            logger.error("SAFETY REGRESSION DETECTED — exiting with error.")
            sys.exit(2)
        # Non-safety regressions: log but don't fail the job by default
        # (operators can tighten this by catching sys.exit(1) downstream)
        logger.warning("Quality regression detected but not safety-critical.")
