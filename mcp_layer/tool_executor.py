"""
mcp_layer/tool_executor.py — Resilient Tool Executor
=====================================================

The executor is the only component that actually instantiates and runs
tools.  It adds:

  1. Parameter validation (Pydantic models on each tool).
  2. Automatic retry with exponential back-off (via tenacity).
  3. Structured logging of every attempt, duration, and outcome.
  4. Consistent ToolResult return — callers never deal with raw exceptions.

DESIGN NOTES:
    The AI layer calls execute(tool_name, params) and receives a ToolResult.
    It never has to know about retries, logging, or parameter schemas.
    The executor is a "middleware" layer between intelligence and action.
"""

from __future__ import annotations
import time
import logging
from typing import Any, Dict, Optional

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from models.tool_result import ToolResult, ToolStatus
from .tool_registry import ToolRegistry, registry as _default_registry

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# CUSTOM EXCEPTION — signals that a retry makes sense
# ──────────────────────────────────────────────────────────────

class RetryableError(Exception):
    """
    Raise this inside a tool's execute() to request an automatic retry.

    Example:
        if not self._window_visible():
            raise RetryableError("GX Works3 window not ready yet")
    """


# ──────────────────────────────────────────────────────────────
# EXECUTOR
# ──────────────────────────────────────────────────────────────

class ToolExecutor:
    """
    Executes registered MCP tools with retry logic and logging.

    Parameters
    ----------
    registry:
        The ToolRegistry to look up tools in.
        Defaults to the global built-in registry.
    max_retries:
        How many times to retry a failing tool before giving up.
    wait_min / wait_max:
        Exponential back-off window in seconds.
    """

    def __init__(
        self,
        registry:    ToolRegistry = _default_registry,
        max_retries: int          = 3,
        wait_min:    float        = 1.0,
        wait_max:    float        = 8.0,
    ) -> None:
        self.registry    = registry
        self.max_retries = max_retries
        self.wait_min    = wait_min
        self.wait_max    = wait_max

    # ── public API ────────────────────────────────────────────

    def execute(
        self,
        tool_name: str,
        params:    Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        """
        Run a tool by name, with automatic retries on RetryableError.

        Args:
            tool_name: Registered tool name (e.g. "open_gxworks3").
            params:    Dictionary of keyword arguments for the tool.

        Returns:
            ToolResult — always returned, never raises.
        """
        params = params or {}
        start  = time.perf_counter()
        attempt_count = 0

        logger.info("→ Executing tool: %s  params=%s", tool_name, params)

        try:
            tool_cls = self.registry.get(tool_name)
        except KeyError as exc:
            return ToolResult.failure(
                tool_name=tool_name,
                error=str(exc),
                message=f"Tool '{tool_name}' not found in registry.",
            )

        # Build tenacity retry decorator dynamically
        retry_decorator = retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(min=self.wait_min, max=self.wait_max),
            retry=retry_if_exception_type(RetryableError),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )

        @retry_decorator
        def _run() -> ToolResult:
            nonlocal attempt_count
            attempt_count += 1
            tool_instance = tool_cls()
            return tool_instance.execute(**params)

        try:
            result = _run()
        except RetryableError as exc:
            elapsed = (time.perf_counter() - start) * 1000
            result = ToolResult.failure(
                tool_name=tool_name,
                error=f"Retries exhausted: {exc}",
                message="Tool failed after all retry attempts.",
                attempts=attempt_count,
                duration_ms=elapsed,
            )
        except Exception as exc:  # noqa: BLE001  — catch-all for safety
            elapsed = (time.perf_counter() - start) * 1000
            logger.exception("Unexpected error in tool '%s'", tool_name)
            result = ToolResult.failure(
                tool_name=tool_name,
                error=str(exc),
                message="Unexpected error during tool execution.",
                attempts=attempt_count,
                duration_ms=elapsed,
            )

        # Attach timing info
        elapsed = (time.perf_counter() - start) * 1000
        result.duration_ms = elapsed
        result.attempts    = attempt_count

        # Log outcome
        if result.ok:
            logger.info(
                "✓ Tool '%s' succeeded in %.0f ms  msg=%s",
                tool_name, elapsed, result.message,
            )
        else:
            logger.error(
                "✗ Tool '%s' FAILED after %d attempt(s) in %.0f ms  error=%s",
                tool_name, attempt_count, elapsed, result.error,
            )

        return result

    def execute_sequence(
        self,
        steps: list[Dict[str, Any]],
        stop_on_failure: bool = True,
    ) -> list[ToolResult]:
        """
        Execute a list of tool calls in order.

        Args:
            steps:
                List of dicts with keys:
                    "tool"   — tool name
                    "params" — (optional) parameter dict
            stop_on_failure:
                If True (default), abort the sequence on the first failure.

        Returns:
            List of ToolResult objects, one per step executed.

        Example:
            executor.execute_sequence([
                {"tool": "open_gxworks3"},
                {"tool": "create_project", "params": {"name": "MyMotor"}},
                {"tool": "open_ladder_editor"},
                {"tool": "insert_contact",  "params": {"address": "X0", "col": 0}},
                {"tool": "insert_coil",     "params": {"address": "Y0", "col": 2}},
                {"tool": "save_project"},
            ])
        """
        results: list[ToolResult] = []

        for step in steps:
            tool_name = step.get("tool", "")
            params    = step.get("params", {})
            result    = self.execute(tool_name, params)
            results.append(result)

            if not result.ok and stop_on_failure:
                logger.error(
                    "Sequence aborted at step '%s': %s", tool_name, result.error
                )
                break

        return results
