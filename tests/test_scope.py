import pytest
import logging
from retrosys.core.dependency_injection import Container, Lifecycle, Scope

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestScope:
    def test_scoped_instance_caching(self):
        # Arrange
        container = Container()
        
        class Service:
            def __init__(self):
                self.id = id(self)
                
        # Register with scoped lifecycle
        container.register(Service, lifecycle=Lifecycle.SCOPED)
        
        # Act
        scope = container.create_scope()
        instance1 = scope.resolve(Service)
        instance2 = scope.resolve(Service)
        
        # Assert
        assert instance1 is instance2, "Expected same instance within scope"
        
        # Create new scope
        scope2 = container.create_scope()
        instance3 = scope2.resolve(Service)
        
        # Assert different instances between scopes
        assert instance1 is not instance3, "Expected different instances between scopes"
        
    def test_scoped_vs_singleton_lifecycle(self):
        # Arrange
        container = Container()
        
        class SingletonService:
            def __init__(self):
                self.id = id(self)
                
        class ScopedService:
            def __init__(self):
                self.id = id(self)
        
        # Register services
        container.register(SingletonService, lifecycle=Lifecycle.SINGLETON)
        container.register(ScopedService, lifecycle=Lifecycle.SCOPED)
        
        # Act & Assert
        scope1 = container.create_scope()
        scope2 = container.create_scope()
        
        # Singleton should be the same across scopes
        singleton1 = scope1.resolve(SingletonService)
        singleton2 = scope2.resolve(SingletonService)
        assert singleton1 is singleton2
        
        # Scoped should be different per scope
        scoped1 = scope1.resolve(ScopedService)
        scoped2 = scope2.resolve(ScopedService)
        assert scoped1 is not scoped2
        
    @pytest.mark.asyncio
    async def test_async_scope_context_manager(self):
        # Arrange
        container = Container()
        disposed = False
        
        class DisposableService:
            def __init__(self):
                self.disposed = False
                
            async def dispose(self):
                self.disposed = True
                nonlocal disposed
                disposed = True
        
        container.register(DisposableService, lifecycle=Lifecycle.SCOPED)
        
        # Act
        async with container.create_scope() as scope:
            service = scope.resolve(DisposableService)
            assert not service.disposed, "Service should not be disposed yet"
            
        # Assert
        assert disposed, "Dispose method should have been called"
        assert service.disposed, "Service should be disposed"
        
    @pytest.mark.asyncio
    async def test_scope_disposal(self):
        # Arrange
        container = Container()
        dispose_count = 0
        
        class DisposableService:
            def __init__(self):
                self.disposed = False
                
            async def dispose(self):
                self.disposed = True
                nonlocal dispose_count
                dispose_count += 1
        
        container.register(DisposableService, lifecycle=Lifecycle.SCOPED)
        
        # Act
        scope = container.create_scope()
        service1 = scope.resolve(DisposableService)
        service2 = scope.resolve(DisposableService)  # Same instance
        
        await scope.dispose()
        
        # Assert
        assert dispose_count == 1, "Should only dispose once for the single instance"
        assert service1.disposed, "First service instance should be disposed"
        assert service2.disposed, "Second service instance should be disposed (same instance)"