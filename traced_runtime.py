"""Opt-in tracing for Agent requests and HITL resumes."""
import json
import re
from deployment_config import data_directory
from threading import Lock
from redis_runtime import RedisPostgresAgentOpsRuntime
from observability import observability
from trace_callback import TraceCallback

TRACE_FILE = data_directory() / 'evaluations/lesson62_traces.jsonl'
TRACE_LOCK = Lock()

class InstrumentedAgentOpsRuntime(RedisPostgresAgentOpsRuntime):
    def __init__(self):
        super().__init__()
        self.observer = observability
        self.callback = TraceCallback(self.observer)

    async def start(self):
        with self.observer.span('startup', 'runtime.start'):
            return await super().start()

    def _config(self, session_id):
        config = dict(super()._config(session_id))
        existing = config.get('callbacks')
        if existing is None:
            config['callbacks'] = [self.callback]
        elif isinstance(existing, (tuple, list)):
            config['callbacks'] = [*existing, self.callback]
        # Otherwise preserve the existing callback manager instead of replacing it.
        return config

    async def approve(self, session_id, action_id, decision):
        return await self._traced_call(
            session_id, None,
            lambda: super(InstrumentedAgentOpsRuntime, self).approve(session_id, action_id, decision),
        )

    async def ask(self, session_id, question):
        incident = re.search(r'\bINC-\d{3}\b', question, re.I)
        incident_id = incident.group(0).upper() if incident else None
        trace_id = None
        try:
            with self.observer.run_scope(session_id=session_id, incident_id=incident_id) as ctx:
                trace_id = ctx.trace_id
                return await super().ask(session_id, question)
        finally:
            if trace_id:
                self._save_trace(trace_id)

    async def _traced_call(self, session_id, incident_id, invoke):
        trace_id = None
        try:
            with self.observer.run_scope(session_id=session_id, incident_id=incident_id) as ctx:
                trace_id = ctx.trace_id
                return await invoke()
        finally:
            if trace_id:
                self._save_trace(trace_id)

    def _save_trace(self, trace_id):
        try:
            report = self.observer.summary(trace_id)
            TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with TRACE_LOCK, TRACE_FILE.open('a', encoding='utf8') as out:
                out.write(json.dumps(report, ensure_ascii=False) + '\n')
            print(f"[Lesson62 Trace] id={trace_id} request_ms={report['request_duration_ms']} "
                  f"node_spans={report['node_count']} tool_calls={report['tool_call_count']} "
                  f"errors={report['error_count']}")
        except Exception as exc:
            print(f'[Lesson62] Trace write failed: {type(exc).__name__}')
