class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected."""
    pass


class DependencyNotFoundError(Exception):
    """Raised when a dependency cannot be resolved."""
    def __init__(self, message, service_type=None, context_key=None):
        self.service_type = service_type
        self.context_key = context_key
        
        # Build detailed message
        detailed_message = message
        if service_type:
            type_name = getattr(service_type, '__name__', str(service_type))
            detailed_message += f"\nService type: {type_name}"
        if context_key:
            detailed_message += f"\nContext key: '{context_key}'"
            
        super().__init__(detailed_message)

class AsyncInitializationError(Exception):
    """Raised when async initialization fails."""
    pass