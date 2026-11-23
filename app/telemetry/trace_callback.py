"""Record LangGraph callback spans, excluding inputs/outputs and sensitive payloads."""
from app.telemetry.observability import exception_status
import time
from datetime import datetime, timezone
from uuid import UUID
from langchain_core.callbacks import AsyncCallbackHandler

class TraceCallback(AsyncCallbackHandler):
    def __init__(self, collector):
        super().__init__()
        self.collector = collector
        self.started = {}

    def _begin(self, run_id, kind, name):
        ctx = self.collector._current_trace()
        if ctx is not None:
            self.started[str(run_id)] = (time.perf_counter(), kind, str(name)[:80], ctx)

    def _finish(self, run_id, error=None):
        data = self.started.pop(str(run_id), None)
        if data is None:
            return
        start, kind, name, ctx = data
        self.collector._append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'trace_id': ctx.trace_id,
            'session_id': ctx.session_id,
            'incident_id': ctx.incident_id,
            'kind': kind,
            'name': name,
            'duration_ms': round(1000 * (time.perf_counter()-start), 3),
            'status': exception_status(error),
            'metadata': {'error_type': type(error).__name__} if error is not None else {},
        })

    async def on_chain_start(self, serialized, inputs, *, run_id: UUID, parent_run_id=None, **kwargs):
        name = kwargs.get('name') or (serialized or {}).get('name') or 'chain'
        self._begin(run_id, 'node', name)

    async def on_chain_end(self, outputs, *, run_id: UUID, parent_run_id=None, **kwargs):
        self._finish(run_id)

    async def on_chain_error(self, error, *, run_id: UUID, parent_run_id=None, **kwargs):
        self._finish(run_id, error)

    async def on_tool_start(self, serialized, input_str, *, run_id: UUID, parent_run_id=None, **kwargs):
        name = kwargs.get('name') or (serialized or {}).get('name') or 'tool'
        self._begin(run_id, 'tool_callback', name)

    async def on_tool_end(self, output, *, run_id: UUID, parent_run_id=None, **kwargs):
        self._finish(run_id)

    async def on_tool_error(self, error, *, run_id: UUID, parent_run_id=None, **kwargs):
        self._finish(run_id, error)
