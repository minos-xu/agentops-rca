"""Run a local MCP STDIO server with credential-redacted stderr.

Stdout is left untouched because it carries the MCP JSON-RPC protocol.
"""
from __future__ import annotations

import os
from pathlib import Path
import runpy
import sys

from app.core.deployment_config import load_environment


class RedactedStderr:
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def write(self, value):
        # Replace a whole DSN before its password substring. Read values at write
        # time so credentials loaded during server startup are covered too.
        credentials = sorted({os.getenv(name, "") for name in (
            "DEEPSEEK_API_KEY", "POSTGRES_PASSWORD", "POSTGRES_DSN"
        )} - {""}, key=len, reverse=True)
        for credential in credentials:
            value = value.replace(credential, "[REDACTED]")
        return self.wrapped.write(value)

    def __getattr__(self, name):
        return getattr(self.wrapped, name)


def main():
    load_environment()
    sys.stderr = RedactedStderr(sys.stderr)
    if len(sys.argv) != 2:
        raise SystemExit("Usage: mcp_stdio_launcher.py SERVER_MODULE")
    target = sys.argv[1]
    sys.argv = [target]
    runpy.run_module(target, run_name="__main__")


if __name__ == "__main__":
    main()
