"""Opt-in private FastAPI entrypoint with tracing. Use loopback and one worker."""
from app.api.routes import create_app
from app.agent.traced_runtime import InstrumentedAgentOpsRuntime

app = create_app(InstrumentedAgentOpsRuntime)
app.title = 'AgentOps · Instrumented Synthetic RCA (Lesson 62)'
app.version = '0.62.0'
