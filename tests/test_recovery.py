"""Offline fault injection against real wrappers, graph, runtime and HTTP routes. No LLM network."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
import psycopg
from recovery import bounded_call, classify_error
from observability import observability as obs
from workflow import create_graph, tracked_chat_completion
from hitl import SimulationAudit
from runtime import AgentOpsRuntime, APIProblem
from postgres_runtime import PostgresAgentOpsRuntime
from redis_runtime import RedisPostgresAgentOpsRuntime
from main import create_recovery_app
from observability_mcp_client import query_observability_tool
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage


class Recovery(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        obs.clear()

    async def test_classification(self):
        from langgraph.errors import GraphInterrupt
        for error, category in [(GraphInterrupt(()),'workflow_interrupt'), (TimeoutError(),'timeout_error'),
                (ValueError(),'validation_error'), (PermissionError(),'permanent_error'),
                (psycopg.OperationalError(),'dependency_unavailable')]:
            self.assertEqual(classify_error(error), category)

    async def test_transient_recovery_and_trace(self):
        call = AsyncMock(side_effect=[ConnectionError('SECRET'), 'recovered'])
        pause = AsyncMock()
        with obs.run_scope(session_id='retry') as ctx:
            result = await bounded_call(call, kind='tool_attempt', name='search_logs', safe_read=True, sleep=pause)
        self.assertEqual(result,'recovered'); self.assertEqual(call.await_count,2)
        pause.assert_awaited_once_with(.25)
        events = obs.snapshot(ctx.trace_id)
        self.assertEqual([e['status'] for e in events],['error','ok','ok'])
        self.assertEqual(events[0]['metadata']['error_category'],'dependency_unavailable')
        self.assertEqual(events[1]['metadata']['transport_retry_count'],1)
        self.assertNotIn('SECRET',str(events))

    async def test_cancellation_never_retried(self):
        call=AsyncMock(side_effect=asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await bounded_call(call,kind='tool_attempt',name='search_logs',safe_read=True,sleep=AsyncMock())
        self.assertEqual(call.await_count,1)

    async def test_retry_exhaustion(self):
        call=AsyncMock(side_effect=ConnectionError())
        with self.assertRaises(ConnectionError):
            await bounded_call(call,kind='tool_attempt',name='search_logs',safe_read=True,sleep=AsyncMock())
        self.assertEqual(call.await_count,2)

    async def test_unsafe_no_retry(self):
        call=AsyncMock(side_effect=ConnectionError())
        with self.assertRaises(ConnectionError):
            await bounded_call(call,kind='action',name='simulate',sleep=AsyncMock())
        self.assertEqual(call.await_count,1)

    async def test_llm_timeout_permanent_and_sdk_budget(self):
        for error in (TimeoutError('SECRET'),PermissionError('SECRET')):
            create=AsyncMock(side_effect=error)
            api=NS(chat=NS(completions=NS(create=create)))
            from unittest.mock import Mock
            client=NS(with_options=Mock(return_value=api))
            with self.assertRaises(type(error)):
                await tracked_chat_completion(client,'planner',model='deepseek-chat')
            self.assertEqual(create.await_count,1)
            client.with_options.assert_called_once_with(max_retries=0,timeout=30.0)
        self.assertEqual(obs.summary('system')['llm_error_count'],2)
        self.assertNotIn('SECRET',str(obs.snapshot()))

    async def test_llm_rate_limit_only_retry(self):
        class Rejected(Exception): status_code=429
        create=AsyncMock(side_effect=[Rejected(),NS(usage=None)])
        client=NS(chat=NS(completions=NS(create=create)))
        with patch('recovery.asyncio.sleep',new=AsyncMock()):
            reply=await tracked_chat_completion(client,'planner',model='deepseek-chat')
        self.assertIsNone(reply.usage); self.assertEqual(create.await_count,2)
        self.assertEqual(obs.summary('system')['llm_call_count'],2)

    async def test_mcp_protocol_and_invalid_data(self):
        for result in (NS(is_error=True,content=[]),NS(is_error=False,structured_content=None,content=[])):
            call=AsyncMock(return_value=result)
            with self.assertRaises(RuntimeError):
                await query_observability_tool(NS(call_tool=call),'search_logs','INC-001')
            self.assertEqual(call.await_count,1)

    async def test_mcp_timeout_bound(self):
        async def blocked(*args): await asyncio.Event().wait()
        call=AsyncMock(side_effect=blocked)
        with patch('observability_mcp_client.MCP_TIMEOUT_SECONDS',.001):
            with self.assertRaises(TimeoutError):
                await query_observability_tool(NS(call_tool=call),'search_logs','INC-001')
        self.assertEqual(call.await_count,2)
        self.assertEqual(obs.summary('system')['tool_error_count'],1)

    async def test_mcp_connect_cleanup(self):
        from mcp_tool_runtime import MCPToolRuntime
        runtime=MCPToolRuntime({'offline':object()})
        runtime.stack.enter_async_context=AsyncMock(side_effect=ConnectionError('SECRET'))
        runtime.stack.aclose=AsyncMock()
        with self.assertRaises(ConnectionError): await runtime.__aenter__()
        runtime.stack.aclose.assert_awaited_once()
        self.assertEqual(runtime.tool_clients,{})

    async def test_partial_evidence_real_graph(self):
        from incident_mock_data import query_telemetry
        async def tool(name,args):
            if name=='search_logs': return NS(is_error=True,content=[])
            return NS(is_error=False,structured_content=query_telemetry(name,args['incident_id']))
        # A plausible prioritized report cites the missing logs; unchanged validation must reject it.
        replies=[NS(usage=None,choices=[NS(message=NS(content='{"tools":["get_service_topology"]}'))])]
        import json
        from test_rca import valid_result, catalog_for
        replies += [NS(usage=None,choices=[NS(message=NS(content=json.dumps(valid_result(catalog_for('INC-001')))))])]*2
        llm=NS(chat=NS(completions=NS(create=AsyncMock(side_effect=replies))))
        with tempfile.TemporaryDirectory() as tmp:
            graph=create_graph(llm,NS(),NS(retrieve=lambda q:[]),InMemorySaver(),NS(call_tool=tool),SimulationAudit(Path(tmp)/'audit'))
            state=await graph.ainvoke({'messages':[HumanMessage(content='调查 INC-001')]}, {'configurable':{'thread_id':'partial'}})
            self.assertEqual(len(state['observations']),4)
            self.assertEqual(sum('error' not in o for o in state['observations']),3)
            self.assertIsNone(next(o for o in state['observations'] if o['tool']=='search_logs')['data'])
            self.assertEqual(state['rca_report']['diagnosis_status'],'insufficient_evidence')
            self.assertIn('search_logs',state['rca_report']['missing_sources'])
            self.assertFalse(state['action_proposal'])
            self.assertFalse((await graph.aget_state({'configurable':{'thread_id':'partial'}})).next)

    async def test_durable_insert_and_reset_failure(self):
        runtime=PostgresAgentOpsRuntime(); runtime.graph=NS(aget_state=AsyncMock(return_value=NS(next=())))
        runtime.repository=NS(insert=AsyncMock(side_effect=psycopg.OperationalError()),reset=AsyncMock(side_effect=psycopg.OperationalError()))
        with self.assertRaises(psycopg.OperationalError): await runtime.create_session()
        self.assertEqual(runtime.sessions,{})
        runtime.sessions['sid']='original'
        with self.assertRaises(psycopg.OperationalError): await runtime.reset('sid')
        self.assertEqual(runtime.sessions['sid'],'original')

    async def test_checkpoint_read_write_no_success_or_replay(self):
        runtime=AgentOpsRuntime(); runtime.sessions['sid']='thread'
        for method in ('aget_state','ainvoke'):
            runtime.graph=NS(aget_state=AsyncMock(return_value=NS(next=())),ainvoke=AsyncMock(side_effect=psycopg.OperationalError()))
            if method=='aget_state': runtime.graph.aget_state.side_effect=psycopg.OperationalError()
            with self.assertRaises(psycopg.OperationalError): await runtime.ask('sid','hello')
            self.assertEqual(runtime.sessions['sid'],'thread')
            self.assertLessEqual(runtime.graph.ainvoke.await_count,1)

    async def test_hitl_reject_repeat_guard(self):
        import json
        from test_rca import catalog_for, valid_result
        from incident_mock_data import query_telemetry
        from trace_callback import TraceCallback
        with tempfile.TemporaryDirectory() as tmp:
            audit=SimulationAudit(Path(tmp)/'audit')
            runtime=AgentOpsRuntime(); runtime.sessions['sid']='hitl'; runtime.graph=create_graph(
                NS(chat=NS(completions=NS(create=AsyncMock(side_effect=[
                    NS(usage=None,choices=[NS(message=NS(content='{"tools":["get_service_topology"]}'))]),
                    NS(usage=None,choices=[NS(message=NS(content=json.dumps(valid_result(catalog_for('INC-001')))))]),
                ])))), NS(),NS(retrieve=lambda q:[]),InMemorySaver(),
                NS(call_tool=AsyncMock(side_effect=lambda name,args: NS(is_error=False,structured_content=query_telemetry(name,args['incident_id'])))),audit)
            cfg=runtime._config('sid'); cfg['callbacks']=[TraceCallback(obs)]
            with obs.run_scope(session_id='sid') as ctx:
                await runtime.graph.ainvoke({'messages':[HumanMessage(content='调查 INC-001')]},cfg)
            self.assertGreater(obs.summary(ctx.trace_id)['interrupted_count'],0)
            self.assertEqual(obs.summary(ctx.trace_id)['error_count'],0)
            aid=(await runtime.graph.aget_state(cfg)).values['action_proposal']['action_id']
            result=await runtime.approve('sid',aid,'reject')
            self.assertEqual(result['status'],'completed')
            for decision in ('reject','approve'):
                with self.assertRaises(APIProblem) as caught: await runtime.approve('sid',aid,decision)
                self.assertEqual(caught.exception.status,409)
            self.assertEqual([r['status'] for r in audit.read()],['rejected'])

    async def test_failed_read_node_resume_does_not_repeat_prior_nodes(self):
        from langgraph.graph import StateGraph,START,END
        from typing import TypedDict
        class State(TypedDict): done: bool
        counts={'first':0,'read':0}
        def first(state): counts['first']+=1; return {}
        def read(state):
            counts['read']+=1
            if counts['read']==1: raise ConnectionError('injected')
            return {'done':True}
        builder=StateGraph(State);builder.add_node('first',first);builder.add_node('read',read)
        builder.add_edge(START,'first');builder.add_edge('first','read');builder.add_edge('read',END)
        saver=InMemorySaver();graph=builder.compile(checkpointer=saver);cfg={'configurable':{'thread_id':'recover'}}
        with self.assertRaises(ConnectionError): await graph.ainvoke({'done':False},cfg)
        self.assertFalse((await graph.aget_state(cfg)).values['done'])
        # Explicit operator-style resume of a known read-only node; no automatic graph replay policy.
        graph=builder.compile(checkpointer=saver)
        self.assertTrue((await graph.ainvoke(None,cfg))['done'])
        self.assertEqual(counts,{'first':1,'read':2})

    async def test_postgres_start_failure_no_memory_fallback(self):
        from contextlib import asynccontextmanager
        @asynccontextmanager
        async def unavailable(*args, **kwargs):
            raise psycopg.OperationalError('injected unavailable')
            yield
        runtime=PostgresAgentOpsRuntime()
        with patch.dict('os.environ',{'POSTGRES_DSN':'postgresql://unused','DEEPSEEK_API_KEY':'unit-only'}), patch('langgraph.checkpoint.postgres.aio.AsyncPostgresSaver.from_conn_string',unavailable):
            with self.assertRaises(psycopg.OperationalError): await runtime.start()
        self.assertIsNone(runtime.graph);self.assertIsNone(runtime.repository)
        self.assertEqual(runtime.sessions,{})
        with self.assertRaises(APIProblem): await runtime.create_session()

    async def test_real_saver_failure_preserves_pending_checkpoint(self):
        from test_workflow_interrupt import build,report
        from langgraph.types import Command
        class FaultSaver(InMemorySaver):
            fail_read=False
            fail_write=False
            async def aget_tuple(self,*args,**kwargs):
                if self.fail_read: raise psycopg.OperationalError('injected read')
                return await super().aget_tuple(*args,**kwargs)
            async def aput(self,*args,**kwargs):
                if self.fail_write: raise psycopg.OperationalError('injected write')
                return await super().aput(*args,**kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            saver=FaultSaver();audit=SimulationAudit(Path(tmp)/'audit');graph=build(audit)
            # Recompile the same real graph with the fault-injecting saver.
            graph=graph.builder.compile(checkpointer=saver)
            cfg={'configurable':{'thread_id':'saver'}}
            await graph.ainvoke({'report':report('INC-001')},cfg)
            saver.fail_read=True
            with self.assertRaises(psycopg.OperationalError): await graph.aget_state(cfg)
            saver.fail_read=False
            self.assertIn('gate',(await graph.aget_state(cfg)).next)
            self.assertEqual(audit.read(),[])
            # Write failure is tested on a separate new run before any action.
            saver.fail_write=True
            with self.assertRaises(psycopg.OperationalError):
                await graph.ainvoke({'report':report('INC-001')},{'configurable':{'thread_id':'failed-write'}})
            saver.fail_write=False
            self.assertIn('gate',(await graph.aget_state(cfg)).next)
            aid=(await graph.aget_state(cfg)).values['proposal']['action_id']
            await graph.ainvoke(Command(resume={'decision':'reject','action_id':aid}),cfg)
            self.assertEqual([r['status'] for r in audit.read()],['rejected'])


class HTTPFaults(unittest.TestCase):
    def test_dependency_failure_and_rate_limiter(self):
        from fastapi.testclient import TestClient
        class Fake(RedisPostgresAgentOpsRuntime):
            async def start(self):
                self.sessions={'sid':'thread'}
                self.graph=NS(aget_state=AsyncMock(side_effect=psycopg.OperationalError('SECRET')),ainvoke=AsyncMock())
                self.redis_store=NS(hit_rate_limit=AsyncMock(side_effect=ConnectionError('SECRET')))
            async def close(self): pass
        with TestClient(create_recovery_app(Fake)) as client:
            response=client.get('/api/v1/sessions/sid')
            self.assertEqual(response.status_code,503);self.assertNotIn('SECRET',response.text)
            response=client.post('/api/v1/sessions/sid/messages',json={'message':'hello'})
            self.assertEqual(response.status_code,503)
            client.app.state.agentops.graph.ainvoke.assert_not_awaited()
            self.assertEqual(client.app.state.agentops.sessions,{'sid':'thread'})

if __name__=='__main__': unittest.main(verbosity=2)
