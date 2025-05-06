from typing import Generic, Type
from .project_types import T, ContainerProtocol


class Lazy(Generic[T]):
    """Wrapper for lazy dependency resolution.

    This class provides a way to delay the resolution of a dependency until it is
    actually needed. It acts as a proxy that resolves the dependency only when
    accessed, which can help break circular dependencies and improve performance
    when expensive dependencies might not always be used.

    Attributes:
        _container: The dependency injection container used to resolve the service.
        _service_type: The type of service to be lazily resolved.
        _context_key: Optional key for contextual binding.
        _instance: Cached instance of the resolved service (None until resolved).
        _resolved: Flag indicating whether the service has been resolved.

    Usage:
        # As a variable
        lazy_service = container.lazy_resolve(ServiceType)
        # Later, when needed
        service_instance = lazy_service()

        # For async resolution
        service_instance = await lazy_service.async_resolve()
    """

    def __init__(
        self, container: ContainerProtocol, service_type: Type[T], context_key: str = ""
    ):
        """Initialize a new lazy dependency reference.

        Args:
            container: The container that will be used to resolve the service.
            service_type: The type of service to be lazily resolved.
            context_key: Optional key for contextual binding. Defaults to an empty string.
        """
        self._container = container
        self._service_type = service_type
        self._context_key = context_key
        self._instance = None
        self._resolved = False

    def __call__(self) -> T:
        """Resolve the dependency when the lazy object is called.

        This method allows the Lazy object to be used like a function.
        When called, it resolves the dependency if not already resolved,
        caches the instance, and returns it.

        Returns:
            T: The resolved service instance.

        Side Effects:
            Resolves the dependency and caches it on first call.
        """
        if not self._resolved:
            self._instance = self._container.resolve(
                self._service_type, self._context_key
            )
            self._resolved = True
        return self._instance

    async def async_resolve(self) -> T:
        """Asynchronously resolve the dependency.

        This method is the asynchronous counterpart to __call__. It should be used
        when working with services that require async resolution.

        Returns:
            T: The resolved service instance.

        Side Effects:
            Asynchronously resolves the dependency and caches it on first call.
        """
        if not self._resolved:
            self._instance = await self._container.resolve_async(
                self._service_type, self._context_key
            )
            self._resolved = True
        return self._instance
