"""Minimal demo agent for the agentops-stacks v2 eval pattern.

A deliberately trivial agent that echoes the user's input. It exists only
to demonstrate the closed loop (register -> evaluate -> gate) end-to-end —
not to model what a real agent looks like. Replace this with your actual
agent once the pattern is understood.
"""
import mlflow
from mlflow.pyfunc import PythonModel


class HelloAgent(PythonModel):
    @mlflow.trace
    def predict(self, context, model_input):
        if hasattr(model_input, "to_dict"):
            rows = model_input.to_dict(orient="records")
        elif isinstance(model_input, dict):
            rows = [model_input]
        else:
            rows = list(model_input)

        return [self._respond(row) for row in rows]

    def _respond(self, row: dict) -> dict:
        query = row.get("query", "")
        return {"response": f"Hello! You said: {query}"}
