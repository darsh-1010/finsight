"""
perf_utils.py
Performance instrumentation — add-only, never modifies existing logic.
Import and apply @timed("label") in existing files.
Does NOT change return values, exception behaviour, or function signatures.
"""

import asyncio
import contextlib
import functools
import logging
import time

logger = logging.getLogger("perf")


def timed(label: str, warn_threshold_s: float = 2.0):
    """
    Decorator that works on both sync and async functions.
    Logs elapsed time at INFO level; WARNING if it exceeds warn_threshold_s.

    Usage:
        @timed("LLM call")
        async def call_llm(...): ...

        @timed("DB query", warn_threshold_s=0.5)
        def fetch_user(...): ...
    """

    def decorator(fn):
        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                t = time.perf_counter()
                try:
                    result = await fn(*args, **kwargs)
                    return result
                finally:
                    elapsed = time.perf_counter() - t
                    lvl = (
                        logging.WARNING if elapsed > warn_threshold_s else logging.INFO
                    )
                    logger.log(lvl, "[PERF] %s: %.3fs", label, elapsed)

            return async_wrapper
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                t = time.perf_counter()
                try:
                    result = fn(*args, **kwargs)
                    return result
                finally:
                    elapsed = time.perf_counter() - t
                    lvl = (
                        logging.WARNING if elapsed > warn_threshold_s else logging.INFO
                    )
                    logger.log(lvl, "[PERF] %s: %.3fs", label, elapsed)

            return sync_wrapper

    return decorator


@contextlib.asynccontextmanager
async def timed_context(label: str, warn_threshold_s: float = 2.0):
    """
    Async context manager for timing code blocks (not functions).

    Usage:
        async with timed_context("vector search"):
            results = await vectordb.query(...)
    """
    t = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - t
        lvl = logging.WARNING if elapsed > warn_threshold_s else logging.INFO
        logger.log(lvl, "[PERF] %s: %.3fs", label, elapsed)
