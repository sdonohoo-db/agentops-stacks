"""
Batch Inferencing
=================
Spark-based batch inference against deployed Model Serving endpoints.

Use cases:
  - Scheduled large-scale document processing
  - Offline evaluation over new production data
  - Bulk extraction/transformation pipelines

Results are written to Prod Catalog Delta tables and traced to MLflow.
"""
