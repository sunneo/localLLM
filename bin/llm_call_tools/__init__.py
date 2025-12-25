"""
LLM Call Tools - Modular tool system for LLM function calling.

This package automatically imports all tool modules except the 'sample' directory.
It also automatically initializes submodules if ai_config is available.
"""

import os
import importlib
import pkgutil
import sys

# Import common utilities first
from .common import (
    register_ai_tool,
    get_tool_names
)

# Try to import configuration
_config = None
try:
    current_dir = os.getcwd()
    # 將 CWD 插入到 sys.path 的最前面 (索引 0)，使其優先被搜尋
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    import ai_config
    _config = ai_config
    # override_ai_config有產生就可以覆蓋
    import override_ai_config
    _config = override_ai_config
except ImportError as e:
    #print(f"{e}",flush=True,file=sys.stderr)
    pass

# Auto-import all submodules except 'sample' and initialize them
_current_dir = os.path.dirname(__file__)
_ignore_modules = {'sample', 'common', "git_tool"}

for finder, name, ispkg in pkgutil.iter_modules([_current_dir]):
    if name not in _ignore_modules:
        try:
            # Import the module
            module = importlib.import_module(f'.{name}', package=__name__)
            
            # Try to initialize the module if config is available
            if _config:
                # Check for module-specific initialization function
                if hasattr(module, 'initialize'):
                   try:
                       module.initialize(_config)
                   except Exception as e:
                       print(f"Warning: {name} initialization failed: {e}", flush=True, file=sys.stderr)
        except Exception as e:
            # Print warning but don't fail if a module can't be imported
            print(f"Warning: Failed to import llm_call_tools.{name}: {e}", flush=True, file=sys.stderr)

__all__ = [
    'get_tool_names',
    'register_ai_tool'
]
