from typing import Type, Dict
import inspect
from .project_types import Lifecycle, ResolutionStrategy
from .module import Module

def injectable(lifecycle: Lifecycle = Lifecycle.SINGLETON, 
               context_key: str = "",
               is_async: bool = False,
               resolution_strategy: ResolutionStrategy = ResolutionStrategy.EAGER):
    """Decorator to mark a class as injectable."""
    def decorator(cls):
        # Store DI metadata on the class
        setattr(cls, '__di_injectable__', True)
        setattr(cls, '__di_lifecycle__', lifecycle)
        setattr(cls, '__di_context_key__', context_key)
        setattr(cls, '__di_is_async__', is_async)
        setattr(cls, '__di_resolution_strategy__', resolution_strategy)
        
        # Auto-detect async initialization
        if hasattr(cls, '__init__') and inspect.iscoroutinefunction(cls.__init__):
            setattr(cls, '__di_is_async__', True)
        
        return cls
    return decorator

def inject_property(service_type: Type):
    """Decorator to inject a dependency as a property."""
    def decorator(cls):
        if not hasattr(cls, '__di_property_injections__'):
            setattr(cls, '__di_property_injections__', {})
        
        property_injections = getattr(cls, '__di_property_injections__')
        
        def property_wrapper(prop_name):
            property_injections[prop_name] = service_type
        
        return property_wrapper
    return decorator

def inject_method(param_types: Dict[str, Type]):
    """Decorator to inject dependencies into a method."""
    def decorator(func):
        setattr(func, '__di_inject_params__', param_types)
        return func
    return decorator

def register_module(container):
    """Register all injectables from a module."""
    def decorator(module_class):
        if not inspect.isclass(module_class):
            raise TypeError("@register_module can only be applied to classes")
            
        module = Module(module_class.__name__)
        
        # Find all injectable members
        for name, member in inspect.getmembers(module_class):
            if inspect.isclass(member) and getattr(member, '__di_injectable__', False):
                lifecycle = getattr(member, '__di_lifecycle__', Lifecycle.SINGLETON)
                context_key = getattr(member, '__di_context_key__', "")
                is_async = getattr(member, '__di_is_async__', False)
                resolution_strategy = getattr(member, '__di_resolution_strategy__', ResolutionStrategy.EAGER)
                
                # Register the service
                module.register(
                    member, 
                    lifecycle=lifecycle,
                    context_key=context_key,
                    is_async=is_async,
                    resolution_strategy=resolution_strategy
                )
                
                # Add property injections
                property_injections = getattr(member, '__di_property_injections__', {})
                for prop_name, prop_type in property_injections.items():
                    module._container._descriptors[member][0].property_injections[prop_name] = prop_type
                
                # Add method injections
                for method_name, method in inspect.getmembers(member, inspect.isfunction):
                    if hasattr(method, '__di_inject_params__'):
                        params = getattr(method, '__di_inject_params__')
                        module._container._descriptors[member][0].method_injections[method_name] = params
        
        # Register the module with the container
        container.register_module(module)
        return module_class
    return decorator