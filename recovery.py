"""Conservative recovery: retry only known-safe reads or explicitly rejected LLM calls."""
from __future__ import annotations
import asyncio
from observability import observability, exception_status

LLM_TIMEOUT_SECONDS = 30.0
MCP_TIMEOUT_SECONDS = 10.0
MAX_ATTEMPTS = 2


def classify_error(error: BaseException) -> str:
    if exception_status(error) == 'interrupted':
        return 'workflow_interrupt'
    mro = {(c.__module__.split('.')[0], c.__name__) for c in type(error).__mro__}
    names = {name for _, name in mro}
    if isinstance(error, TimeoutError) or names & {'APITimeoutError', 'ReadTimeout', 'ConnectTimeout', 'TimeoutException', 'TimeoutError'}:
        return 'timeout_error'
    transport_connection = any(module in {'redis', 'httpx', 'httpx2'} and name in {'ConnectionError', 'ConnectError'} for module, name in mro)
    if transport_connection or isinstance(error, ConnectionError) or names & {'APIConnectionError', 'OperationalError', 'InterfaceError', 'ConnectionClosed', 'ClosedResourceError', 'BrokenResourceError'}:
        return 'dependency_unavailable'
    status = getattr(error, 'status_code', None)
    if status in {408, 409, 429} or isinstance(status, int) and status >= 500:
        return 'transient_error'
    if isinstance(error, (ValueError, TypeError)) or names & {'ValidationError', 'RCAValidationError'}:
        return 'validation_error'
    return 'permanent_error'


async def bounded_call(invoke, *, kind, name, metadata=None, safe_read=False,
                       rejected_llm=False, timeout=None, sleep=asyncio.sleep):
    """At most two attempts. Never automatically replay an ambiguous LLM/write request.

    The caller, not model output, must establish that safe_read is true.
    """
    for attempt in range(MAX_ATTEMPTS):
        fields = {**(metadata or {}), 'attempt': attempt + 1, 'transport_retry_count': attempt}
        try:
            with observability.span(kind, name, metadata=fields):
                try:
                    if timeout is None:
                        return await invoke()
                    return await asyncio.wait_for(invoke(), timeout)
                except Exception as error:
                    fields['error_category'] = classify_error(error)
                    raise
        except Exception as error:
            category = classify_error(error)
            retryable = (safe_read and category in {'transient_error', 'timeout_error', 'dependency_unavailable'}) or (
                rejected_llm and getattr(error, 'status_code', None) == 429)
            if not retryable or attempt + 1 == MAX_ATTEMPTS:
                raise
            await sleep(0.25 * (2 ** attempt))
