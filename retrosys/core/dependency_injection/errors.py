class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected."""
    pass

class DependencyNotFoundError(Exception):
    """Raised when a dependency cannot be resolved."""
    pass

class AsyncInitializationError(Exception):
    """Raised when async initialization fails."""
    pass