from typing import Generic, Type
from .project_types import T, ContainerProtocol


class Lazy(Generic[T]):
    """Wrapper for lazy dependency resolution."""

    def __init__(
        self, container: ContainerProtocol, service_type: Type[T], context_key: str = ""
    ):
        self._container = container
        self._service_type = service_type
        self._context_key = context_key
        self._instance = None
        self._resolved = False

    def __call__(self) -> T:
        """Resolve the dependency when called."""
        if not self._resolved:
            self._instance = self._container.resolve(
                self._service_type, self._context_key
            )
            self._resolved = True
        return self._instance

    async def async_resolve(self) -> T:
        """Async version of resolve."""
        if not self._resolved:
            self._instance = await self._container.resolve_async(
                self._service_type, self._context_key
            )
            self._resolved = True
        return self._instance
