"""
Polaris Tool Registry

Auto-discovers all *_tools.py modules and exposes:
  - get_all_tools()          -> list of Anthropic tool definitions
  - execute_tool(name, args) -> result string from running a tool
"""

import importlib
import pkgutil
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auto-discovery: import every *_tools module in this package
# ---------------------------------------------------------------------------

_TOOL_DEFS: List[Dict] = []          # All Anthropic tool schemas
_HANDLERS: Dict[str, callable] = {}  # tool_name -> handler function

def _discover_tools():
    """Scan this package for *_tools modules, collect TOOLS and HANDLERS."""
    global _TOOL_DEFS, _HANDLERS

    package_path = __path__
    package_name = __name__

    for finder, module_name, is_pkg in pkgutil.iter_modules(package_path):
        if not module_name.endswith("_tools"):
            continue

        fqn = f"{package_name}.{module_name}"
        try:
            mod = importlib.import_module(fqn)
        except Exception as e:
            logger.warning(f"Failed to import {fqn}: {e}")
            continue

        # Collect tool definitions
        tools = getattr(mod, "TOOLS", [])
        _TOOL_DEFS.extend(tools)

        # Collect handlers
        handlers = getattr(mod, "HANDLERS", {})
        for name, fn in handlers.items():
            if name in _HANDLERS:
                logger.warning(f"Duplicate tool name '{name}' from {fqn}, overwriting")
            _HANDLERS[name] = fn

        logger.debug(f"Loaded {len(tools)} tools from {module_name}")

# Run discovery on import
_discover_tools()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_all_tools() -> List[Dict]:
    """Return list of all registered Anthropic tool definitions."""
    return list(_TOOL_DEFS)


def execute_tool(name: str, args: dict) -> str:
    """
    Execute a tool by name with the given arguments.

    Args:
        name: Tool name (must match a registered tool)
        args: Dictionary of arguments to pass to the handler

    Returns:
        Result string (JSON) from the handler
    """
    handler = _HANDLERS.get(name)
    if handler is None:
        import json
        return json.dumps({"error": f"Unknown tool: {name}"})
    return handler(**args)
