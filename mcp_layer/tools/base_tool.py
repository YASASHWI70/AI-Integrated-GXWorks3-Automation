"""
mcp_layer/tools/base_tool.py — Abstract Base Class for All MCP Tools
=====================================================================

Every tool in the system inherits from BaseTool.
This enforces a consistent interface so the registry and executor can
treat all tools uniformly.

HOW TO CREATE A NEW TOOL:
--------------------------
    class MyNewTool(BaseTool):
        name        = "my_new_tool"
        description = "Does something useful in GX Works3."
        parameters  = {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "PLC address to operate on"
                }
            },
            "required": ["address"]
        }

        def execute(self, address: str, **kwargs) -> ToolResult:
            # ... do the work ...
            return ToolResult.success(self.name, message=f"Done: {address}")

Then register it:
    from mcp_layer import registry
    registry.register(MyNewTool)
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Dict

from models.tool_result import ToolResult


class BaseTool(ABC):
    """
    Abstract base class for all MCP tools.

    Class Attributes
    ----------------
    name:
        Unique snake_case identifier.  Used as the lookup key in the registry.
    description:
        Plain-English description shown to the AI model when listing tools.
    parameters:
        JSON Schema (dict) describing the tool's input parameters.
        Follow the OpenAI function-calling schema convention.
    """

    name:        ClassVar[str]  = ""
    description: ClassVar[str]  = ""
    parameters:  ClassVar[Dict] = {"type": "object", "properties": {}, "required": []}

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Run the tool with the supplied keyword arguments.

        Must return a ToolResult — never raise unhandled exceptions.
        Wrap unexpected errors in ToolResult.failure().
        """

    @classmethod
    def schema(cls) -> Dict:
        """
        Return the OpenAI-compatible function schema for this tool.

        This is what gets sent to the LLM when listing available tools.
        """
        return {
            "name":        cls.name,
            "description": cls.description,
            "parameters":  cls.parameters,
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
