import pytest
import asyncio
from typing import List, Optional, Generic, TypeVar

from retrosys.core.dependency_injection import (
    Container, Lifecycle, injectable, inject_property, inject_method, Lazy
)
from retrosys.core.dependency_injection.errors import (
    CircularDependencyError, DependencyNotFoundError
)

class TestPropertyInjection:
    def test_property_injection(self):
    # Arrange
        container = Container()
        
        class Logger:
            def log(self, message: str) -> None:
                pass
        
        class Service:
            def __init__(self):
                self.logger = None
                
            @inject_property(Logger)
            def logger(self):
                pass
        
        # Act
        container.register(Logger)
        container.register(Service)
        resolved = container.resolve(Service)
        
        # Assert
        assert isinstance(resolved, Service)
        assert isinstance(resolved.logger, Logger)

        
class TestMethodInjection:
    def test_method_injection(self):
        # Arrange
        container = Container()
        
        class Logger:
            def log(self, message: str) -> None:
                pass
                
        class Service:
            def __init__(self):
                self.logger_used = False
                
            @inject_method({"logger": Logger})
            def use_logger(self, logger: Logger, message: str) -> None:
                logger.log(message)
                self.logger_used = True
                
        # Act
        container.register(Logger)
        container.register(Service)
        resolved = container.resolve(Service)
        resolved.use_logger(message="Test message")
        
        # Assert
        assert resolved.logger_used is True
class TestLazyDependencies:
    def test_lazy_dependency_not_resolved_immediately(self):
        # Arrange
        container = Container()
        init_count = 0
        
        class ExpensiveService:
            def __init__(self):
                nonlocal init_count
                init_count += 1
                
        class ServiceWithLazy:
            def __init__(self, lazy_dep: Lazy[ExpensiveService]):
                self.lazy_dep = lazy_dep
                
        # Act
        container.register(ExpensiveService)
        container.register(ServiceWithLazy)
        resolved = container.resolve(ServiceWithLazy)
        
        # Assert
        assert init_count == 0  # Not created yet
        
        # Now resolve the lazy dependency
        actual_dep = resolved.lazy_dep()
        assert isinstance(actual_dep, ExpensiveService)
        assert init_count == 1  # Now it's created

class TestCircularDependencies:
    def test_circular_dependency_detection(self):
        # Arrange
        container = Container()
        
        class ServiceA:
            def __init__(self, b: 'ServiceB'):
                self.b = b
                
        class ServiceB:
            def __init__(self, a: ServiceA):
                self.a = a
                
        # Act & Assert
        container.register(ServiceA)
        container.register(ServiceB)
        
        with pytest.raises((CircularDependencyError, DependencyNotFoundError)) as exc_info:
            container.resolve(ServiceA)
            
        # Verify the error message contains "Circular dependency detected"
        assert "Circular dependency detected" in str(exc_info.value)