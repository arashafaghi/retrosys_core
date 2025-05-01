from typing import Optional, Type, Union, Callable, Awaitable, Any, TYPE_CHECKING
from .project_types import T, Lifecycle, FactoryCallable, AsyncFactoryCallable, ResolutionStrategy
from .errors import DependencyNotFoundError, AsyncInitializationError

if TYPE_CHECKING:
    from .dependency_injection import Container

import inspect

class Module:
    """A group of related dependencies."""
    
    def __init__(self, name: str = ""):
        """Initialize a new module."""
        from .dependency_injection import Container
        self._container = Container()
        self.parent_container: Optional['Container'] = None
        self.name = name
        
    def register(self, service_type: Type[T], 
                implementation_type: Optional[Type] = None,
                lifecycle: Lifecycle = Lifecycle.SINGLETON,
                factory: Optional[Union[FactoryCallable, AsyncFactoryCallable]] = None,
                context_key: str = "",
                is_async: bool = False,
                resolution_strategy: ResolutionStrategy = ResolutionStrategy.EAGER,
                on_init: Optional[Callable[[Any], Optional[Awaitable[None]]]] = None,
                on_destroy: Optional[Callable[[Any], Optional[Awaitable[None]]]] = None) -> 'Module':
        """Register a service with the module."""
        self._container.register(
            service_type, 
            implementation_type, 
            lifecycle, 
            factory, 
            context_key,
            is_async,
            resolution_strategy, 
            on_init, 
            on_destroy
        )
        return self
        
    def register_instance(self, service_type: Type[T], instance: T) -> 'Module':
        """Register an existing instance with the module."""
        self._container.register_instance(service_type, instance)
        return self
        
    def register_factory(self, service_type: Type[T], 
                            factory: Union[FactoryCallable, AsyncFactoryCallable],
                            lifecycle: Lifecycle = Lifecycle.SINGLETON,
                            is_async: bool = False) -> 'Module':
        """Register a factory function for a service."""
        if inspect.iscoroutinefunction(factory):
            is_async = True
        self._container.register_factory(service_type, factory, lifecycle, is_async)
        return self
        
    def _get_descriptor(self, service_type: Type, context_key: str = ""):
        """Get the service descriptor for a type."""
        return self._container._get_descriptor(service_type, context_key)
        
    def resolve(self, service_type: Type[T], context_key: str = "") -> Optional[T]:
        """Resolve a service from the module."""
        try:
            return self._container.resolve(service_type, context_key)
        except (DependencyNotFoundError, AsyncInitializationError):
            # If the parent container is set, try to resolve from it
            if self.parent_container:
                try:
                    return self.parent_container.resolve(service_type, context_key)
                except (DependencyNotFoundError, AsyncInitializationError):
                    return None
            return None
            
    async def resolve_async(self, service_type: Type[T], context_key: str = "") -> Optional[T]:
        """Async resolve a service from the module."""
        try:
            return await self._container.resolve_async(service_type, context_key)
        except DependencyNotFoundError:
            # If the parent container is set, try to resolve from it
            if self.parent_container:
                try:
                    return await self.parent_container.resolve_async(service_type, context_key)
                except DependencyNotFoundError:
                    return None
            return None