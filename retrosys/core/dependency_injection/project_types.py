from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Awaitable,
    TypeVar,
    Protocol,
    Optional,
    Type,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from .service_descriptor import ServiceDescriptor

T = TypeVar("T")


class Lifecycle(Enum):
    """Defines how dependencies are instantiated and cached.

    This enum specifies the lifecycle strategy for dependency instances within the container,
    determining when instances are created and how long they are retained.

    Attributes:
        SINGLETON: One instance per container. The instance is created once and reused for all
            resolutions within the container's lifetime.
        TRANSIENT: New instance per resolution. Every time the dependency is requested, a new
            instance is created.
        SCOPED: One instance per scope (e.g., request). The instance is created once per defined
            scope and reused within that scope.
    """

    SINGLETON = auto()  # One instance per container
    TRANSIENT = auto()  # New instance per resolution
    SCOPED = auto()  # One instance per scope (e.g., request)


class ResolutionStrategy(Enum):
    """Defines when dependencies are resolved in the container.

    This enum specifies the strategy for when dependencies should be resolved,
    either immediately upon registration or delayed until the dependency is requested.

    Attributes:
        EAGER: Resolve immediately when the dependency is registered in the container.
            This front-loads initialization costs but ensures dependencies are valid early.
        LAZY: Resolve only when the dependency is actually requested from the container.
            This defers initialization costs but may delay discovery of configuration issues.
    """

    EAGER = auto()  # Resolve immediately
    LAZY = auto()  # Resolve only when needed


class ContainerProtocol(Protocol):
    """Protocol defining the interface for a dependency injection container.

    This protocol specifies the methods that any dependency injection container
    must implement to properly resolve dependencies and manage container hierarchies.

    The container is responsible for resolving services based on their type and
    optional context keys, handling both synchronous and asynchronous resolution.
    """

    def resolve(self, service_type: Type[T], context_key: str = "") -> T:
        """Resolves a service instance from the container.

        Args:
            service_type: The type of service to resolve.
            context_key: Optional context key for disambiguating multiple registrations
                of the same type. Defaults to an empty string.

        Returns:
            T: An instance of the requested service type.

        Raises:
            ResolutionError: If the service cannot be resolved or has not been registered.
        """
        ...

    async def resolve_async(self, service_type: Type[T], context_key: str = "") -> T:
        """Asynchronously resolves a service instance from the container.

        Args:
            service_type: The type of service to resolve.
            context_key: Optional context key for disambiguating multiple registrations
                of the same type. Defaults to an empty string.

        Returns:
            T: An instance of the requested service type.

        Raises:
            ResolutionError: If the service cannot be resolved or has not been registered.
        """
        ...

    def create_child_container(self) -> "ContainerProtocol":
        """Creates a new child container with this container as parent.

        Child containers inherit all registrations from their parent but can override
        them with their own registrations. Resolution in a child container checks the
        child first, then falls back to the parent if the service is not found.

        Returns:
            ContainerProtocol: A new child container instance.
        """
        ...

    def _get_descriptor(
        self, service_type: Type, context_key: str = ""
    ) -> Optional["ServiceDescriptor"]:
        """Gets the service descriptor for a given type and context key.

        This internal method retrieves the descriptor that defines how to create
        and manage instances of the specified service type.

        Args:
            service_type: The type to get the descriptor for.
            context_key: Optional context key for disambiguating multiple registrations
                of the same type. Defaults to an empty string.

        Returns:
            Optional[ServiceDescriptor]: The service descriptor if found, None otherwise.
        """
        ...


FactoryCallable = Callable[[ContainerProtocol], Any]
"""Type for factory functions that create service instances.

A function that accepts a container instance and returns a service instance.
This is used when registering factory methods with the dependency injection container.
"""

AsyncFactoryCallable = Callable[[ContainerProtocol], Awaitable[Any]]
"""Type for asynchronous factory functions that create service instances.

A function that accepts a container instance and returns a coroutine that resolves to a service instance.
This is used when registering async factory methods with the dependency injection container.
"""
