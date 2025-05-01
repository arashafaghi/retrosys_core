from typing import Dict, Any, Type
from .project_types import T, Lifecycle, ContainerProtocol

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
        for service_type, instance in self._instances.items():
            descriptor = self._container._get_descriptor(service_type)
            if descriptor and descriptor.on_destroy:
                if descriptor.is_async:
                    await descriptor.on_destroy(instance)
                else:
                    descriptor.on_destroy(instance)
        self._instances.clear()