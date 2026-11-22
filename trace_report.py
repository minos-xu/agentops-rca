"""Summarize the latest Lesson 62 trace from JSONL."""
import argparse
import json
from deployment_config import data_directory

TRACE = data_directory() / 'evaluations/lesson62_traces.jsonl'

def main():
    if not TRACE.is_file():
        raise SystemExit('No trace yet; send a synthetic incident to Lesson 62 API first.')
    with TRACE.open(encoding='utf8') as f:
        lines = [line for line in f if line.strip()]
    if not lines:
        raise SystemExit('Trace file empty')
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-id", help="Select a request trace instead of the latest")
    args = parser.parse_args()
    items = [json.loads(line) for line in lines]
    matches = [item for item in items if not args.trace_id or item['trace_id'] == args.trace_id]
    if not matches:
        raise SystemExit("Trace ID not found")
    item = matches[-1]
    print(f"Trace ID: {item['trace_id']}")
    print(f"Request duration: {item.get('request_duration_ms')}ms")
    print(f"LangGraph callback spans: {item.get('node_count')}")
    print(f"MCP tool calls: {item.get('tool_call_count')}")
    print(f"Errors: {item.get('error_count')}")
    print(f"LLM calls: {item.get('llm_call_count', 0)}; usage records: {item.get('llm_usage_records', 0)}")
    print(f"Tokens: prompt={item.get('prompt_tokens', 0)} completion={item.get('completion_tokens', 0)} total={item.get('total_tokens', 0)}")
    print(f"LLM failures: {item.get('llm_error_count', 0)}; MCP failures: {item.get('tool_error_count', 0)}")
    print(f"MCP attempts: {item.get('tool_attempt_count', 0)}; failed attempts: {item.get('tool_attempt_error_count', 0)}")
    print(f"Interrupted spans: {item.get('interrupted_count', 0)}")
    for event in item['events']:
        if event['kind'] in ('node','tool','tool_attempt','llm','llm_usage'):
            duration = f"{event['duration_ms']}ms" if event['duration_ms'] is not None else "usage"
            print(f" {event['kind']} {event['name']}: {duration} [{event['status']}] {json.dumps(event['metadata'], ensure_ascii=False)}")
    print('Counts reflect retained events; node callbacks include graph/sequence wrappers.')

if __name__ == '__main__':
    main()
