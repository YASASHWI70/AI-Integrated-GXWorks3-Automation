"""
mcp_layer/tool_registry.py — MCP Tool Registry
===============================================

WHAT IS MCP? (Model Context Protocol)
--------------------------------------
MCP is an open standard (by Anthropic) that lets AI models invoke external
"tools" in a structured, well-typed way.  Each tool has:

  • name        — unique identifier (e.g. "open_gxworks3")
  • description — what the tool does (shown to the AI model)
  • parameters  — JSON Schema describing the tool's inputs
  • execute()   — the Python function that does the actual work

This module implements a lightweight version of that pattern.  Tools are
registered once at startup.  The executor (tool_executor.py) then calls
them by name, passing validated parameters.

ARCHITECTURE BENEFIT:
    The AI layer never imports GX Works3 automation code directly.
    It only knows about tool names and schemas.  This makes it trivial to:
      - Swap out the UI automation backend (e.g. switch from pyautogui
        to a COM/DDE API when one becomes available)
      - Add new tools without touching AI code
      - Test the AI layer with mock tools
"""

from __future__ import annotations
import logging
from typing import Dict, List, Optional, Type

from .tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Central registry that maps tool names → tool classes.

    Usage
    -----
        registry = ToolRegistry()
        registry.register(OpenGXWorks3Tool)
        tool_cls = registry.get("open_gxworks3")
        result = tool_cls().execute()

    The global `registry` singleton (bottom of this file) is pre-populated
    with all built-in tools by the mcp_layer package.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, Type[BaseTool]] = {}

    # ── registration ─────────────────────────────────────────

    def register(self, tool_class: Type[BaseTool]) -> None:
        """
        Register a tool class.

        Args:
            tool_class: A concrete subclass of BaseTool.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        name = tool_class.name
        if name in self._tools:
            raise ValueError(
                f"Tool '{name}' is already registered. "
                "Use register_or_replace() to overwrite."
            )
        self._tools[name] = tool_class
        logger.debug("Registered tool: %s", name)

    def register_or_replace(self, tool_class: Type[BaseTool]) -> None:
        """Register a tool, overwriting any existing entry with the same name."""
        self._tools[tool_class.name] = tool_class
        logger.debug("Registered (replace) tool: %s", tool_class.name)

    # ── lookup ───────────────────────────────────────────────

    def get(self, name: str) -> Type[BaseTool]:
        """
        Return the tool class for the given name.

        Raises:
            KeyError: If no tool with that name is registered.
        """
        if name not in self._tools:
            available = ", ".join(sorted(self._tools.keys()))
            raise KeyError(
                f"Unknown tool '{name}'. Available tools: {available}"
            )
        return self._tools[name]

    def has(self, name: str) -> bool:
        """Return True if a tool with this name is registered."""
        return name in self._tools

    # ── introspection ─────────────────────────────────────────

    def list_tools(self) -> List[Dict]:
        """
        Return a list of tool descriptors suitable for passing to an LLM.

        Each descriptor follows the OpenAI / Anthropic function-calling schema:
            {
                "name": "open_gxworks3",
                "description": "...",
                "parameters": { ... JSON Schema ... }
            }
        """
        return [cls.schema() for cls in self._tools.values()]

    def list_names(self) -> List[str]:
        """Return sorted list of all registered tool names."""
        return sorted(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        return f"ToolRegistry({self.list_names()})"


# ──────────────────────────────────────────────────────────────
# GLOBAL SINGLETON
# ──────────────────────────────────────────────────────────────
# Import and register all built-in tools here.
# New tools only need to be added to this list to become available.

registry = ToolRegistry()

def _register_builtin_tools() -> None:
    """Import and register all built-in GX Works3 tools."""
    from .tools.open_gxworks3      import OpenGXWorks3Tool
    from .tools.create_project     import CreateProjectTool
    from .tools.open_ladder_editor import OpenLadderEditorTool
    from .tools.insert_contact     import InsertContactTool
    from .tools.insert_coil        import InsertCoilTool
    from .tools.save_project       import SaveProjectTool

    for tool_cls in [
        OpenGXWorks3Tool,
        CreateProjectTool,
        OpenLadderEditorTool,
        InsertContactTool,
        InsertCoilTool,
        SaveProjectTool,
    ]:
        registry.register(tool_cls)

_register_builtin_tools()
