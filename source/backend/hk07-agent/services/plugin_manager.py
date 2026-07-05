import os
import sys
import importlib.util
import logging
from typing import List, Dict, Any, Callable

log = logging.getLogger("hk07.plugin_manager")

class PluginManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(PluginManager, cls).__new__(cls, *args, **kwargs)
            cls._instance.plugins = {}
            cls._instance.tools = {}
            cls._instance.loaded = False
        return cls._instance

    def load_plugins(self):
        if self.loaded:
            return
        
        plugins_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir, exist_ok=True)
            # Create a README inside plugins
            with open(os.path.join(plugins_dir, "README.md"), "w", encoding="utf-8") as f:
                f.write("# HK-07 Cognitive Plugins\nDrop custom cognitive agent plugins here.\nEach plugin should expose `get_tools()` and `execute_tool()`.\n")

        log.info("[PLUGINS] Loading cognitive plugins from: %s", plugins_dir)
        
        for item in os.listdir(plugins_dir):
            if item.startswith("__") or item == "README.md":
                continue
            
            item_path = os.path.join(plugins_dir, item)
            module_name = f"plugins.{os.path.splitext(item)[0]}"
            
            try:
                spec = None
                if os.path.isdir(item_path):
                    init_file = os.path.join(item_path, "__init__.py")
                    if os.path.exists(init_file):
                        spec = importlib.util.spec_from_file_location(module_name, init_file)
                elif item.endswith(".py"):
                    spec = importlib.util.spec_from_file_location(module_name, item_path)
                
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, "get_tools") and hasattr(module, "execute_tool"):
                        tools = module.get_tools()
                        for tool in tools:
                            name = tool.get("function", {}).get("name")
                            if name:
                                self.tools[name] = module.execute_tool
                                log.info("[PLUGINS] Registered tool '%s' from plugin: %s", name, item)
                        
                        self.plugins[item] = {
                            "module": module,
                            "tools": tools
                        }
                        log.info("[PLUGINS] Successfully loaded plugin: %s", item)
                    else:
                        log.warning("[PLUGINS] Plugin %s is missing get_tools or execute_tool functions.", item)
            except Exception as e:
                log.error("[PLUGINS] Failed to load plugin %s: %s", item, e, exc_info=True)
        
        self.loaded = True

    def get_all_tools(self) -> List[Dict[str, Any]]:
        all_tools = []
        for plugin_info in self.plugins.values():
            all_tools.extend(plugin_info["tools"])
        return all_tools

    async def execute_plugin_tool(self, tool_name: str, parameters: Dict[str, Any], vitals: Dict[str, Any], user_id: str) -> str:
        handler = self.tools.get(tool_name)
        if handler:
            try:
                res = await handler(tool_name, parameters, vitals, user_id)
                return str(res)
            except Exception as e:
                log.error("[PLUGINS] Tool '%s' execution failed: %s", tool_name, e)
                return f"[ERROR] Plugin tool execution failed: {str(e)}"
        return f"[ERROR] Tool '{tool_name}' handler not found"

def get_plugin_manager() -> PluginManager:
    pm = PluginManager()
    pm.load_plugins()
    return pm
