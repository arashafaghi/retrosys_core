from typing import Dict, Any, Type
from .project_types import T, Lifecycle, ContainerProtocol
import inspect


class Scope:
    """Represents a dependency injection scope."""

    def __init__(self, parent_container: ContainerProtocol):
        """Initialize a new dependency injection scope.

        Creates a new scope with its own container that inherits from the parent
        container. The scope maintains a cache of resolved service instances.

        Args:
            parent_container (ContainerProtocol): The parent container that this
                scope will create a child container from.

        Side Effects:
            Creates a child container from the parent container.
        """
        self._container = parent_container.create_child_container()
        self._instances: Dict[Type, Any] = {}

    def resolve(self, service_type: Type[T], context_key: str = "") -> T:
        """Resolves a service instance within the current scope.

        This method retrieves or creates a service instance of the specified type.
        If the instance already exists in the scope's cache, it returns the cached
        instance. Otherwise, it resolves the service from the container
        and caches it if it has a scoped lifecycle.

        Args:
            service_type (Type[T]): The type of service to resolve.
            context_key (str, optional): A key for contextual binding resolution.
                Defaults to an empty string.

        Returns:
            T: An instance of the requested service type.

        Side Effects:
            Updates the internal instances cache if the resolved service has a
            scoped lifecycle.
        """
        if service_type in self._instances:
            return self._instances[service_type]

        instance = self._container.resolve(service_type, context_key)

        # Cache scoped instances
        descriptor = self._container._get_descriptor(service_type, context_key)
        if descriptor and descriptor.lifecycle == Lifecycle.SCOPED:
            self._instances[service_type] = instance

        return instance

    async def resolve_async(self, service_type: Type[T], context_key: str = "") -> T:
        """Asynchronously resolves a service instance within the current scope.

        This method retrieves or creates a service instance of the specified type.
        If the instance already exists in the scope's cache, it returns the cached
        instance. Otherwise, it asynchronously resolves the service from the container
        and caches it if it has a scoped lifecycle.

        Args:
            service_type (Type[T]): The type of service to resolve.
            context_key (str, optional): A key for contextual binding resolution.
                Defaults to an empty string.

        Returns:
            T: An instance of the requested service type.

        Side Effects:
            Updates the internal instances cache if the resolved service has a
            scoped lifecycle.
        """
        if service_type in self._instances:
            return self._instances[service_type]

        instance = await self._container.resolve_async(service_type, context_key)

        # Cache scoped instances
        descriptor = self._container._get_descriptor(service_type, context_key)
        if descriptor and descriptor.lifecycle == Lifecycle.SCOPED:
            self._instances[service_type] = instance

        return instance

    async def __aenter__(self) -> "Scope":
        """Async context manager entry point.

        Allows the scope to be used as an async context manager with the 'async with' statement.

        Returns:
            Scope: Returns self to be used within the context manager.
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit point.

        Called when exiting an 'async with' block. Automatically disposes of all
        scoped instances by calling the dispose method.

        Args:
            exc_type: The exception type if an exception was raised in the context block, None otherwise.
            exc_val: The exception value if an exception was raised in the context block, None otherwise.
            exc_tb: The traceback if an exception was raised in the context block, None otherwise.

        Side Effects:
            Calls the dispose method to clean up all scoped instances.
        """
        await self.dispose()

    async def dispose(self):
        """Dispose of all scoped instances.

        This method cleans up all service instances managed by this scope.
        It attempts to call the dispose method on instances if they have one,
        or calls the on_destroy handler if specified in the service descriptor.
        Finally, it clears the instances cache.

        The method handles both synchronous and asynchronous dispose/on_destroy methods.

        Side Effects:
            - Calls dispose methods on service instances if available
            - Calls on_destroy handlers from service descriptors if available
            - Catches and logs any exceptions during disposal
            - Clears the internal instances cache
        """
        for service_type, instance in list(self._instances.items()):
            descriptor = self._container._get_descriptor(service_type)
            if descriptor and descriptor.lifecycle == Lifecycle.SCOPED:
                if hasattr(instance, "dispose"):
                    try:
                        dispose_method = instance.dispose
                        if inspect.iscoroutinefunction(dispose_method):
                            await dispose_method()
                        else:
                            dispose_method()
                    except Exception as e:
                        # Log error but continue disposing other instances
                        import logging

                        logging.getLogger(__name__).error(
                            f"Error disposing instance of {service_type}: {e}"
                        )
                elif descriptor.on_destroy:
                    try:
                        if inspect.iscoroutinefunction(descriptor.on_destroy):
                            await descriptor.on_destroy(instance)
                        else:
                            descriptor.on_destroy(instance)
                    except Exception as e:
                        # Log error but continue disposing other instances
                        import logging

                        logging.getLogger(__name__).error(
                            f"Error in on_destroy for {service_type}: {e}"
                        )
        self._instances.clear()
