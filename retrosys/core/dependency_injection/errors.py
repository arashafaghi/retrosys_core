class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected in the container.

    This exception is thrown during service resolution when the dependency injection
    container detects a circular reference in the dependency graph. For example, if
    Service A depends on Service B, which depends on Service C, which depends on Service A,
    this creates a circular dependency that cannot be resolved.
    """

    pass


class DependencyNotFoundError(Exception):
    """Raised when a requested dependency cannot be resolved from the container.

    This exception occurs when attempting to resolve a service that hasn't been
    registered in the container, or when the registered service cannot be properly
    instantiated due to missing dependencies.

    Attributes:
        service_type: The type of the service that could not be resolved.
        context_key: The context key used in the resolution attempt, if any.
        message: The base error message, which will be enhanced with service type
            and context key information.
    """

    def __init__(self, message, service_type=None, context_key=None):
        """Initialize a new DependencyNotFoundError with detailed information.

        Args:
            message: The base error message.
            service_type: The type of service that could not be resolved.
            context_key: The context key used in the resolution attempt, if any.
        """
        self.service_type = service_type
        self.context_key = context_key

        # Build detailed message
        detailed_message = message
        if service_type:
            type_name = getattr(service_type, "__name__", str(service_type))
            detailed_message += f"\nService type: {type_name}"
        if context_key:
            detailed_message += f"\nContext key: '{context_key}'"

        super().__init__(detailed_message)


class AsyncInitializationError(Exception):
    """Raised when asynchronous service initialization fails.

    This exception is thrown when an error occurs during the asynchronous
    initialization of a service, such as when an async factory method fails
    or when an async on_init lifecycle hook throws an exception.
    """

    pass
