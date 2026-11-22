"""Run offline project regressions in an isolated source snapshot.

No project .env, deployed database, Redis or existing data directory is copied.
The embedding model must already exist locally; downloads are disabled.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
TESTS = (
    "test_hitl.py",
    "test_workflow_interrupt.py",
    "test_rca.py",
    "test_postgres_store.py",
    "test_redis_degradation.py",
    "test_eval_regression.py",
    "test_eval_scoring.py",
    "test_eval_robustness.py",
    "test_observability.py",
    "test_trace_wiring.py",
    "test_error_classification.py",
    "test_recovery.py",
)


def adapt_fault_injection(source: str) -> str:
    """Keep fault flags visible through the saver's strict-serde shallow clone.

    Only the temporary test double is adapted. Assertions, strict msgpack,
    application modules and the original test remain unchanged.
    """
    changes = (
        (
            "            fail_read=False\n            fail_write=False\n",
            "            def __init__(self):\n"
            "                super().__init__()\n"
            "                self.faults = {'read': False, 'write': False}\n",
            1,
        ),
        ("if self.fail_read:", "if self.faults['read']:", 1),
        ("if self.fail_write:", "if self.faults['write']:", 1),
        ("saver.fail_read=True", "saver.faults['read']=True", 1),
        ("saver.fail_read=False", "saver.faults['read']=False", 1),
        ("saver.fail_write=True", "saver.faults['write']=True", 1),
        ("saver.fail_write=False", "saver.faults['write']=False", 1),
    )
    for before, after, expected in changes:
        if source.count(before) != expected:
            raise RuntimeError("Original FaultSaver changed; review the compatibility adapter before running")
        source = source.replace(before, after)
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "test-results" / "offline")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout per test script in seconds")
    parser.add_argument("--original-tests", action="store_true", help="Run the original test double without the strict-serde clone compatibility adapter")
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="agentops-public-regression-") as directory:
        snapshot = Path(directory)
        for source in ROOT.glob("*.py"):
            shutil.copy2(source, snapshot / source.name)
        shutil.copytree(ROOT / "evaluation", snapshot / "evaluation", ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(ROOT / "tests" / "fixtures" / "trace_api.py", snapshot / "trace_api.py")
        for name in TESTS:
            shutil.copy2(ROOT / "tests" / name, snapshot / name)
        if not args.original_tests:
            recovery = snapshot / "test_recovery.py"
            recovery.write_text(adapt_fault_injection(recovery.read_text(encoding="utf-8")), encoding="utf-8")
        # Explicit values take precedence over inherited credentials. There is
        # deliberately no .env in the snapshot, including for config.py.
        env = os.environ.copy()
        for name in tuple(env):
            if any(word in name.upper() for word in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "POSTGRES", "REDIS")):
                env.pop(name, None)
        env.update({
            "AGENTOPS_ENV_FILE": str(snapshot / ".env"),
            "AGENTOPS_DATA_DIR": str(snapshot / "data"),
            "DEEPSEEK_API_KEY": "offline-test-placeholder",
            "OPENAI_API_KEY": "offline-test-placeholder",
            "POSTGRES_DSN": "postgresql://offline:offline@127.0.0.1:1/offline",
            "REDIS_URL": "redis://127.0.0.1:1/0",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "PYTHONUNBUFFERED": "1",
            "LANGGRAPH_STRICT_MSGPACK": "true",
        })
        # Deny unintended network connections even if a future test loses its
        # mock. Unix sockets, pipes and anonymous socketpairs remain usable.
        (snapshot / "sitecustomize.py").write_text(
            "import socket\n"
            "_connect = socket.socket.connect\n"
            "_connect_ex = socket.socket.connect_ex\n"
            "def _offline_connect(self, address):\n"
            "    if self.family in (socket.AF_INET, socket.AF_INET6):\n"
            "        raise RuntimeError('Lesson64 offline regression forbids network connections')\n"
            "    return _connect(self, address)\n"
            "def _offline_connect_ex(self, address):\n"
            "    if self.family in (socket.AF_INET, socket.AF_INET6):\n"
            "        raise RuntimeError('Lesson64 offline regression forbids network connections')\n"
            "    return _connect_ex(self, address)\n"
            "socket.socket.connect = _offline_connect\n"
            "socket.socket.connect_ex = _offline_connect_ex\n",
            encoding="utf-8",
        )
        env["PYTHONPATH"] = str(snapshot)
        for name in TESTS:
            started = time.monotonic()
            with (output / f"{Path(name).stem}.log").open("w", encoding="utf-8") as log:
                try:
                    process = subprocess.run(
                        [sys.executable, name], cwd=snapshot, env=env,
                        stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout,
                        check=False,
                    )
                    code = process.returncode
                except subprocess.TimeoutExpired:
                    log.write(f"\nTimeout after {args.timeout} seconds\n")
                    code = 124
            result = {"test": name, "exit_code": code, "seconds": round(time.monotonic() - started, 3)}
            results.append(result)
            print(f"{name}: {'PASS' if code == 0 else 'FAIL'}", flush=True)
    summary = {
        "kind": "offline_regression",
        "python": sys.version.split()[0],
        "interpreter": sys.executable,
        "network_connections_allowed": False,
        "existing_env_or_data_copied": False,
        "test_harness_adjustments": [] if args.original_tests else [{
            "test": "test_recovery.py::Recovery.test_real_saver_failure_preserves_pending_checkpoint",
            "change": "Temporary FaultSaver uses a shared fault-flag dict across shallow clones; all assertions and strict msgpack remain enabled.",
            "reason": "LangGraph 1.2.16 / checkpoint 4.3.0 derives a strict-serde saver clone; original boolean flag updates target the unused saver instance.",
            "source_test_modified_by_runner": False,
        }],
        "results": results,
        "passed": all(row["exit_code"] == 0 for row in results),
        "limitations": "Mocked LLM/MCP/database faults and local models; does not validate live DeepSeek or production telemetry.",
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
