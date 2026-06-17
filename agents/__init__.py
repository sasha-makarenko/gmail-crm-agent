"""
Package bootstrap for the `agents` package.

We alias a few submodules into `sys.modules` so that accidental absolute
imports like `import gmail_client` still work when the code is executed as
`python -m agents.main`. This avoids "No module named 'gmail_client'" errors
if any file or tool (e.g., a notebook snippet) uses absolute imports.

Prefer package-relative imports everywhere (e.g., `from . import gmail_client`).
"""

from importlib import import_module
import sys as _sys

# Ensure key submodules are importable both as `agents.X` and as bare `X`.
# This is a small shim only for developer convenience.
for _name in ("gmail_client", "sheets_client", "utils", "state_store", "llm", "reanalyze", "debug", "list_threads"):
    try:
        _mod = import_module(f".{_name}", __name__)
        # Register alias only if not already present
        _sys.modules.setdefault(_name, _mod)
    except Exception:
        # Don't crash on partial environments; normal relative imports still work.
        pass
