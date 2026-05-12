# Databricks notebook source
# MAGIC %md
# MAGIC # Register Hello Agent to Unity Catalog
# MAGIC
# MAGIC Run this once before pushing the project to GitHub — the CI eval gate
# MAGIC loads the registered model from UC, and the gate will fail until this
# MAGIC notebook has been run successfully.
# MAGIC
# MAGIC Re-run only when you change the agent code or want to register a new version.

# COMMAND ----------

dbutils.widgets.text("catalog", "", "Unity Catalog (e.g. hello_agent_dev)")
dbutils.widgets.text("schema", "hello_agent", "Schema within the catalog")

# COMMAND ----------

import sys
sys.path.insert(0, "../src")

import mlflow
import pandas as pd
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient

from hello_agent import HelloAgent

# COMMAND ----------

mlflow.set_registry_uri("databricks-uc")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
if not catalog:
    raise ValueError("Set the 'catalog' widget before running this notebook.")

model_name = f"{catalog}.{schema}.hello_agent"
print(f"Registering to: {model_name}")

# COMMAND ----------

agent = HelloAgent()
example_input = pd.DataFrame([{"query": "hello"}])
example_output = agent.predict(None, example_input)
signature = infer_signature(example_input, example_output)

# COMMAND ----------

with mlflow.start_run(run_name="register-hello-agent"):
    info = mlflow.pyfunc.log_model(
        artifact_path="model",
        python_model=agent,
        signature=signature,
        registered_model_name=model_name,
        input_example=example_input,
    )

version = info.registered_model_version
print(f"Registered version {version} at {info.model_uri}")

# COMMAND ----------

# Assign the @champion alias so the eval gate can reference a stable URI.
client = MlflowClient()
client.set_registered_model_alias(
    name=model_name,
    alias="champion",
    version=version,
)
print(f"Set alias 'champion' -> version {version}")
print(f"Eval gate will load: models:/{model_name}@champion")
