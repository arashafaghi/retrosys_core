from typing import Dict, Any, Type
from .project_types import T, Lifecycle, ContainerProtocol
import inspect

class Scope:
    """Represents a dependency injection scope."""
    def __init__(self, parent_container: ContainerProtocol):
        self._container = parent_container.create_child_container()
        self._instances: Dict[Type, Any] = {}
        
    def resolve(self, service_type: Type[T], context_key: str = "") -> T:
        """Resolve a service within this scope."""
        if service_type in self._instances:
            return self._instances[service_type]
            
        instance = self._container.resolve(service_type, context_key)
        
        # Cache scoped instances
        descriptor = self._container._get_descriptor(service_type, context_key)
        if descriptor and descriptor.lifecycle == Lifecycle.SCOPED:
            self._instances[service_type] = instance
            
        return instance
        
    async def resolve_async(self, service_type: Type[T], context_key: str = "") -> T:
        """Async resolve a service within this scope."""
        if service_type in self._instances:
            return self._instances[service_type]
            
        instance = await self._container.resolve_async(service_type, context_key)
        
        # Cache scoped instances
        descriptor = self._container._get_descriptor(service_type, context_key)
        if descriptor and descriptor.lifecycle == Lifecycle.SCOPED:
            self._instances[service_type] = instance
            
        return instance
    
    async def __aenter__(self) -> 'Scope':
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.dispose()
        
    async def dispose(self):
        """Dispose of all scoped instances."""
        for service_type, instance in list(self._instances.items()):
            descriptor = self._container._get_descriptor(service_type)
            if descriptor and descriptor.lifecycle == Lifecycle.SCOPED:
                if hasattr(instance, 'dispose'):
                    try:
                        dispose_method = instance.dispose
                        if inspect.iscoroutinefunction(dispose_method):
                            await dispose_method()
                        else:
                            dispose_method()
                    except Exception as e:
                        # Log error but continue disposing other instances
                        import logging
                        logging.getLogger(__name__).error(f"Error disposing instance of {service_type}: {e}")
                elif descriptor.on_destroy:
                    try:
                        if inspect.iscoroutinefunction(descriptor.on_destroy):
                            await descriptor.on_destroy(instance)
                        else:
                            descriptor.on_destroy(instance)
                    except Exception as e:
                        # Log error but continue disposing other instances
                        import logging
                        logging.getLogger(__name__).error(f"Error in on_destroy for {service_type}: {e}")
        self._instances.clear()