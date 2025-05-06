import functools
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
    def decorator(prop_fn):
        prop_name = prop_fn.__name__
        
        class PropertyDescriptor:
            def __init__(self):
                self.service_type = service_type
                
            def __get__(self, obj, objtype=None):
                if obj is None:  # Class access
                    return self
                
                # Get the backing field
                backing_field = f"_{prop_name}"
                
                # Create backing field if it doesn't exist
                if not hasattr(obj, backing_field):
                    setattr(obj, backing_field, None)
                    
                value = getattr(obj, backing_field, None)
                
                # If property not yet injected and we have a container, 
                # try to resolve from container
                if value is None and hasattr(obj, '_container'):
                    container = getattr(obj, '_container')
                    try:
                        resolved_value = container.resolve(service_type)
                        setattr(obj, backing_field, resolved_value)
                        return resolved_value
                    except Exception as e:
                        # Fall back to returning None if resolution fails
                        pass
                
                return value
                
            def __set__(self, obj, value):
                setattr(obj, f"_{prop_name}", value)
            
            def __set_name__(self, owner, name):
                if not hasattr(owner, '__di_property_injections__'):
                    setattr(owner, '__di_property_injections__', {})
                getattr(owner, '__di_property_injections__')[name] = service_type
        
        return PropertyDescriptor()
    
    return decorator

def inject_method(params: Dict[str, Type]):
    """Decorator to inject dependencies as method parameters."""
    def decorator(method):
        # method_name = method.__name__
        # sig = inspect.signature(method)
        
        @functools.wraps(method)
        def wrapper(self, **kwargs):
            method_params = {}
            
            # Inject dependencies that aren't provided in kwargs
            for param_name, param_type in params.items():
                if param_name not in kwargs:
                    # Try to get the container from the instance's context
                    container = None
                    
                    # Look for container in predefined locations
                    for attr_name in ['_container', '_di_container', '__container__']:
                        if hasattr(self, attr_name):
                            container = getattr(self, attr_name)
                            break
                    
                    # If we have a container, resolve the dependency
                    if container:
                        method_params[param_name] = container.resolve(param_type)
                    else:
                        # Without container, try to lookup from registry if registered 
                        from retrosys.core.dependency_injection.container import Container
                        c = Container()
                        method_params[param_name] = c.resolve(param_type)
            
            # Combine with explicitly provided parameters
            method_params.update(kwargs)
            
            # Call the original method with all parameters
            return method(self, **method_params)
            
        # Store metadata for the DI container to use during resolution
        setattr(wrapper, '__di_method_params__', params)
        
        def __set_name__(owner, name):
            if not hasattr(owner, '__di_method_injections__'):
                setattr(owner, '__di_method_injections__', {})
            getattr(owner, '__di_method_injections__')[name] = params
            
        wrapper.__set_name__ = __set_name__
        
        return wrapper
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
                
                # Add property injections if they exist - FIX: properly look up the descriptor
                property_injections = getattr(member, '__di_property_injections__', {})
                if property_injections:
                    descriptor = module._container._get_descriptor(member)
                    if descriptor:
                        for prop_name, prop_type in property_injections.items():
                            descriptor.property_injections[prop_name] = prop_type
                
                # Add method injections
                method_injections = getattr(member, '__di_method_injections__', {})
                if method_injections:
                    descriptor = module._container._get_descriptor(member)
                    if descriptor:
                        for method_name, params in method_injections.items():
                            descriptor.method_injections[method_name] = params
        
        # Register the module with the container
        container.register_module(module)
        return module_class
    return decorator