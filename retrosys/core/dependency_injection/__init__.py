# Re-export from types
from .project_types import (
    T, FactoryCallable, AsyncFactoryCallable, 
    Lifecycle, ResolutionStrategy, ContainerProtocol
)

# Re-export from service_descriptor
from .service_descriptor import ServiceDescriptor
# Re-export from types
from .project_types import (
    T, FactoryCallable, AsyncFactoryCallable, 
    Lifecycle, ResolutionStrategy, ContainerProtocol
)

# Re-export from service_descriptor
from .service_descriptor import ServiceDescriptor

# Re-export from errors
from .errors import (
    CircularDependencyError, 
    DependencyNotFoundError, 
    AsyncInitializationError
)

# Re-export from lazy
from .lazy import Lazy

# Re-export from scope
from .scope import Scope

# IMPORTANT: Import Container first, then Module
from .container import Container
# Only after Container is imported, import Module
from .module import Module

# Re-export decorators
from .decorators import (
    injectable, inject_property, inject_method, register_module
)



__all__ = [
    # Types
    'T', 'FactoryCallable', 'AsyncFactoryCallable',
    'Lifecycle', 'ResolutionStrategy', 'ContainerProtocol',
    
    # Classes
    'ServiceDescriptor', 'Container', 'Module', 'Lazy', 'Scope',
    
    # Errors
    'CircularDependencyError', 'DependencyNotFoundError', 'AsyncInitializationError',
    
    # Decorators
    'injectable', 'inject_property', 'inject_method', 'register_module'
]