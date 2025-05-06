import pytest
import asyncio
import logging
from retrosys.core.dependency_injection import Container, Lifecycle, Scope
from retrosys.core.dependency_injection.service_descriptor import ServiceDescriptor

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestScopeAsync:
    @pytest.mark.asyncio
    async def test_resolve_async(self):
        """Test asynchronous resolution of services within a scope."""
        # Arrange
        container = Container()
        
        class AsyncService:
            def __init__(self):
                self.id = id(self)
                self.initialized = False
            
            async def initialize(self):
                await asyncio.sleep(0.01)  # Simulate async initialization
                self.initialized = True
                return self
        
        # Register with async factory
        container.register(
            AsyncService, 
            lifecycle=Lifecycle.SCOPED,
            factory=lambda c: AsyncService().initialize(),
            is_async=True  # Indicate this factory returns a coroutine that needs to be awaited
        )
        
        # Act
        scope = container.create_scope()
        instance1 = await scope.resolve_async(AsyncService)
        instance2 = await scope.resolve_async(AsyncService)
        
        # Assert
        assert instance1 is instance2, "Expected same instance within scope"
        assert instance1.initialized, "Expected instance to be initialized"
        
        # Create new scope
        scope2 = container.create_scope()
        instance3 = await scope2.resolve_async(AsyncService)
        
        # Assert different instances between scopes
        assert instance1 is not instance3, "Expected different instances between scopes"
        assert instance3.initialized, "Expected instance to be initialized"

    @pytest.mark.asyncio
    async def test_on_destroy_callback(self):
        """Test the on_destroy callback functionality for scoped services."""
        # Arrange
        container = Container()
        destroy_called = False
        
        class DisposableService:
            def __init__(self):
                self.id = id(self)
        
        async def on_destroy(instance):
            nonlocal destroy_called
            destroy_called = True
            await asyncio.sleep(0.01)  # Simulate async cleanup
        
        # Register with on_destroy callback
        container.register(
            DisposableService, 
            lifecycle=Lifecycle.SCOPED,
            on_destroy=on_destroy
        )
        
        # Act
        scope = container.create_scope()
        service = scope.resolve(DisposableService)
        
        # Assert before disposal
        assert not destroy_called, "on_destroy should not be called yet"
        
        # Dispose the scope
        await scope.dispose()
        
        # Assert after disposal
        assert destroy_called, "on_destroy should have been called"

    @pytest.mark.asyncio
    async def test_sync_on_destroy_callback(self):
        """Test synchronous on_destroy callback for scoped services."""
        # Arrange
        container = Container()
        destroy_called = False
        
        class DisposableService:
            def __init__(self):
                self.id = id(self)
        
        def sync_on_destroy(instance):
            nonlocal destroy_called
            destroy_called = True
        
        # Register with synchronous on_destroy callback
        container.register(
            DisposableService, 
            lifecycle=Lifecycle.SCOPED,
            on_destroy=sync_on_destroy
        )
        
        # Act
        scope = container.create_scope()
        service = scope.resolve(DisposableService)
        await scope.dispose()
        
        # Assert
        assert destroy_called, "Synchronous on_destroy should have been called"

    @pytest.mark.asyncio
    async def test_error_handling_during_disposal(self):
        """Test error handling during disposal of scoped services."""
        # Arrange
        container = Container()
        second_dispose_called = False
        
        class ErrorService:
            def __init__(self):
                self.id = id(self)
            
            async def dispose(self):
                raise ValueError("Simulated error during disposal")
        
        class SecondService:
            def __init__(self):
                self.id = id(self)
            
            async def dispose(self):
                nonlocal second_dispose_called
                second_dispose_called = True
        
        # Register services
        container.register(ErrorService, lifecycle=Lifecycle.SCOPED)
        container.register(SecondService, lifecycle=Lifecycle.SCOPED)
        
        # Act
        scope = container.create_scope()
        error_service = scope.resolve(ErrorService)
        second_service = scope.resolve(SecondService)
        
        # Should not raise exception and should continue disposing other services
        await scope.dispose()
        
        # Assert
        assert second_dispose_called, "Second service should still be disposed despite error in first service"

    @pytest.mark.asyncio
    async def test_mixed_sync_async_disposal(self):
        """Test both synchronous and asynchronous dispose methods in the same scope."""
        # Arrange
        container = Container()
        sync_disposed = False
        async_disposed = False
        
        class SyncDisposable:
            def __init__(self):
                self.id = id(self)
            
            def dispose(self):
                nonlocal sync_disposed
                sync_disposed = True
        
        class AsyncDisposable:
            def __init__(self):
                self.id = id(self)
            
            async def dispose(self):
                await asyncio.sleep(0.01)  # Simulate async cleanup
                nonlocal async_disposed
                async_disposed = True
        
        # Register services
        container.register(SyncDisposable, lifecycle=Lifecycle.SCOPED)
        container.register(AsyncDisposable, lifecycle=Lifecycle.SCOPED)
        
        # Act
        scope = container.create_scope()
        sync_service = scope.resolve(SyncDisposable)
        async_service = scope.resolve(AsyncDisposable)
        
        await scope.dispose()
        
        # Assert
        assert sync_disposed, "Sync service should be disposed"
        assert async_disposed, "Async service should be disposed"

    @pytest.mark.asyncio
    async def test_error_in_on_destroy_callback(self):
        """Test error handling in on_destroy callbacks."""
        # Arrange
        container = Container()
        second_callback_called = False
        
        class Service1:
            def __init__(self):
                self.id = id(self)
        
        class Service2:
            def __init__(self):
                self.id = id(self)
        
        def error_callback(instance):
            raise ValueError("Simulated error in on_destroy callback")
        
        def second_callback(instance):
            nonlocal second_callback_called
            second_callback_called = True
        
        # Register services
        container.register(
            Service1, 
            lifecycle=Lifecycle.SCOPED,
            on_destroy=error_callback
        )
        
        container.register(
            Service2, 
            lifecycle=Lifecycle.SCOPED,
            on_destroy=second_callback
        )
        
        # Act
        scope = container.create_scope()
        service1 = scope.resolve(Service1)
        service2 = scope.resolve(Service2)
        
        # Should not raise exception
        await scope.dispose()
        
        # Assert
        assert second_callback_called, "Second callback should still be called despite error in first callback"

    @pytest.mark.asyncio
    async def test_multiple_scopes_with_shared_singletons(self):
        """Test interaction between multiple scopes with shared singleton services."""
        # Arrange
        container = Container()
        
        class SingletonService:
            def __init__(self):
                self.id = id(self)
                self.counter = 0
            
            def increment(self):
                self.counter += 1
                return self.counter
        
        class ScopedServiceWithDependency:
            def __init__(self, singleton: SingletonService):
                self.id = id(self)
                self.singleton = singleton
        
        # Register services
        container.register(SingletonService, lifecycle=Lifecycle.SINGLETON)
        container.register(ScopedServiceWithDependency, lifecycle=Lifecycle.SCOPED)
        
        # Act - Create multiple scopes
        scope1 = container.create_scope()
        scope2 = container.create_scope()
        
        # Get services from different scopes
        scoped1 = scope1.resolve(ScopedServiceWithDependency)
        scoped2 = scope2.resolve(ScopedServiceWithDependency)
        
        # Increment counter via each scoped service
        count1 = scoped1.singleton.increment()
        count2 = scoped2.singleton.increment()
        
        # Assert
        assert scoped1 is not scoped2, "Scoped services should be different across scopes"
        assert scoped1.singleton is scoped2.singleton, "Singleton dependency should be shared"
        assert count1 == 1, "First increment should return 1"
        assert count2 == 2, "Second increment should return 2 (shared state)"