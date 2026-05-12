"""
models/tool_result.py — Tool Execution Result Model
====================================================

Every MCP tool returns a ToolResult.  This uniform wrapper lets the
tool executor, logger, and AI reasoning layer handle successes and
failures consistently without each tool defining its own return shape.
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import datetime


class ToolStatus(str, Enum):
    """Outcome of a single tool execution attempt."""
    SUCCESS = "success"        # Tool completed without errors
    FAILURE = "failure"        # Tool failed (non-retryable or retries exhausted)
    PARTIAL = "partial"        # Some sub-steps succeeded; manual review needed
    SKIPPED = "skipped"        # Tool was intentionally not run (precondition not met)
    RETRYING = "retrying"      # Currently retrying (transient status used internally)


class ToolResult(BaseModel):
    """
    The standardised return value for every MCP tool.

    Attributes
    ----------
    status:
        One of the ToolStatus enum values.
    tool_name:
        The name of the tool that produced this result.
    message:
        A human-readable summary — shown in logs and returned to the AI layer.
    data:
        Arbitrary extra data the tool wants to pass back (screenshot path,
        detected coordinates, generated project path, etc.).
    error:
        The exception message if status is FAILURE.
    attempts:
        How many times the tool was attempted before this result.
    duration_ms:
        Wall-clock milliseconds the tool took to run.
    timestamp:
        ISO-8601 UTC timestamp of when the result was produced.
    """
    status:      ToolStatus            = Field(..., description="Outcome of the tool")
    tool_name:   str                   = Field(..., description="Name of the tool")
    message:     str                   = Field("", description="Human-readable summary")
    data:        Dict[str, Any]        = Field(default_factory=dict)
    error:       Optional[str]         = Field(None, description="Error message on failure")
    attempts:    int                   = Field(1, description="Execution attempt count")
    duration_ms: Optional[float]       = Field(None)
    timestamp:   str                   = Field(
        default_factory=lambda: datetime.datetime.utcnow().isoformat() + "Z"
    )

    # ── convenience constructors ──────────────────────────────

    @classmethod
    def success(
        cls,
        tool_name: str,
        message:   str = "OK",
        data:      Dict[str, Any] | None = None,
        **kwargs,
    ) -> "ToolResult":
        return cls(
            status=ToolStatus.SUCCESS,
            tool_name=tool_name,
            message=message,
            data=data or {},
            **kwargs,
        )

    @classmethod
    def failure(
        cls,
        tool_name: str,
        error:     str,
        message:   str = "Tool failed",
        **kwargs,
    ) -> "ToolResult":
        return cls(
            status=ToolStatus.FAILURE,
            tool_name=tool_name,
            message=message,
            error=error,
            **kwargs,
        )

    # ── helpers ───────────────────────────────────────────────

    @property
    def ok(self) -> bool:
        """True when status is SUCCESS."""
        return self.status == ToolStatus.SUCCESS

    def raise_if_failed(self) -> None:
        """Raise RuntimeError if this result represents a failure."""
        if not self.ok:
            raise RuntimeError(
                f"Tool '{self.tool_name}' failed: {self.error or self.message}"
            )

    def __repr__(self) -> str:
        return (
            f"ToolResult(tool={self.tool_name!r}, "
            f"status={self.status}, msg={self.message!r})"
        )
