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

from .project_types import (
    T,
    FactoryCallable,
    AsyncFactoryCallable,
    Lifecycle,
    ResolutionStrategy,
)
from .service_descriptor import ServiceDescriptor
from .errors import (
    CircularDependencyError,
    DependencyNotFoundError,
    AsyncInitializationError,
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
        self._signature_cache: Dict[Type, inspect.Signature] = {}
        self._property_injection_cache: Dict[Type, Dict[str, Type]] = {}
        self._method_injection_cache: Dict[Type, Dict[str, Dict[str, Type]]] = {}

    def register(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type] = None,
        lifecycle: Lifecycle = Lifecycle.SINGLETON,
        factory: Optional[Union[FactoryCallable, AsyncFactoryCallable]] = None,
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

            # Cache property injections for performance
            if impl_type not in self._property_injection_cache:
                self._property_injection_cache[impl_type] = {}
                if hasattr(impl_type, "__di_property_injections__"):
                    self._property_injection_cache[impl_type] = getattr(
                        impl_type, "__di_property_injections__", {}
                    )

            # Apply cached property injections
            for prop_name, prop_type in self._property_injection_cache[
                impl_type
            ].items():
                descriptor.property_injections[prop_name] = prop_type

            # Cache method injections for performance
            if impl_type not in self._method_injection_cache:
                self._method_injection_cache[impl_type] = {}
                if hasattr(impl_type, "__di_method_injections__"):
                    self._method_injection_cache[impl_type] = getattr(
                        impl_type, "__di_method_injections__", {}
                    )

            # Apply cached method injections
            for method_name, params in self._method_injection_cache[impl_type].items():
                descriptor.method_injections[method_name] = params

            # CRITICAL PART - FIXED INDENTATION
            if service_type not in self._descriptors:
                self._descriptors[service_type] = []

            self._descriptors[service_type].append(descriptor)

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
            service_type,
            lifecycle=lifecycle,
            factory=factory,
            is_async=is_async,
            context_key=context_key,
        )

    def lazy_resolve(self, service_type: Type[T], context_key: str = "") -> Lazy[T]:
        """Get a lazy wrapper for a dependency."""
        return Lazy(self, service_type, context_key)

    def resolve(self, service_type: Type[T], context_key: str = "") -> T:
        """Synchronously resolve a service from the container."""
        with self._lock:
            # test mode, check for mocks first
            if self._test_mode and service_type in self._mock_instances:
                return self._mock_instances[service_type]

            # Check for circular dependencies
            if service_type in self._resolution_stack:
                path = " -> ".join(
                    [t.__name__ for t in self._resolution_stack]
                    + [service_type.__name__]
                )
                raise CircularDependencyError(
                    f"Circular dependency detected: {path}\n"
                    f"Resolution stack (newest first):\n"
                    + "\n".join(
                        [
                            f"  {i + 1}. {t.__name__}"
                            for i, t in enumerate(reversed(self._resolution_stack))
                        ]
                    )
                )

            # resolution stack for circular dependency detection
            self._resolution_stack.append(service_type)

            try:
                descriptor = self._get_descriptor(service_type, context_key)

                # Just-in-time registration for injectable classes
                if (
                    not descriptor
                    and hasattr(service_type, "__di_injectable__")
                    and getattr(service_type, "__di_injectable__")
                ):

                    # Extract metadata (this added from decorator)
                    lifecycle = getattr(
                        service_type, "__di_lifecycle__", Lifecycle.SINGLETON
                    )
                    ctx_key = getattr(service_type, "__di_context_key__", context_key)
                    is_async = getattr(service_type, "__di_is_async__", False)
                    resolution_strategy = getattr(
                        service_type,
                        "__di_resolution_strategy__",
                        ResolutionStrategy.EAGER,
                    )

                    # Register automatically
                    self.register(
                        service_type,
                        lifecycle=lifecycle,
                        context_key=ctx_key,
                        is_async=is_async,
                        resolution_strategy=resolution_strategy,
                    )

                    # update descriptor
                    descriptor = self._get_descriptor(service_type, context_key)

                if not descriptor:
                    raise DependencyNotFoundError(
                        f"No registration found for {service_type.__name__}"
                    )

                if (
                    descriptor.lifecycle == Lifecycle.SINGLETON
                    and descriptor.instance is not None
                ):
                    return descriptor.instance

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

                # Apply property injections using cache
                impl_type = descriptor.implementation_type
                if impl_type not in self._property_injection_cache:
                    self._property_injection_cache[impl_type] = {}
                    if hasattr(impl_type, "__di_property_injections__"):
                        self._property_injection_cache[impl_type] = getattr(
                            impl_type, "__di_property_injections__", {}
                        )

                for prop_name, prop_type in self._property_injection_cache[
                    impl_type
                ].items():
                    try:
                        setattr(
                            instance, prop_name, self.resolve(prop_type, context_key)
                        )
                    except DependencyNotFoundError as e:
                        raise DependencyNotFoundError(
                            f"Failed to inject property '{prop_name}' of type {prop_type.__name__} "
                            f"into {service_type.__name__} instance: {str(e)}",
                            prop_type,
                            context_key,
                        ) from e

                # Apply method injections using cache
                if impl_type not in self._method_injection_cache:
                    self._method_injection_cache[impl_type] = {}
                    if hasattr(impl_type, "__di_method_injections__"):
                        self._method_injection_cache[impl_type] = getattr(
                            impl_type, "__di_method_injections__", {}
                        )

                for method_name, param_types in self._method_injection_cache[
                    impl_type
                ].items():
                    method = getattr(instance, method_name)
                    params = {
                        name: self.resolve(typ, context_key)
                        for name, typ in param_types.items()
                    }
                    method(**params)

                # Call on_init if provided
                if descriptor.on_init and not descriptor.is_async:
                    descriptor.on_init(instance)

                if descriptor.lifecycle == Lifecycle.SINGLETON:
                    descriptor.instance = instance

                return instance
            except DependencyNotFoundError as e:
                raise e
            finally:
                self._resolution_stack.pop()

    async def resolve_async(self, service_type: Type[T], context_key: str = "") -> T:
        """Asynchronously resolve a service from the container."""
        with self._lock:
            # test mode, check for mocks first
            if self._test_mode and service_type in self._mock_instances:
                return self._mock_instances[service_type]

            # Check for circular dependencies
            if service_type in self._resolution_stack:
                path = " -> ".join(
                    [t.__name__ for t in self._resolution_stack]
                    + [service_type.__name__]
                )
                raise CircularDependencyError(f"Circular dependency detected: {path}")

            # resolution stack for circular dependency detection
            self._resolution_stack.append(service_type)

            try:
                descriptor = self._get_descriptor(service_type, context_key)

                # Just-in-time registration for injectable classes
                if (
                    not descriptor
                    and hasattr(service_type, "__di_injectable__")
                    and getattr(service_type, "__di_injectable__")
                ):

                    # Extract metadata from the class
                    lifecycle = getattr(
                        service_type, "__di_lifecycle__", Lifecycle.SINGLETON
                    )
                    ctx_key = getattr(service_type, "__di_context_key__", context_key)
                    is_async = getattr(service_type, "__di_is_async__", False)
                    resolution_strategy = getattr(
                        service_type,
                        "__di_resolution_strategy__",
                        ResolutionStrategy.EAGER,
                    )

                    # Register it automatically
                    self.register(
                        service_type,
                        lifecycle=lifecycle,
                        context_key=ctx_key,
                        is_async=is_async,
                        resolution_strategy=resolution_strategy,
                    )

                    descriptor = self._get_descriptor(service_type, context_key)

                if not descriptor:
                    raise DependencyNotFoundError(
                        f"No registration found for {service_type.__name__}"
                    )

                if (
                    descriptor.lifecycle == Lifecycle.SINGLETON
                    and descriptor.instance is not None
                ):
                    return descriptor.instance

                if descriptor.factory:
                    if descriptor.is_async:
                        instance = await descriptor.factory(self)
                    else:
                        instance = descriptor.factory(self)
                else:
                    instance = await self._create_instance_async(
                        descriptor.implementation_type
                    )

                impl_type = descriptor.implementation_type
                if impl_type not in self._property_injection_cache:
                    self._property_injection_cache[impl_type] = {}
                    if hasattr(impl_type, "__di_property_injections__"):
                        self._property_injection_cache[impl_type] = getattr(
                            impl_type, "__di_property_injections__", {}
                        )

                for prop_name, prop_type in self._property_injection_cache[
                    impl_type
                ].items():
                    prop_descriptor = self._get_descriptor(prop_type, context_key)
                    if prop_descriptor and prop_descriptor.is_async:
                        setattr(
                            instance,
                            prop_name,
                            await self.resolve_async(prop_type, context_key),
                        )
                    else:
                        setattr(
                            instance, prop_name, self.resolve(prop_type, context_key)
                        )

                if impl_type not in self._method_injection_cache:
                    self._method_injection_cache[impl_type] = {}
                    if hasattr(impl_type, "__di_method_injections__"):
                        self._method_injection_cache[impl_type] = getattr(
                            impl_type, "__di_method_injections__", {}
                        )

                for method_name, param_types in self._method_injection_cache[
                    impl_type
                ].items():
                    method = getattr(instance, method_name)
                    params = {}
                    for name, typ in param_types.items():
                        param_descriptor = self._get_descriptor(typ, context_key)
                        if param_descriptor and param_descriptor.is_async:
                            params[name] = await self.resolve_async(typ, context_key)
                        else:
                            params[name] = self.resolve(typ, context_key)
                    method(**params)

                if descriptor.on_init:
                    if descriptor.is_async:
                        await descriptor.on_init(instance)
                    else:
                        descriptor.on_init(instance)

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
                descriptor = module._container._get_descriptor(
                    service_type, context_key
                )
                if descriptor:
                    return descriptor
            return None

        # Find the appropriate descriptor based on context
        return next(
            (d for d in descriptors if d.context_key == context_key), descriptors[0]
        )

    def _create_instance(self, implementation_type: Type[T]) -> T:
        """Create a new instance with constructor injection."""
        try:
            if not hasattr(implementation_type, "__init__"):
                instance = implementation_type()
                # set container reference for property injections
                setattr(instance, "_container", self)
                # Apply property injections after construction
                self._apply_property_injections(instance, implementation_type)
                return instance

            # Get the constructor
            init = implementation_type.__init__
            if init is object.__init__:  # Default constructor
                instance = implementation_type()
                # set container reference for property injections
                setattr(instance, "_container", self)
                # Apply property injections after construction
                self._apply_property_injections(instance, implementation_type)
                return instance

            # Get parameter annotations using cached signature
            if implementation_type not in self._signature_cache:
                self._signature_cache[implementation_type] = inspect.signature(init)

            sig = self._signature_cache[implementation_type]
            params = {}

            for name, param in sig.parameters.items():
                if name == "self":
                    continue

                # Skip parameters with default values
                if param.default is not inspect.Parameter.empty:
                    continue  # Parameter has default, don't inject it

                annotation = param.annotation
                if annotation is inspect.Parameter.empty:
                    # Cannot resolve parameter without type annotation
                    raise DependencyNotFoundError(
                        f"Cannot resolve parameter '{name}' for {implementation_type.__name__} "
                        f"without type annotation"
                    )

                # Handle string annotations (forward references)
                if isinstance(annotation, str):
                    # Try multiple resolution strategies
                    resolved = False

                    # 1. check if any registered type has this name
                    for registered_type in self._descriptors:
                        if registered_type.__name__ == annotation:
                            annotation = registered_type
                            resolved = True
                            break

                    # 2. evaluate in module context
                    if not resolved:
                        impl_module = inspect.getmodule(implementation_type)
                        try:
                            if impl_module:
                                # Add registered types to evaluation context
                                module_dict = impl_module.__dict__.copy()
                                for service_type in self._descriptors:
                                    module_dict[service_type.__name__] = service_type

                                # Try to evaluate
                                annotation = eval(
                                    annotation,
                                    module_dict,
                                    implementation_type.__dict__,
                                )
                                resolved = True
                        except (NameError, SyntaxError):
                            pass  # Will be handled in the next check

                    # If we still couldn't resolve it
                    if not resolved:
                        raise DependencyNotFoundError(
                            f"Cannot resolve forward reference '{annotation}' for parameter '{name}' "
                            f"in {implementation_type.__name__}.__init__"
                        )

                # Check for primitive types
                primitive_types = (str, int, float, bool, list, dict, tuple, set)
                if annotation in primitive_types:
                    raise DependencyNotFoundError(
                        f"Cannot automatically resolve primitive type '{annotation.__name__}' for parameter '{name}' "
                        f"in {implementation_type.__name__}.__init__. Consider using a factory, "
                        f"providing a default value, or registering the primitive type."
                    )

                # Check if this is a lazy dependency
                if getattr(annotation, "__origin__", None) == Lazy:
                    params[name] = self.lazy_resolve(annotation.__args__[0])
                else:
                    # Regular dependency
                    params[name] = self.resolve(annotation)

            instance = implementation_type(**params)
            setattr(instance, "_container", self)

            # Apply property injections
            self._apply_property_injections(instance, implementation_type)

            return instance
        except Exception as e:
            raise DependencyNotFoundError(
                f"Error creating instance of {implementation_type.__name__}: {str(e)}"
            ) from e

    def _apply_property_injections(self, instance: Any, impl_type: Type) -> None:
        """Apply property injections to an instance.
        This is extracted to a separate method for clarity and reuse."""
        # Get the cached property injections
        if impl_type not in self._property_injection_cache:
            self._property_injection_cache[impl_type] = {}
            if hasattr(impl_type, "__di_property_injections__"):
                self._property_injection_cache[impl_type] = getattr(
                    impl_type, "__di_property_injections__", {}
                )

        # Apply each property injection
        for prop_name, prop_type in self._property_injection_cache[impl_type].items():
            try:
                # Check if the property is already set
                backing_field = f"_{prop_name}"
                if (
                    not hasattr(instance, backing_field)
                    or getattr(instance, backing_field) is None
                ):
                    setattr(instance, prop_name, self.resolve(prop_type))
            except DependencyNotFoundError as e:
                raise DependencyNotFoundError(
                    f"Failed to inject property '{prop_name}' of type {prop_type.__name__} "
                    f"into {impl_type.__name__} instance: {str(e)}",
                    prop_type,
                    "",
                ) from e

    async def _create_instance_async(self, implementation_type: Type[T]) -> T:
        """Create a new instance with constructor injection, supporting async dependencies."""
        try:
            if not hasattr(implementation_type, "__init__"):
                return implementation_type()

            # Get the constructor
            init = implementation_type.__init__
            if init is object.__init__:  # Default constructor
                return implementation_type()

            # Get parameter annotations using cached signature
            if implementation_type not in self._signature_cache:
                self._signature_cache[implementation_type] = inspect.signature(init)

            sig = self._signature_cache[implementation_type]
            params = {}

            for name, param in sig.parameters.items():
                if name == "self":
                    continue

                # Skip parameters with default values
                if param.default is not inspect.Parameter.empty:
                    continue  # Parameter has default, don't inject it

                annotation = param.annotation
                if annotation is inspect.Parameter.empty:
                    # Cannot resolve parameter without type annotation
                    raise DependencyNotFoundError(
                        f"Cannot resolve parameter '{name}' for {implementation_type.__name__} "
                        f"without type annotation"
                    )

                # Handle string annotations (forward references)
                if isinstance(annotation, str):
                    resolved = False

                    for registered_type in self._descriptors:
                        if registered_type.__name__ == annotation:
                            annotation = registered_type
                            resolved = True
                            break

                    if not resolved:
                        impl_module = inspect.getmodule(implementation_type)
                        try:
                            if impl_module:
                                module_dict = impl_module.__dict__.copy()
                                for service_type in self._descriptors:
                                    module_dict[service_type.__name__] = service_type

                                annotation = eval(
                                    annotation,
                                    module_dict,
                                    implementation_type.__dict__,
                                )
                                resolved = True
                        except (NameError, SyntaxError):
                            pass

                    if not resolved:
                        raise DependencyNotFoundError(
                            f"Cannot resolve forward reference '{annotation}' for parameter '{name}' "
                            f"in {implementation_type.__name__}.__init__"
                        )

                primitive_types = (str, int, float, bool, list, dict, tuple, set)
                if annotation in primitive_types:
                    raise DependencyNotFoundError(
                        f"Cannot automatically resolve primitive type '{annotation.__name__}' for parameter '{name}' "
                        f"in {implementation_type.__name__}.__init__. Consider using a factory, "
                        f"providing a default value, or registering the primitive type."
                    )

                if getattr(annotation, "__origin__", None) == Lazy:
                    params[name] = self.lazy_resolve(annotation.__args__[0])
                else:
                    # Get the descriptor to check if it's async
                    descriptor = self._get_descriptor(annotation)
                    if descriptor and descriptor.is_async:
                        params[name] = await self.resolve_async(annotation)
                    else:
                        params[name] = self.resolve(annotation)

            instance = implementation_type(**params)
            setattr(instance, "_container", self)
            return instance

        except Exception as e:
            raise DependencyNotFoundError(
                f"Error creating async instance of {implementation_type.__name__}: {str(e)}"
            ) from e

    def create_scope(self) -> Scope:
        """Create a new dependency scope."""
        return Scope(self)

    def register_module(self, module: "Module", namespace: str = "") -> "Container":
        """Register a module with the container."""
        # If no namespace is provided, use the module's name
        if not namespace and hasattr(module, "name"):
            namespace = module.name

        if namespace in self._modules:
            warnings.warn(
                f"Module namespace '{namespace}' is already registered. Overwriting."
            )
        self._modules[namespace] = module
        module.parent_container = self

        # Copy module registrations to parent container with proper handling of injections
        for service_type, descriptors in module._container._descriptors.items():
            if service_type not in self._descriptors:
                self._descriptors[service_type] = []

            # Add descriptors from module to parent container
            for descriptor in descriptors:
                # Create a copy of the descriptor to avoid reference issues
                parent_descriptor = ServiceDescriptor(
                    service_type=descriptor.service_type,
                    implementation_type=descriptor.implementation_type,
                    lifecycle=descriptor.lifecycle,
                    factory=descriptor.factory,
                    instance=descriptor.instance,
                    context_key=descriptor.context_key,
                    is_async=descriptor.is_async,
                    resolution_strategy=descriptor.resolution_strategy,
                    on_init=descriptor.on_init,
                    on_destroy=descriptor.on_destroy,
                )

                # Copy property injections
                for prop_name, prop_type in descriptor.property_injections.items():
                    parent_descriptor.property_injections[prop_name] = prop_type

                # Copy method injections
                for method_name, params in descriptor.method_injections.items():
                    parent_descriptor.method_injections[method_name] = params.copy()

                # Add to parent container
                self._descriptors[service_type].append(parent_descriptor)

                # Update cache
                impl_type = descriptor.implementation_type
                if impl_type and hasattr(impl_type, "__di_property_injections__"):
                    if impl_type not in self._property_injection_cache:
                        self._property_injection_cache[impl_type] = {}

                    for prop_name, prop_type in getattr(
                        impl_type, "__di_property_injections__", {}
                    ).items():
                        self._property_injection_cache[impl_type][prop_name] = prop_type

                if impl_type and hasattr(impl_type, "__di_method_injections__"):
                    if impl_type not in self._method_injection_cache:
                        self._method_injection_cache[impl_type] = {}

                    for method_name, params in getattr(
                        impl_type, "__di_method_injections__", {}
                    ).items():
                        self._method_injection_cache[impl_type][method_name] = (
                            params.copy()
                        )

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
