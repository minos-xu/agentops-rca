"""Offline local-model and real STDIO probes for the package layout (no LLM calls)."""
from __future__ import annotations
import argparse
import asyncio
import importlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('AGENTOPS_ENV_FILE', str(ROOT / '.deployment/nonexistent-probe.env'))
os.environ['AGENTOPS_OFFLINE'] = '1'
os.environ['DEEPSEEK_API_KEY'] = 'offline-probe-placeholder'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ.setdefault('OMP_NUM_THREADS', '2')


def rag():
    from app.core.config import DOCUMENT_DIR, INDEX_PATH
    from app.rag.loader import load_documents
    from app.rag.embedder import embed_text
    from app.rag.retriever import retrieve_prefilter
    from app.rag.reranker import rerank
    from app.rag.rag_pipeline import run_rag
    docs = load_documents(DOCUMENT_DIR)
    assert docs and all('demo_ops_manual' in d['document_id'] for d in docs)
    assert Path(INDEX_PATH).parent == ROOT
    vector = embed_text('如何处理合成事故 INC-001？')
    assert len(vector) > 0
    candidates = retrieve_prefilter('如何处理故障和人工审批？', top_k=5, min_score=0, filters=None)
    assert candidates
    ordered = rerank('如何处理故障和人工审批？', candidates, top_k=2)
    assert ordered and all('rerank_score' in row for row in ordered)
    # Empty evidence is a branch probe, not a retrieval quality metric.
    with patch('app.rag.rag_pipeline.retrieve_prefilter', return_value=[]):
        result = run_rag('empty-evidence-probe')
        assert result['answerable'] is False and result['sources'] == []
    print('PASS: synthetic documents, real embedding/FAISS/reranker; mocked empty-evidence branch; no LLM.')


async def mcp():
    from mcp import Client, StdioServerParameters
    from app.tools.tool_config import SERVERS
    from app.tools.observability_mcp_client import discover_observability_tools, query_observability_tool
    for name, params in SERVERS.items():
        async with Client(params) as client:
            page = await client.list_tools()
            names = {t.name for t in page.tools}
            if name == 'rag':
                assert names == {'rag_query'}
            else:
                assert names == {'calculator', 'get_weather'}
                result = await client.call_tool('calculator', {'operation':'add','a':2,'b':3})
                assert not result.is_error
                serialized = json.dumps(result.model_dump(), default=str)
                assert '5' in serialized and 'add' in serialized
        print(f'PASS: real {name} STDIO discovery/close' + (' and calculator call' if name == 'utility' else ''))
    params = StdioServerParameters(command=sys.executable, args=['-m','app.tools.observability_mcp_server'], cwd=str(ROOT))
    async with Client(params) as client:
        await discover_observability_tools(client)
        for tool in ('get_service_metrics','search_logs','query_traces','get_service_topology'):
            result = await query_observability_tool(client, tool, 'INC-001')
            assert result['synthetic'] is True and result['incident_id'] == 'INC-001'
    print('PASS: real observability STDIO, four synthetic tool calls and safe close; no production telemetry.')


def imports():
    for source in sorted((ROOT / 'app').rglob('*.py')):
        if source.name == '__init__.py':
            continue
        module = '.'.join(source.relative_to(ROOT).with_suffix('').parts)
        importlib.import_module(module)
    print('PASS: every application module imports without circular import failures.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('probe', choices=['rag', 'mcp', 'imports'])
    args = parser.parse_args()
    if args.probe == 'mcp':
        asyncio.run(mcp())
    else:
        globals()[args.probe]()
