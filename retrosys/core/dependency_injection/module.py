from typing import Optional, Type, Union, Callable, Awaitable, Any, TYPE_CHECKING
from .project_types import (
    T,
    Lifecycle,
    FactoryCallable,
    AsyncFactoryCallable,
    ResolutionStrategy,
)
from .errors import DependencyNotFoundError

if TYPE_CHECKING:
    from .container import Container

import inspect


class Module:
    """A group of related dependencies in the dependency injection system.

    Modules provide a way to organize related services into logical groups and
    encapsulate their registrations. They act as containers for related dependencies
    and can be registered with a parent container to make all their services available.

    Modules have their own container for registering services, but can also access
    services from their parent container when registered with one.

    Attributes:
        _container: The internal container used for service registrations.
        parent_container: Reference to the parent container if registered.
        name: The name of the module, used for identification and namespace.
    """

    def __init__(self, name: str = ""):
        """Initialize a new module.

        Creates a new module with its own internal container for service registrations.

        Args:
            name: Optional name for the module, used for identification when registered
                with a parent container. Defaults to an empty string.
        """
        from .container import Container

        self._container = Container()
        self.parent_container: Optional["Container"] = None
        self.name = name

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
    ) -> "Module":
        """Register a service with the module.

        This method registers a service type with its implementation type, lifecycle,
        factory functions, and other configuration options in the module's container.

        Args:
            service_type: The type to register, typically an interface or abstract class.
            implementation_type: The concrete implementation type to instantiate when resolving
                the service_type. If None, the service_type itself is used as the implementation.
            lifecycle: Determines how instances are created and cached (singleton, transient, scoped).
                Defaults to Lifecycle.SINGLETON.
            factory: Optional factory function to create instances of the service.
                If provided, this is used instead of constructor injection.
            context_key: Optional key for contextual binding, allowing multiple implementations
                of the same type to be registered with different keys.
            is_async: Whether this service requires asynchronous initialization.
                Set to True for services that have async dependencies or initialization logic.
            resolution_strategy: Whether to resolve the service eagerly or lazily.
                Defaults to ResolutionStrategy.EAGER.
            on_init: Optional callback function to invoke after a service instance is created.
            on_destroy: Optional callback function to invoke when a service instance is being destroyed.

        Returns:
            Module: The module instance for method chaining.
        """
        self._container.register(
            service_type,
            implementation_type,
            lifecycle,
            factory,
            context_key,
            is_async,
            resolution_strategy,
            on_init,
            on_destroy,
        )
        return self

    def register_instance(self, service_type: Type[T], instance: T) -> "Module":
        """Register an existing instance with the module.

        This is a convenience method for registering pre-constructed instances as singletons
        within the module's container.

        Args:
            service_type: The type to register the instance as, typically an interface or base class.
            instance: The pre-constructed instance to register.

        Returns:
            Module: The module instance for method chaining.
        """
        self._container.register_instance(service_type, instance)
        return self

    def register_factory(
        self,
        service_type: Type[T],
        factory: Union[FactoryCallable, AsyncFactoryCallable],
        lifecycle: Lifecycle = Lifecycle.SINGLETON,
        is_async: bool = False,
    ) -> "Module":
        """Register a factory function for a service with the module.

        This is a convenience method for registering a factory function that creates
        service instances within the module's container.

        Args:
            service_type: The type to register, typically an interface or abstract class.
            factory: A function that creates an instance of the service.
                For async factories, this should return a coroutine.
            lifecycle: Determines how instances are created and cached.
                Defaults to Lifecycle.SINGLETON.
            is_async: Whether this factory is asynchronous. This is automatically
                detected for coroutine functions but can be explicitly set.

        Returns:
            Module: The module instance for method chaining.

        Side Effects:
            Automatically detects if the factory is a coroutine function and sets
            is_async accordingly.
        """
        if inspect.iscoroutinefunction(factory):
            is_async = True
        self._container.register_factory(service_type, factory, lifecycle, is_async)
        return self

    def _get_descriptor(self, service_type: Type, context_key: str = ""):
        """Get the service descriptor for a type.

        This internal method retrieves the service descriptor from the module's
        container for a given service type and context key.

        Args:
            service_type: The type to get the descriptor for.
            context_key: Optional context key for disambiguating multiple registrations
                of the same type. Defaults to an empty string.

        Returns:
            Optional[ServiceDescriptor]: The service descriptor if found, None otherwise.
        """
        return self._container._get_descriptor(service_type, context_key)

    def resolve(self, service_type: Type[T], context_key: str = "") -> T:
        """Resolve a service from the module.

        This method resolves and returns an instance of the requested service type.
        It first checks the module's own container, and if not found there, falls back
        to the parent container (if registered with one).

        Args:
            service_type: The type of service to resolve.
            context_key: Optional key for contextual binding. Defaults to an empty string.

        Returns:
            T: An instance of the requested service type.

        Raises:
            DependencyNotFoundError: If the service type is not registered in this module
                or its parent container.
        """
        # First check local module container
        descriptor = self._container._get_descriptor(service_type, context_key)
        if descriptor:
            return self._container.resolve(service_type, context_key)

        # Then check parent container if available
        if self.parent_container:
            return self.parent_container.resolve(service_type, context_key)

        # If no parent and not found locally, raise exception
        raise DependencyNotFoundError(
            f"No registration found for {service_type.__name__}"
        )

    async def resolve_async(self, service_type: Type[T], context_key: str = "") -> T:
        """Asynchronously resolve a service from the module.

        This method asynchronously resolves and returns an instance of the requested service type.
        It first checks the module's own container, and if not found there, falls back
        to the parent container (if registered with one).

        Args:
            service_type: The type of service to resolve.
            context_key: Optional key for contextual binding. Defaults to an empty string.

        Returns:
            T: An instance of the requested service type.

        Raises:
            DependencyNotFoundError: If the service type is not registered in this module
                or its parent container.
        """

        descriptor = self._container._get_descriptor(service_type, context_key)
        if descriptor:
            return await self._container.resolve_async(service_type, context_key)

        if self.parent_container:
            return await self.parent_container.resolve_async(service_type, context_key)

        raise DependencyNotFoundError(
            f"No registration found for {service_type.__name__}"
        )
