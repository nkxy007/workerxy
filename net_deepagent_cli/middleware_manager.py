import json
import logging
import importlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Awaitable
from langchain.agents.middleware import AgentMiddleware

logger = logging.getLogger(__name__)

class MiddlewareManager:
    """Manages custom middleware registry and user preferences."""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.config_dir = Path.home() / ".net-deepagent" / agent_name
        self.config_file = self.config_dir / "middlewares.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Default middlewares and their states
        self.available_middlewares = {
            "advanced_context": {
                "name": "Advanced Context Pruning",
                "description": "Prunes skills, old tool outputs, and summarizes context at 85% limit.",
                "class_path": "custom_middleware.skill_pruning_middleware.AdvancedContextMiddleware",
                "enabled": True,
                "params": {
                    "max_tokens": 128000,
                    "trigger_ratio": 0.85,
                    "keep_skills": 1,
                    "keep_tool_uses": 3
                }
            },
            "netpii": {
                "name": "NetPII Pseudonymization",
                "description": "Masks sensitive network info like IPs and MAC addresses.",
                "class_path": "custom_middleware.netpii_middlewares.PIIPseudonymizationMiddleware",
                "enabled": False,
                "params": {
                    "pii_types": "all"
                }
            },
            "security_guard": {
                "name": "Security Guardrail",
                "description": "Basic security checks for model inputs/outputs.",
                "class_path": "custom_middleware.security_middleware.rebuff_middleware.RebuffSecurityMiddleware",
                "enabled": False,
                "params": {
                    "mode": "local"
                }
            }
        }
        
        self.load_config()

    def load_config(self):
        """Load middleware configuration from disk."""
        if self.config_file.exists():
            try:
                user_config = json.loads(self.config_file.read_text())
                # Update default config with user preferences (enabled state and params)
                for key, config in user_config.items():
                    if key in self.available_middlewares:
                        self.available_middlewares[key]["enabled"] = config.get("enabled", self.available_middlewares[key]["enabled"])
                        self.available_middlewares[key]["params"].update(config.get("params", {}))
            except Exception as e:
                logger.error(f"Failed to load middleware config: {e}")

    def save_config(self):
        """Save current middleware configuration to disk."""
        try:
            config_to_save = {
                key: {
                    "enabled": val["enabled"],
                    "params": val["params"]
                }
                for key, val in self.available_middlewares.items()
            }
            self.config_file.write_text(json.dumps(config_to_save, indent=4))
        except Exception as e:
            logger.error(f"Failed to save middleware config: {e}")

    def toggle_middleware(self, key: str, enabled: bool):
        """Toggle a middleware on or off."""
        if key in self.available_middlewares:
            self.available_middlewares[key]["enabled"] = enabled
            self.save_config()
            return True
        return False

    def get_enabled_middlewares(self) -> List[Dict[str, Any]]:
        """Return a list of enabled middleware configurations."""
        return [cfg for cfg in self.available_middlewares.values() if cfg["enabled"]]

    def list_all(self) -> Dict[str, Dict[str, Any]]:
        """List all registered middlewares and their status."""
        return self.available_middlewares

class DynamicMiddlewareRegistry(AgentMiddleware):
    """
    A proxy middleware that dynamically delegates to enabled custom middlewares.
    Allows for hot-reloading configurations without restarting the agent.
    """
    
    def __init__(self, agent_name: str, main_model_name: str):
        super().__init__()
        self.agent_name = agent_name
        self.main_model_name = main_model_name
        self.manager = MiddlewareManager(agent_name)
        self._instances = {} # Cache for instantiated middleware objects

    def _get_enabled_instances(self) -> List[Any]:
        """Resolve and return currently enabled middleware instances."""
        self.manager.load_config() # Refresh from disk
        enabled_configs = self.manager.get_enabled_middlewares()
        
        active_instances = []
        for cfg in enabled_configs:
            class_path = cfg["class_path"]
            params = cfg.get("params", {})
            
            # Simple cache key based on class_path and params
            instance_key = f"{class_path}_{json.dumps(params, sort_keys=True)}"
            
            if instance_key not in self._instances:
                try:
                    # Special case for AdvancedContextMiddleware
                    if "AdvancedContextMiddleware" in class_path and "summarize_model" not in params:
                        # We use a copy of params to avoid modifying the original config in manager
                        params = params.copy()
                        params["summarize_model"] = self.main_model_name
                    
                    module_name, class_name = class_path.rsplit(".", 1)
                    module = importlib.import_module(module_name)
                    middleware_class = getattr(module, class_name)
                    self._instances[instance_key] = middleware_class(**params)
                    logger.info(f"Dynamically loaded middleware: {cfg['name']}")
                except Exception as e:
                    logger.error(f"Error loading middleware {cfg.get('name', 'unknown')}: {e}")
                    continue
            
            active_instances.append(self._instances[instance_key])
            
        return active_instances

    def _is_overridden(self, instance, method_name):
        """Check if a method is overridden from the base AgentMiddleware class."""
        if not hasattr(instance, method_name):
            return False
        
        # Get the implementation from the instance and the base class
        instance_method = getattr(instance, method_name)
        base_method = getattr(AgentMiddleware, method_name)
        
        # For bound methods, compare the underlying functions
        if hasattr(instance_method, "__func__"):
            return instance_method.__func__ != base_method
        
        return instance_method != base_method

    def state_schema(self, input_schema: type) -> type:
        schema = input_schema
        for instance in self._get_enabled_instances():
            if hasattr(instance, 'state_schema'):
                schema = instance.state_schema(schema)
        return schema

    def before_model(self, state, runtime):
        all_updates = {}
        for instance in self._get_enabled_instances():
            if hasattr(instance, 'before_model'):
                updates = instance.before_model(state, runtime)
                if updates:
                    state.update(updates)
                    all_updates.update(updates)
        return all_updates if all_updates else None

    async def abefore_model(self, state, runtime):
        all_updates = {}
        for instance in self._get_enabled_instances():
            if hasattr(instance, 'abefore_model'):
                updates = await instance.abefore_model(state, runtime)
                if updates:
                    state.update(updates)
                    all_updates.update(updates)
        return all_updates if all_updates else None

    def after_model(self, state, runtime):
        all_updates = {}
        for instance in self._get_enabled_instances():
            if hasattr(instance, 'after_model'):
                updates = instance.after_model(state, runtime)
                if updates:
                    state.update(updates)
                    all_updates.update(updates)
        return all_updates if all_updates else None

    async def aafter_model(self, state, runtime):
        all_updates = {}
        for instance in self._get_enabled_instances():
            if hasattr(instance, 'aafter_model'):
                updates = await instance.aafter_model(state, runtime)
                if updates:
                    state.update(updates)
                    all_updates.update(updates)
        return all_updates if all_updates else None

    def wrap_model_call(self, request, handler):
        instances = [i for i in self._get_enabled_instances() if self._is_overridden(i, 'wrap_model_call')]
        
        def chain(idx, req):
            if idx >= len(instances):
                return handler(req)
            return instances[idx].wrap_model_call(req, lambda r: chain(idx + 1, r))

        return chain(0, request)

    async def awrap_model_call(self, request, handler):
        instances = [i for i in self._get_enabled_instances() if self._is_overridden(i, 'awrap_model_call')]
        
        async def achain(idx, req):
            if idx >= len(instances):
                return await handler(req)
            return await instances[idx].awrap_model_call(req, lambda r: achain(idx + 1, r))

        return await achain(0, request)

    def wrap_tool_call(self, request, handler):
        instances = [i for i in self._get_enabled_instances() if self._is_overridden(i, 'wrap_tool_call')]
        
        def chain(idx, req):
            if idx >= len(instances):
                return handler(req)
            return instances[idx].wrap_tool_call(req, lambda r: chain(idx + 1, r))

        return chain(0, request)

    async def awrap_tool_call(self, request, handler):
        instances = [i for i in self._get_enabled_instances() if self._is_overridden(i, 'awrap_tool_call')]
        
        async def achain(idx, req):
            if idx >= len(instances):
                return await handler(req)
            return await instances[idx].awrap_tool_call(req, lambda r: achain(idx + 1, r))

        return await achain(0, request)
