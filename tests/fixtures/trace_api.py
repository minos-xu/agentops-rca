"""Opt-in private FastAPI entrypoint with tracing. Use loopback and one worker."""
from api_routes import create_app
from traced_runtime import InstrumentedAgentOpsRuntime

app = create_app(InstrumentedAgentOpsRuntime)
app.title = 'AgentOps · Instrumented Synthetic RCA (Lesson 62)'
app.version = '0.62.0'
