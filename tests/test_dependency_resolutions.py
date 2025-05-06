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
    
    def test_multiple_calls_return_same_instance(self):
        # Arrange
        container = Container()
        
        class SingletonService:
            def __init__(self):
                self.id = id(self)
                
        class ServiceWithLazy:
            def __init__(self, lazy_dep: Lazy[SingletonService]):
                self.lazy_dep = lazy_dep
                
        # Act
        container.register(SingletonService, lifecycle=Lifecycle.SINGLETON)
        container.register(ServiceWithLazy)
        resolved = container.resolve(ServiceWithLazy)
        
        # Assert
        instance1 = resolved.lazy_dep()
        instance2 = resolved.lazy_dep()
        assert instance1 is instance2  # Same instance returned
        assert instance1.id == instance2.id
    
    def test_transient_lazy_dependencies(self):
        # Arrange
        container = Container()
        
        class TransientService:
            def __init__(self):
                self.id = id(self)
                
        class ServiceWithLazy:
            def __init__(self, lazy_dep: Lazy[TransientService]):
                self.lazy_dep = lazy_dep
                
        # Act
        container.register(TransientService, lifecycle=Lifecycle.TRANSIENT)
        container.register(ServiceWithLazy)
        resolved = container.resolve(ServiceWithLazy)
        
        # Assert
        instance1 = resolved.lazy_dep()
        instance2 = resolved.lazy_dep()
        assert instance1 is instance2  # Still same instance from Lazy wrapper
        
        # But different from directly resolved instances
        direct1 = container.resolve(TransientService)
        direct2 = container.resolve(TransientService)
        assert direct1 is not direct2
        assert direct1 is not instance1
    
    @pytest.mark.asyncio
    async def test_lazy_async_dependency(self):
        # Arrange
        container = Container()
        init_count = 0
        
        class AsyncService:
            def __init__(self):
                nonlocal init_count
                init_count += 1
                
            async def initialize(self):
                return "initialized"
                
        class ServiceWithLazy:
            def __init__(self, lazy_dep: Lazy[AsyncService]):
                self.lazy_dep = lazy_dep
                
        # Act
        container.register(AsyncService, is_async=True)
        container.register(ServiceWithLazy)
        resolved = container.resolve(ServiceWithLazy)
        
        # Assert
        assert init_count == 0  # Not created yet
        
        # Now resolve the lazy dependency asynchronously
        lazy_service = await resolved.lazy_dep.async_resolve()
        assert isinstance(lazy_service, AsyncService)
        assert init_count == 1
        
        # Ensure we can use the async service
        result = await lazy_service.initialize()
        assert result == "initialized"
    
    def test_lazy_dependency_chain(self):
        # Arrange
        container = Container()
        init_counts = {"A": 0, "B": 0, "C": 0}
        
        class ServiceC:
            def __init__(self):
                init_counts["C"] += 1
                
        class ServiceB:
            def __init__(self, lazy_c: Lazy[ServiceC]):
                init_counts["B"] += 1
                self.lazy_c = lazy_c
                
        class ServiceA:
            def __init__(self, lazy_b: Lazy[ServiceB]):
                init_counts["A"] += 1
                self.lazy_b = lazy_b
                
        # Act
        container.register(ServiceC)
        container.register(ServiceB)
        container.register(ServiceA)
        resolved = container.resolve(ServiceA)
        
        # Assert
        assert init_counts == {"A": 1, "B": 0, "C": 0}  # Only A is created
        
        # Resolve B
        service_b = resolved.lazy_b()
        assert init_counts == {"A": 1, "B": 1, "C": 0}  # Now B is created
        
        # Resolve C
        service_c = service_b.lazy_c()
        assert init_counts == {"A": 1, "B": 1, "C": 1}  # Finally C is created
        assert isinstance(service_c, ServiceC)
        
    def test_lazy_with_interface(self):
        # Arrange
        container = Container()
        
        class IService:
            def do_work(self) -> str:
                pass
        
        class ServiceImpl(IService):
            def do_work(self) -> str:
                return "work done"
        
        class Client:
            def __init__(self, lazy_service: Lazy[IService]):
                self.lazy_service = lazy_service
            
            def perform_task(self) -> str:
                service = self.lazy_service()
                return service.do_work()
        
        # Act
        container.register(IService, ServiceImpl)
        container.register(Client)
        client = container.resolve(Client)
        
        # Assert
        result = client.perform_task()
        assert result == "work done"

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