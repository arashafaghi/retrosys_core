import functools
from typing import Type, Dict
import inspect
from .project_types import Lifecycle, ResolutionStrategy
from .module import Module


def injectable(
    lifecycle: Lifecycle = Lifecycle.SINGLETON,
    context_key: str = "",
    is_async: bool = False,
    resolution_strategy: ResolutionStrategy = ResolutionStrategy.EAGER,
):
    """Marks a class as injectable by the dependency injection container.

    This decorator attaches special metadata attributes to a class to make it
    recognizable by the dependency injection system. It configures how the
    class should be instantiated, cached, and resolved by the container.

    Args:
        lifecycle: Determines how instances are created and cached. Options are:
            - SINGLETON: One instance per container
            - TRANSIENT: New instance per resolution
            - SCOPED: One instance per scope
            Defaults to Lifecycle.SINGLETON.
        context_key: Optional key for contextual binding, allowing multiple
            implementations of the same type. Defaults to an empty string.
        is_async: Whether this service requires asynchronous initialization.
            Defaults to False.
        resolution_strategy: Whether to resolve the service eagerly or lazily.
            Options are:
            - EAGER: Resolve immediately when registered
            - LAZY: Resolve only when requested
            Defaults to ResolutionStrategy.EAGER.

    Returns:
        A decorator function that attaches DI metadata to the decorated class.

    Side Effects:
        Sets the following attributes on the decorated class:
        - __di_injectable__: Marker indicating the class is injectable
        - __di_lifecycle__: The lifecycle strategy
        - __di_context_key__: The context key for disambiguating registrations
        - __di_is_async__: Whether the class requires async initialization
        - __di_resolution_strategy__: The resolution strategy
        Also auto-detects async initialization based on the __init__ method.
    """

    def decorator(cls):
        # Store DI metadata on the class
        setattr(cls, "__di_injectable__", True)
        setattr(cls, "__di_lifecycle__", lifecycle)
        setattr(cls, "__di_context_key__", context_key)
        setattr(cls, "__di_is_async__", is_async)
        setattr(cls, "__di_resolution_strategy__", resolution_strategy)

        # Auto-detect async initialization
        if hasattr(cls, "__init__") and inspect.iscoroutinefunction(cls.__init__):
            setattr(cls, "__di_is_async__", True)

        return cls

    return decorator


def inject_property(service_type: Type):
    """Creates a property that automatically resolves a dependency when accessed.

    This decorator creates a descriptor that lazily resolves a dependency from
    the container when the property is accessed. It enables property injection
    by using a backing field to store the resolved instance.

    Args:
        service_type: The type of service to be injected when the property is accessed.
            This should be a type (class) that is registered with the container.

    Returns:
        A property descriptor that resolves and returns the dependency when accessed.

    Side Effects:
        - Creates a backing field (with the same name as the property but prefixed with '_')
            to store the resolved dependency.
        - Registers the property in the class's __di_property_injections__ dictionary
            for automatic resolution during instance creation.
        - When accessed, attempts to resolve the dependency from the container
            if not already resolved.

    Usage Example:
        ```python
        class MyService:
            @inject_property(IDatabase)
            def database(self):
                pass  # The method body is not used
        ```
    """

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
                if value is None and hasattr(obj, "_container"):
                    container = getattr(obj, "_container")
                    try:
                        resolved_value = container.resolve(service_type)
                        setattr(obj, backing_field, resolved_value)
                        return resolved_value
                    except Exception:
                        # Fall back to returning None if resolution fails
                        pass

                return value

            def __set__(self, obj, value):
                setattr(obj, f"_{prop_name}", value)

            def __set_name__(self, owner, name):
                if not hasattr(owner, "__di_property_injections__"):
                    setattr(owner, "__di_property_injections__", {})
                getattr(owner, "__di_property_injections__")[name] = service_type

        return PropertyDescriptor()

    return decorator


def inject_method(params: Dict[str, Type]):
    """Automatically injects dependencies as parameters to a method.

    This decorator allows method parameters to be automatically injected from the
    dependency injection container. It wraps the original method and resolves the
    specified dependencies before calling it, unless they are explicitly provided
    in the method call.

    Args:
        params: A dictionary mapping parameter names to their types. Each entry
            specifies a parameter to be injected and the type of service to resolve
            from the container.

    Returns:
        A decorated method that automatically resolves and injects dependencies.

    Side Effects:
        - Wraps the original method to intercept calls and inject dependencies.
        - Registers the method in the class's __di_method_injections__ dictionary
            for automatic resolution during instance creation.
        - When called, resolves dependencies from the container if not explicitly provided.
        - Attempts to find a container reference from various common attribute names
            or creates a new container if none is found.

    Usage Example:
        ```python
        class MyService:
            @inject_method({'database': IDatabase, 'logger': ILogger})
            def process_data(self, data, database, logger):
                # database and logger are automatically injected
                pass
        ```
    """

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
                    for attr_name in ["_container", "_di_container", "__container__"]:
                        if hasattr(self, attr_name):
                            container = getattr(self, attr_name)
                            break

                    # If we have a container, resolve the dependency
                    if container:
                        method_params[param_name] = container.resolve(param_type)
                    else:
                        # Without container, try to lookup from registry if registered
                        from retrosys.core.dependency_injection.container import (
                            Container,
                        )

                        c = Container()
                        method_params[param_name] = c.resolve(param_type)

            # Combine with explicitly provided parameters
            method_params.update(kwargs)

            # Call the original method with all parameters
            return method(self, **method_params)

        # Store metadata for the DI container to use during resolution
        setattr(wrapper, "__di_method_params__", params)

        def __set_name__(owner, name):
            if not hasattr(owner, "__di_method_injections__"):
                setattr(owner, "__di_method_injections__", {})
            getattr(owner, "__di_method_injections__")[name] = params

        wrapper.__set_name__ = __set_name__

        return wrapper

    return decorator


def register_module(container):
    """Scans a class for injectable components and registers them with a container.

    This decorator examines a class (typically a module definition class) and finds
    all of its member classes that have been marked as injectable using the @injectable
    decorator. It creates a Module instance and registers all discovered injectable
    components with that module, then registers the module with the provided container.

    This enables organizing related services into modules for better structuring of
    the dependency injection system.

    Args:
        container: The dependency injection container to register the module with.
            This should be an instance of Container.

    Returns:
        A decorator function that processes a class and returns it after registering
        all its injectable members.

    Raises:
        TypeError: If the decorated object is not a class.

    Side Effects:
        - Creates a new Module instance named after the decorated class.
        - Registers all injectable members of the class with the module.
        - Registers any property and method injections for the members.
        - Registers the completed module with the provided container.

    Usage Example:
        ```python
        @register_module(container)
        class DataModule:
            @injectable()
            class DatabaseService:
                pass

            @injectable()
            class RepositoryService:
                pass
        ```
    """

    def decorator(module_class):
        if not inspect.isclass(module_class):
            raise TypeError("@register_module can only be applied to classes")

        module = Module(module_class.__name__)

        # Find all injectable members
        for name, member in inspect.getmembers(module_class):
            if inspect.isclass(member) and getattr(member, "__di_injectable__", False):
                lifecycle = getattr(member, "__di_lifecycle__", Lifecycle.SINGLETON)
                context_key = getattr(member, "__di_context_key__", "")
                is_async = getattr(member, "__di_is_async__", False)
                resolution_strategy = getattr(
                    member, "__di_resolution_strategy__", ResolutionStrategy.EAGER
                )

                # Register the service
                module.register(
                    member,
                    lifecycle=lifecycle,
                    context_key=context_key,
                    is_async=is_async,
                    resolution_strategy=resolution_strategy,
                )

                # Add property injections if they exist - FIX: properly look up the descriptor
                property_injections = getattr(member, "__di_property_injections__", {})
                if property_injections:
                    descriptor = module._container._get_descriptor(member)
                    if descriptor:
                        for prop_name, prop_type in property_injections.items():
                            descriptor.property_injections[prop_name] = prop_type

                # Add method injections
                method_injections = getattr(member, "__di_method_injections__", {})
                if method_injections:
                    descriptor = module._container._get_descriptor(member)
                    if descriptor:
                        for method_name, params in method_injections.items():
                            descriptor.method_injections[method_name] = params

        # Register the module with the container
        container.register_module(module)
        return module_class

    return decorator
