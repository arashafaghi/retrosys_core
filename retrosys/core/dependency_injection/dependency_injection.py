from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    Union,
    Awaitable,
)

import inspect
import warnings
import threading
import logging
import networkx as nx
import matplotlib.pyplot as plt

from .project_types import (
    T, FactoryCallable, AsyncFactoryCallable, Lifecycle, ResolutionStrategy
)
from .service_descriptor import ServiceDescriptor
from .errors import (
    CircularDependencyError, DependencyNotFoundError, AsyncInitializationError
)
from .lazy import Lazy
from .scope import Scope
from .module import Module


class Container:
    """Main dependency injection container with async support."""

    def __init__(self):
        self._descriptors: Dict[Type, List[ServiceDescriptor]] = {}
        self._resolution_stack: List[Type] = []
        self._lock = threading.RLock()
        self._modules: Dict[str, "Module"] = {}
        self._logger = logging.getLogger("DI.Container")
        self._test_mode = False
        self._mock_instances: Dict[Type, Any] = {}

    def register(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type] = None,
        lifecycle: Lifecycle = Lifecycle.SINGLETON,
        factory: Optional[Union[FactoryCallable, AsyncFactoryCallable]] = None, #this is self factory, lamda to use.
        context_key: str = "",
        is_async: bool = False,
        resolution_strategy: ResolutionStrategy = ResolutionStrategy.EAGER,
        on_init: Optional[Callable[[Any], Optional[Awaitable[None]]]] = None,
        on_destroy: Optional[Callable[[Any], Optional[Awaitable[None]]]] = None,
    ) -> "Container":
        """Register a service with the container."""
        with self._lock:
            impl_type = implementation_type or service_type

            # Detect async factory
            if factory and inspect.iscoroutinefunction(factory):
                is_async = True

            descriptor = ServiceDescriptor(
                service_type=service_type,
                implementation_type=impl_type,
                lifecycle=lifecycle,
                factory=factory,
                context_key=context_key,
                is_async=is_async,
                resolution_strategy=resolution_strategy,
                on_init=on_init,
                on_destroy=on_destroy,
            )

            if service_type not in self._descriptors:
                self._descriptors[service_type] = []

            self._descriptors[service_type].append(descriptor)
            self._logger.debug(
                f"Registered {service_type.__name__} with implementation {impl_type.__name__}"
            )
            return self

    def register_instance(self, service_type: Type[T], instance: T) -> "Container":
        """Register an existing instance with the container."""
        with self._lock:
            descriptor = ServiceDescriptor(
                service_type=service_type,
                implementation_type=type(instance),
                lifecycle=Lifecycle.SINGLETON,
                instance=instance,
            )

            if service_type not in self._descriptors:
                self._descriptors[service_type] = []

            self._descriptors[service_type].append(descriptor)
            self._logger.debug(f"Registered instance of {service_type.__name__}")
            return self

    def register_factory(
        self,
        service_type: Type[T],
        factory: Union[FactoryCallable, AsyncFactoryCallable],
        lifecycle: Lifecycle = Lifecycle.SINGLETON,
        is_async: bool = False,
        context_key: str = "",
    ) -> "Container":
        """Register a factory function for a service."""
        if inspect.iscoroutinefunction(factory):
            is_async = True
        return self.register(
            service_type, lifecycle=lifecycle, factory=factory, is_async=is_async, context_key=context_key
        )

    def lazy_resolve(self, service_type: Type[T], context_key: str = "") -> Lazy[T]:
        """Get a lazy wrapper for a dependency."""
        return Lazy(self, service_type, context_key)

    def resolve(self, service_type: Type[T], context_key: str = "") -> T:
        """Synchronously resolve a service from the container."""
        with self._lock:
            # If we're in test mode, check for mocks first
            if self._test_mode and service_type in self._mock_instances:
                return self._mock_instances[service_type]

            # Check for circular dependencies
            if service_type in self._resolution_stack:
                path = " -> ".join(
                    [t.__name__ for t in self._resolution_stack] + [service_type.__name__]
                )
                raise CircularDependencyError(f"Circular dependency detected: {path}")

            # Add to resolution stack for circular dependency detection
            self._resolution_stack.append(service_type)

            try:
                descriptor = self._get_descriptor(service_type, context_key)
                
                # Just-in-time registration for injectable classes
                if not descriptor and hasattr(service_type, '__di_injectable__') and getattr(service_type, '__di_injectable__'):
                    self._logger.debug(f"Auto-registering {service_type.__name__}")
                    
                    # Extract metadata from the class
                    lifecycle = getattr(service_type, '__di_lifecycle__', Lifecycle.SINGLETON)
                    ctx_key = getattr(service_type, '__di_context_key__', context_key)
                    is_async = getattr(service_type, '__di_is_async__', False)
                    resolution_strategy = getattr(service_type, '__di_resolution_strategy__', 
                                            ResolutionStrategy.EAGER)
                    
                    # Register it automatically
                    self.register(
                        service_type, 
                        lifecycle=lifecycle,
                        context_key=ctx_key,
                        is_async=is_async,
                        resolution_strategy=resolution_strategy
                    )
                    
                    # Get the descriptor again
                    descriptor = self._get_descriptor(service_type, context_key)
                
                if not descriptor:
                    raise DependencyNotFoundError(
                        f"No registration found for {service_type.__name__}"
                    )

                # For singletons, check if we already have an instance
                if (
                    descriptor.lifecycle == Lifecycle.SINGLETON
                    and descriptor.instance is not None
                ):
                    return descriptor.instance

                self._logger.debug(f"Resolving {service_type.__name__}")

                # Handle async services
                if descriptor.is_async:
                    raise AsyncInitializationError(
                        f"Service {service_type.__name__} is async and must be resolved with resolve_async"
                    )

                # Use factory if provided
                if descriptor.factory:
                    instance = descriptor.factory(self)
                else:
                    # Create a new instance using constructor injection
                    instance = self._create_instance(descriptor.implementation_type)

                # Apply property injections
                for prop_name, prop_type in descriptor.property_injections.items():
                    setattr(instance, prop_name, self.resolve(prop_type, context_key))

                # Apply method injections
                for method_name, param_types in descriptor.method_injections.items():
                    method = getattr(instance, method_name)
                    params = {
                        name: self.resolve(typ, context_key)
                        for name, typ in param_types.items()
                    }
                    method(**params)

                # Call on_init if provided
                if descriptor.on_init and not descriptor.is_async:
                    descriptor.on_init(instance)

                # Store singleton instances
                if descriptor.lifecycle == Lifecycle.SINGLETON:
                    descriptor.instance = instance

                return instance
            finally:
                # Remove from resolution stack
                self._resolution_stack.pop()

    async def resolve_async(self, service_type: Type[T], context_key: str = "") -> T:
        """Asynchronously resolve a service from the container."""
        with self._lock:
            # If we're in test mode, check for mocks first
            if self._test_mode and service_type in self._mock_instances:
                return self._mock_instances[service_type]

            # Check for circular dependencies
            if service_type in self._resolution_stack:
                path = " -> ".join(
                    [t.__name__ for t in self._resolution_stack] + [service_type.__name__]
                )
                raise CircularDependencyError(f"Circular dependency detected: {path}")

            # Add to resolution stack for circular dependency detection
            self._resolution_stack.append(service_type)

            try:
                descriptor = self._get_descriptor(service_type, context_key)
                
                # Just-in-time registration for injectable classes
                if not descriptor and hasattr(service_type, '__di_injectable__') and getattr(service_type, '__di_injectable__'):
                    self._logger.debug(f"Auto-registering {service_type.__name__}")
                    
                    # Extract metadata from the class
                    lifecycle = getattr(service_type, '__di_lifecycle__', Lifecycle.SINGLETON)
                    ctx_key = getattr(service_type, '__di_context_key__', context_key)
                    is_async = getattr(service_type, '__di_is_async__', False)
                    resolution_strategy = getattr(service_type, '__di_resolution_strategy__', 
                                            ResolutionStrategy.EAGER)
                    
                    # Register it automatically
                    self.register(
                        service_type, 
                        lifecycle=lifecycle,
                        context_key=ctx_key,
                        is_async=is_async,
                        resolution_strategy=resolution_strategy
                    )
                    
                    # Get the descriptor again
                    descriptor = self._get_descriptor(service_type, context_key)
                
                if not descriptor:
                    raise DependencyNotFoundError(
                        f"No registration found for {service_type.__name__}"
                    )

                # For singletons, check if we already have an instance
                if (
                    descriptor.lifecycle == Lifecycle.SINGLETON
                    and descriptor.instance is not None
                ):
                    return descriptor.instance

                self._logger.debug(f"Async resolving {service_type.__name__}")

                # Use factory if provided
                if descriptor.factory:
                    if descriptor.is_async:
                        instance = await descriptor.factory(self)
                    else:
                        instance = descriptor.factory(self)
                else:
                    # Create a new instance using constructor injection
                    instance = await self._create_instance_async(
                        descriptor.implementation_type
                    )

                # Apply property injections asynchronously
                for prop_name, prop_type in descriptor.property_injections.items():
                    prop_descriptor = self._get_descriptor(prop_type, context_key)
                    if prop_descriptor and prop_descriptor.is_async:
                        setattr(
                            instance,
                            prop_name,
                            await self.resolve_async(prop_type, context_key),
                        )
                    else:
                        setattr(instance, prop_name, self.resolve(prop_type, context_key))

                # Apply method injections (async methods not supported yet)
                for method_name, param_types in descriptor.method_injections.items():
                    method = getattr(instance, method_name)
                    params = {}
                    for name, typ in param_types.items():
                        param_descriptor = self._get_descriptor(typ, context_key)
                        if param_descriptor and param_descriptor.is_async:
                            params[name] = await self.resolve_async(typ, context_key)
                        else:
                            params[name] = self.resolve(typ, context_key)
                    method(**params)

                # Call on_init if provided
                if descriptor.on_init:
                    if descriptor.is_async:
                        await descriptor.on_init(instance)
                    else:
                        descriptor.on_init(instance)

                # Store singleton instances
                if descriptor.lifecycle == Lifecycle.SINGLETON:
                    descriptor.instance = instance

                return instance
            finally:
                # Remove from resolution stack
                self._resolution_stack.pop()
    def _get_descriptor(
        self, service_type: Type, context_key: str = ""
    ) -> Optional[ServiceDescriptor]:
        """Get the service descriptor for a type."""
        descriptors = self._descriptors.get(service_type, [])
        if not descriptors:
            # Check if it's registered in any modules
            for module in self._modules.values():
                if descriptor := module._get_descriptor(service_type, context_key):
                    return descriptor
            return None

        # Find the appropriate descriptor based on context
        return next(
            (d for d in descriptors if d.context_key == context_key), descriptors[0]
        )

    def _create_instance(self, implementation_type: Type[T]) -> T:
        """Create a new instance with constructor injection."""
        if not hasattr(implementation_type, "__init__"):
            return implementation_type()

        # Get the constructor
        init = implementation_type.__init__
        if init is object.__init__:  # Default constructor
            return implementation_type()

        # Get parameter annotations
        sig = inspect.signature(init)
        params = {}

        for name, param in sig.parameters.items():
            if name == "self":
                continue

            annotation = param.annotation
            if annotation is inspect.Parameter.empty:
                if param.default is inspect.Parameter.empty:
                    # Cannot resolve parameter without type annotation or default
                    raise DependencyNotFoundError(
                        f"Cannot resolve parameter '{name}' for {implementation_type.__name__} "
                        f"without type annotation"
                    )
                continue  # Use default value

            # Check if this is a lazy dependency
            if getattr(annotation, "__origin__", None) == Lazy:
                params[name] = self.lazy_resolve(annotation.__args__[0])
            else:
                # Regular dependency
                descriptor = self._get_descriptor(annotation)
                if descriptor and descriptor.is_async:
                    raise AsyncInitializationError(
                        f"Async dependency {annotation.__name__} cannot be injected into "
                        f"sync constructor of {implementation_type.__name__}"
                    )
                params[name] = self.resolve(annotation)

        return implementation_type(**params)

    async def _create_instance_async(self, implementation_type: Type[T]) -> T:
        """Create a new instance with constructor injection, supporting async dependencies."""
        if not hasattr(implementation_type, "__init__"):
            return implementation_type()

        # Get the constructor
        init = implementation_type.__init__
        if init is object.__init__:  # Default constructor
            return implementation_type()

        # Get parameter annotations
        sig = inspect.signature(init)
        params = {}

        for name, param in sig.parameters.items():
            if name == "self":
                continue

            annotation = param.annotation
            if annotation is inspect.Parameter.empty:
                if param.default is inspect.Parameter.empty:
                    # Cannot resolve parameter without type annotation or default
                    raise DependencyNotFoundError(
                        f"Cannot resolve parameter '{name}' for {implementation_type.__name__} "
                        f"without type annotation"
                    )
                continue  # Use default value

            # Check if this is a lazy dependency
            if getattr(annotation, "__origin__", None) == Lazy:
                params[name] = self.lazy_resolve(annotation.__args__[0])
            else:
                # Get the descriptor to check if it's async
                descriptor = self._get_descriptor(annotation)
                if descriptor and descriptor.is_async:
                    params[name] = await self.resolve_async(annotation)
                else:
                    params[name] = self.resolve(annotation)

        return implementation_type(**params)

    def create_scope(self) -> Scope:
        """Create a new dependency scope."""
        return Scope(self)

    def register_module(self, module: "Module", namespace: str = "") -> "Container":
        """Register a module with the container."""
        if namespace in self._modules:
            warnings.warn(
                f"Module namespace '{namespace}' is already registered. Overwriting."
            )
        self._modules[namespace] = module
        module.parent_container = self
        return self

    def create_child_container(self) -> "Container":
        """Create a new container that inherits registrations from this one."""
        child = Container()
        # Copy registrations
        for service_type, descriptors in self._descriptors.items():
            child._descriptors[service_type] = descriptors.copy()
        # Copy modules
        for namespace, module in self._modules.items():
            child._modules[namespace] = module
        return child

    def enable_test_mode(self) -> "Container":
        """Enable test mode for mocking dependencies."""
        self._test_mode = True
        return self

    def disable_test_mode(self) -> "Container":
        """Disable test mode and clear mocks."""
        self._test_mode = False
        self._mock_instances.clear()
        return self

    def mock(self, service_type: Type[T], instance: T) -> "Container":
        """Register a mock instance for testing."""
        self._mock_instances[service_type] = instance
        return self

    def visualize_dependency_graph(self, filename: str = "dependency_graph.png") -> None:
        """Generate and save a visualization of the dependency graph."""
        import math  # Add this import at the top of the file
        
        graph = self.generate_dependency_graph()

        # Create a directed graph
        G = nx.DiGraph()

        # Add all nodes
        for service_name in graph:
            G.add_node(service_name)

        # Add all edges
        for service_name, dependencies in graph.items():
            for dep in dependencies:
                # Only add edges when both nodes exist
                if dep in graph:
                    G.add_edge(service_name, dep)

        # Generate the visualization with a better layout
        plt.figure(figsize=(15, 10))
        
        # Try different layouts based on graph size
        if len(G.nodes) < 10:
            # For small graphs, hierarchical layout works well
            try:
                pos = nx.nx_pydot.graphviz_layout(G, prog='dot')
            except:
                # Fall back to spring layout if graphviz not available
                pos = nx.spring_layout(G, k=1.5/math.sqrt(len(G.nodes)), iterations=50, seed=42)
        else:
            # For larger graphs, use spring layout with tuned parameters
            pos = nx.spring_layout(G, k=1.5/math.sqrt(len(G.nodes)), iterations=50, seed=42)
        
        # Draw nodes with different colors based on node type
        node_colors = []
        for node in G.nodes:
            if node.startswith('I'):  # Interfaces often start with I
                node_colors.append('lightgreen')
            elif len(list(G.predecessors(node))) == 0:  # Root services
                node_colors.append('orange')
            elif len(list(G.successors(node))) == 0:  # Leaf services
                node_colors.append('lightblue')
            else:  # Middle-tier services
                node_colors.append('lightgray')
        
        # Draw nodes
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=1500, alpha=0.8)
        
        # Draw edges with arrows
        nx.draw_networkx_edges(G, pos, width=1.0, alpha=0.5, arrows=True, arrowsize=15)
        
        # Draw labels with a white background for readability
        labels = {node: node for node in G.nodes}
        bbox_props = dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8)
        nx.draw_networkx_labels(G, pos, labels, font_size=10, bbox=bbox_props)
        
        plt.title("Dependency Injection Graph")
        plt.axis('off')  # Turn off axis
        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()

        self._logger.info(f"Dependency graph saved to {filename}")
    def generate_dependency_graph(self) -> Dict[str, List[str]]:
        """Generate a visualization of the dependency graph."""
        graph = {}
        
        primitive_types = {str, int, float, bool, list, dict, set, tuple}


        # Add all registered types as nodes
        for service_type in self._descriptors:
            if service_type in primitive_types or service_type.__module__ == 'builtins':
                continue

            service_name = service_type.__name__
            graph[service_name] = []

        # Add dependencies as edges
        for service_type, descriptors in self._descriptors.items():
            service_name = service_type.__name__
            for descriptor in descriptors:
                impl_type = descriptor.implementation_type
                if impl_type:
                    self._add_dependencies_to_graph(graph, service_name, impl_type)

        # Add module services
        for module_name, module in self._modules.items():
            for service_type, descriptors in getattr(module._container, '_descriptors', {}).items():
                
                if service_type in primitive_types or service_type.__module__ == 'builtins':
                    continue
                service_name = service_type.__name__
                if service_name not in graph:
                    graph[service_name] = []
                
                for descriptor in descriptors:
                    impl_type = descriptor.implementation_type
                    if impl_type:
                        self._add_dependencies_to_graph(graph, service_name, impl_type)
        
        
        return graph

    def _add_dependencies_to_graph(self, graph: Dict[str, List[str]], source_name: str, implementation_type: Type) -> None:
        """Add dependencies of a type to the graph."""
        
        # Primitive types to exclude from dependency graph
        primitive_types = {str, int, float, bool, list, dict, set, tuple}
        
        # Add constructor dependencies
        if hasattr(implementation_type, "__init__") and implementation_type.__init__ is not object.__init__:
            sig = inspect.signature(implementation_type.__init__)
            
            for name, param in sig.parameters.items():
                if name != "self" and param.annotation is not inspect.Parameter.empty:
                    # Handle Lazy dependencies
                    if getattr(param.annotation, "__origin__", None) == Lazy:
                        dep_type = param.annotation.__args__[0]
                        # Skip primitive types
                        if dep_type in primitive_types or dep_type.__module__ == 'builtins':
                            continue
                        dep_name = dep_type.__name__
                    else:
                        dep_type = param.annotation
                        # Skip primitive types
                        if dep_type in primitive_types or dep_type.__module__ == 'builtins':
                            continue
                        dep_name = dep_type.__name__

                    if dep_name not in graph[source_name]:
                        graph[source_name].append(dep_name)
    async def dispose(self) -> None:
        """Dispose of all services with on_destroy handlers."""
        for descriptors in self._descriptors.values():
            for descriptor in descriptors:
                if (
                    descriptor.lifecycle == Lifecycle.SINGLETON
                    and descriptor.instance
                    and descriptor.on_destroy
                ):
                    if descriptor.is_async:
                        await descriptor.on_destroy(descriptor.instance)
                    else:
                        descriptor.on_destroy(descriptor.instance)

    def register_injectables(self, module) -> "Container":
        """Register all classes with @injectable decorators in a module."""
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and getattr(obj, '__di_injectable__', False):
                lifecycle = getattr(obj, '__di_lifecycle__', Lifecycle.SINGLETON)
                context_key = getattr(obj, '__di_context_key__', "")
                is_async = getattr(obj, '__di_is_async__', False)
                resolution_strategy = getattr(obj, '__di_resolution_strategy__', 
                                            ResolutionStrategy.EAGER)
                self.register(obj, lifecycle=lifecycle, context_key=context_key, 
                            is_async=is_async, resolution_strategy=resolution_strategy)
        return self