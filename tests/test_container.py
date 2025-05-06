import pytest
import asyncio
import inspect
from typing import List, Dict, Optional, Any, Awaitable, Union, Generic, TypeVar

from retrosys.core.dependency_injection import Container, Lifecycle, ResolutionStrategy
from retrosys.core.dependency_injection.errors import (
    CircularDependencyError,
    DependencyNotFoundError,
    AsyncInitializationError,
)
from retrosys.core.dependency_injection.lazy import Lazy
from retrosys.core.dependency_injection.module import Module

# Helper for testing forward references
T = TypeVar('T')


class TestContainer:
    """Test suite for the Container class."""
    
    def test_basic_registration_and_resolution(self):
        """Test basic registration and resolution of services."""
        # Arrange
        container = Container()
        
        class Service:
            def __init__(self):
                self.value = "test"
        
        # Act
        container.register(Service)
        instance = container.resolve(Service)
        
        # Assert
        assert isinstance(instance, Service)
        assert instance.value == "test"
        
        # Resolve again to test singleton behavior
        instance2 = container.resolve(Service)
        assert instance is instance2, "Expected same instance for singleton"
    
    def test_transient_lifecycle(self):
        """Test registration with TRANSIENT lifecycle."""
        # Arrange
        container = Container()
        
        class Service:
            def __init__(self):
                self.id = id(self)
        
        # Act
        container.register(Service, lifecycle=Lifecycle.TRANSIENT)
        instance1 = container.resolve(Service)
        instance2 = container.resolve(Service)
        
        # Assert
        assert isinstance(instance1, Service)
        assert isinstance(instance2, Service)
        assert instance1 is not instance2, "Expected different instances for transient"
        assert instance1.id != instance2.id
    
    def test_factory_registration(self):
        """Test registration with factory function."""
        # Arrange
        container = Container()
        factory_called = False
        
        class Service:
            def __init__(self, value):
                self.value = value
        
        def factory(c):
            nonlocal factory_called
            factory_called = True
            return Service("factory_value")
        
        # Act
        container.register(Service, factory=factory)
        instance = container.resolve(Service)
        
        # Assert
        assert factory_called, "Factory should have been called"
        assert instance.value == "factory_value"
    
    def test_register_factory_method(self):
        """Test the register_factory method."""
        # Arrange
        container = Container()
        
        class Service:
            def __init__(self, value):
                self.value = value
        
        # Act
        container.register_factory(Service, lambda c: Service("factory_value"))
        instance = container.resolve(Service)
        
        # Assert
        assert instance.value == "factory_value"
        
        # Test with async factory
        async def async_factory(c):
            return Service("async_value")
        
        container.register_factory(Service, async_factory, context_key="async")
        
        # Verify the registration worked but we need resolve_async to get the instance
        with pytest.raises(AsyncInitializationError):
            container.resolve(Service, "async")
    
    def test_register_instance(self):
        """Test registering an existing instance."""
        # Arrange
        container = Container()
        
        class Service:
            def __init__(self, value):
                self.value = value
        
        existing = Service("existing")
        
        # Act
        container.register_instance(Service, existing)
        resolved = container.resolve(Service)
        
        # Assert
        assert resolved is existing, "Expected the same instance object"
        assert resolved.value == "existing"
    
    def test_context_key(self):
        """Test registration with context keys."""
        # Arrange
        container = Container()
        
        class Service:
            def __init__(self, value=None):
                self.value = value or "default"
        
        # Act - Register two implementations with different context keys
        container.register(Service)  # default
        container.register(
            Service, 
            factory=lambda c: Service("context1"),
            context_key="context1"
        )
        container.register(
            Service, 
            factory=lambda c: Service("context2"),
            context_key="context2"
        )
        
        # Resolve with different contexts
        default = container.resolve(Service)
        context1 = container.resolve(Service, "context1")
        context2 = container.resolve(Service, "context2")
        
        # Assert
        assert default.value == "default"
        assert context1.value == "context1"
        assert context2.value == "context2"
    
    def test_constructor_injection(self):
        """Test constructor dependency injection."""
        # Arrange
        container = Container()
        
        class Dependency:
            def __init__(self):
                self.value = "dependency"
        
        class Service:
            def __init__(self, dependency: Dependency):
                self.dependency = dependency
        
        # Act
        container.register(Dependency)
        container.register(Service)
        instance = container.resolve(Service)
        
        # Assert
        assert isinstance(instance.dependency, Dependency)
        assert instance.dependency.value == "dependency"
    
    @pytest.mark.asyncio
    async def test_async_factory(self):
        """Test async factory functions."""
        # Arrange
        container = Container()
        
        class AsyncService:
            def __init__(self, value=None):
                self.value = value
        
        async def async_factory(c):
            await asyncio.sleep(0.01)  # Simulate async work
            return AsyncService("async_value")
        
        # Act
        container.register(AsyncService, factory=async_factory, is_async=True)
        instance = await container.resolve_async(AsyncService)
        
        # Assert
        assert instance.value == "async_value"
        
        # Create a new container for testing the error case
        error_container = Container()
        error_container.register(AsyncService, factory=async_factory, is_async=True)
        
        # Should raise error if using synchronous resolve
        with pytest.raises(AsyncInitializationError):
            error_container.resolve(AsyncService)
        
    @pytest.mark.asyncio
    async def test_async_initialization(self):
        """Test async initialization after instance creation."""
        # Arrange
        container = Container()
        init_called = False
        
        class Service:
            def __init__(self):
                self.initialized = False
        
        async def on_init(instance):
            nonlocal init_called
            init_called = True
            await asyncio.sleep(0.01)  # Simulate async work
            instance.initialized = True
        
        # Act
        container.register(Service, on_init=on_init, is_async=True)
        instance = await container.resolve_async(Service)
        
        # Assert
        assert init_called, "on_init should have been called"
        assert instance.initialized, "Instance should be initialized"
    
    def test_lazy_dependency(self):
        """Test lazy dependency resolution."""
        # Arrange
        container = Container()
        resolve_called = False
        
        class LazyDependency:
            def __init__(self):
                nonlocal resolve_called
                resolve_called = True
                self.value = "lazy"
        
        class ServiceWithLazy:
            def __init__(self, lazy_dep: Lazy[LazyDependency]):
                self.lazy_dep = lazy_dep
                
        
        # Act
        container.register(LazyDependency)
        container.register(ServiceWithLazy)
        service = container.resolve(ServiceWithLazy)
        
        # Assert - Lazy dependency should not be resolved yet
        assert not resolve_called, "Lazy dependency should not be resolved during construction"
        assert isinstance(service.lazy_dep, Lazy)
        
        # Now access the value and trigger resolution
        dep = service.lazy_dep()
        assert resolve_called, "Lazy dependency should be resolved when accessed"
        assert dep.value == "lazy"
    
    def test_circular_dependency_detection(self):
        """Test circular dependency detection."""
        # Arrange
        container = Container()
        
        class ServiceA:
            def __init__(self, b: 'ServiceB'):
                self.b = b
        
        class ServiceB:
            def __init__(self, a: ServiceA):
                self.a = a
        
        # Act
        container.register(ServiceA)
        container.register(ServiceB)
        
        # Assert - accept either CircularDependencyError or DependencyNotFoundError
        # that contains a CircularDependencyError
        with pytest.raises((CircularDependencyError, DependencyNotFoundError)) as excinfo:
            container.resolve(ServiceA)
        
        # Check that the error message contains the expected circular dependency path
        assert "Circular dependency detected" in str(excinfo.value)
        assert "ServiceA -> ServiceB -> ServiceA" in str(excinfo.value)
    
    def test_lifecycle_behaviors(self):
        """Test different lifecycle behaviors."""
        # Arrange
        container = Container()
        
        class SingletonService:
            def __init__(self):
                self.id = id(self)
        
        class ScopedService:
            def __init__(self):
                self.id = id(self)
        
        class TransientService:
            def __init__(self):
                self.id = id(self)
        
        # Act
        container.register(SingletonService, lifecycle=Lifecycle.SINGLETON)
        container.register(ScopedService, lifecycle=Lifecycle.SCOPED)
        container.register(TransientService, lifecycle=Lifecycle.TRANSIENT)
        
        # Test singleton behavior
        singleton1 = container.resolve(SingletonService)
        singleton2 = container.resolve(SingletonService)
        assert singleton1 is singleton2, "Expected same instance for singleton"
        
        # Test scoped behavior
        scope1 = container.create_scope()
        scope2 = container.create_scope()
        
        scoped1_1 = scope1.resolve(ScopedService)
        scoped1_2 = scope1.resolve(ScopedService)
        scoped2 = scope2.resolve(ScopedService)
        
        assert scoped1_1 is scoped1_2, "Expected same instance within scope"
        assert scoped1_1 is not scoped2, "Expected different instances between scopes"
        
        # Test transient behavior
        transient1 = container.resolve(TransientService)
        transient2 = container.resolve(TransientService)
        
        assert transient1 is not transient2, "Expected different instances for transient"
    
    def test_on_init_callback(self):
        """Test the on_init callback functionality."""
        # Arrange
        container = Container()
        init_called = False
        
        class Service:
            def __init__(self):
                self.initialized = False
        
        def on_init(instance):
            nonlocal init_called
            init_called = True
            instance.initialized = True
        
        # Act
        container.register(Service, on_init=on_init)
        instance = container.resolve(Service)
        
        # Assert
        assert init_called, "on_init should have been called"
        assert instance.initialized, "Instance should be initialized"
    
    @pytest.mark.asyncio
    async def test_dispose(self):
        """Test the container's dispose method."""
        # Arrange
        container = Container()
        dispose_called = False
        async_dispose_called = False
        
        class Service1:
            def __init__(self):
                pass
        
        class Service2:
            def __init__(self):
                pass
        
        def on_destroy(instance):
            nonlocal dispose_called
            dispose_called = True
        
        async def async_on_destroy(instance):
            nonlocal async_dispose_called
            await asyncio.sleep(0.01)  # Simulate async disposal
            async_dispose_called = True
        
        # Act
        container.register(Service1, on_destroy=on_destroy)
        container.register(Service2, on_destroy=async_on_destroy, is_async=True)
        
        # Resolve to create instances
        container.resolve(Service1)
        await container.resolve_async(Service2)
        
        # Dispose
        await container.dispose()
        
        # Assert
        assert dispose_called, "Synchronous on_destroy should have been called"
        assert async_dispose_called, "Asynchronous on_destroy should have been called"
    
    def test_test_mode_and_mocking(self):
        """Test the test mode and mocking functionality."""
        # Arrange
        container = Container()
        
        class Service:
            def __init__(self):
                self.value = "original"
        
        class MockService:
            def __init__(self):
                self.value = "mock"
        
        # Act - Register real service
        container.register(Service)
        
        # Enable test mode and register mock
        container.enable_test_mode()
        mock = MockService()
        container.mock(Service, mock)
        
        # Resolve in test mode
        test_instance = container.resolve(Service)
        
        # Disable test mode
        container.disable_test_mode()
        normal_instance = container.resolve(Service)
        
        # Assert
        assert test_instance is mock, "Expected mock instance in test mode"
        assert test_instance.value == "mock"
        assert normal_instance.value == "original"
        assert not container._test_mode, "Test mode should be disabled"
        assert not container._mock_instances, "Mock instances should be cleared"
    
    def test_forward_references(self):
        """Test resolution of forward references in string annotations."""
        # Arrange
        container = Container()
        
        class ServiceA:
            def __init__(self):
                self.value = "A"
        
        class ServiceB:
            def __init__(self, a: 'ServiceA'):
                self.a = a
        
        # Act
        container.register(ServiceA)
        container.register(ServiceB)
        instance = container.resolve(ServiceB)
        
        # Assert
        assert isinstance(instance.a, ServiceA)
        assert instance.a.value == "A"
    
    def test_primitive_type_error(self):
        """Test error handling for primitive types."""
        # Arrange
        container = Container()
        
        class ServiceWithPrimitive:
            def __init__(self, name: str):
                self.name = name
        
        # Act
        container.register(ServiceWithPrimitive)
        
        # Assert
        with pytest.raises(DependencyNotFoundError) as excinfo:
            container.resolve(ServiceWithPrimitive)
        
        assert "Cannot automatically resolve primitive type" in str(excinfo.value)
        assert "Consider using a factory" in str(excinfo.value)
    
    def test_missing_dependency_error(self):
        """Test error handling for missing dependencies."""
        # Arrange
        container = Container()
        
        class Dependency:
            pass
        
        class Service:
            def __init__(self, dep: Dependency):
                self.dep = dep
        
        # Act
        container.register(Service)
        
        # Assert
        with pytest.raises(DependencyNotFoundError) as excinfo:
            container.resolve(Service)
        
        assert "No registration found for Dependency" in str(excinfo.value)
    
    def test_child_container(self):
        """Test creating and using a child container."""
        # Arrange
        parent = Container()
        
        class ParentService:
            def __init__(self):
                self.value = "parent"
        
        class ChildService:
            def __init__(self):
                self.value = "child"
        
        # Register in parent
        parent.register(ParentService)
        
        # Create child and register in child
        child = parent.create_child_container()
        child.register(ChildService)
        
        # Act - Resolve from both containers
        parent_from_parent = parent.resolve(ParentService)
        parent_from_child = child.resolve(ParentService)
        child_from_child = child.resolve(ChildService)
        
        # Assert
        assert parent_from_parent.value == "parent"
        assert parent_from_child.value == "parent"
        assert parent_from_parent is parent_from_child, "Expected same instance from parent"
        assert child_from_child.value == "child"
        
        # Parent shouldn't have child's registrations
        with pytest.raises(DependencyNotFoundError):
            parent.resolve(ChildService)
    
    def test_module_integration(self):
        """Test integration with modules."""
        # Arrange
        container = Container()
        
        class ModuleService:
            def __init__(self):
                self.value = "module"
        
        # Create a module
        module = Module("test_module")
        module.register(ModuleService)
        
        # Act - Register module with container
        container.register_module(module)
        
        # Resolve service from container
        service = container.resolve(ModuleService)
        
        # Assert
        assert service.value == "module"
        assert "test_module" in container._modules
        assert module.parent_container is container
    
    def test_module_with_namespace(self):
        """Test registering a module with a custom namespace."""
        # Arrange
        container = Container()
        
        class ModuleService:
            def __init__(self):
                self.value = "module"
        
        # Create a module with its own name
        module = Module("original_name")
        module.register(ModuleService)
        
        # Act - Register module with custom namespace
        container.register_module(module, namespace="custom_namespace")
        
        # Assert
        assert "custom_namespace" in container._modules
        assert "original_name" not in container._modules
        
        # Service should still be resolvable
        service = container.resolve(ModuleService)
        assert service.value == "module"
    
    def test_module_namespace_warning(self):
        """Test warning when registering a module with a duplicate namespace."""
        # Arrange
        container = Container()
        
        module1 = Module("test_namespace")
        module2 = Module("different_name")
        
        # Act & Assert - Register modules with same namespace
        container.register_module(module1)
        
        with pytest.warns(UserWarning, match="Module namespace 'test_namespace' is already registered"):
            container.register_module(module2, namespace="test_namespace")
    
    @pytest.mark.asyncio
    async def test_async_dependency_chain(self):
        """Test a chain of async dependencies."""
        # Arrange
        container = Container()
        
        class AsyncBase:
            def __init__(self):
                self.value = "base"
                self.initialized = False
            
            async def initialize(self):
                await asyncio.sleep(0.01)
                self.initialized = True
                return self
        
        class AsyncMiddle:
            def __init__(self, base: AsyncBase):
                self.base = base
                self.value = "middle"
                self.initialized = False
            
            async def initialize(self):
                await asyncio.sleep(0.01)
                self.initialized = True
                return self
        
        class AsyncTop:
            def __init__(self, middle: AsyncMiddle):
                self.middle = middle
                self.value = "top"
                self.initialized = False
            
            async def initialize(self):
                await asyncio.sleep(0.01)
                self.initialized = True
                return self
        
        # Register with async factories that properly await the coroutines
        container.register(
            AsyncBase,
            factory=lambda c: AsyncBase().initialize(),
            is_async=True
        )
        
        async def middle_factory(c):
            base = await c.resolve_async(AsyncBase)  # Await here
            return await AsyncMiddle(base).initialize()
        
        container.register(
            AsyncMiddle,
            factory=middle_factory,
            is_async=True
        )
        
        async def top_factory(c):
            middle = await c.resolve_async(AsyncMiddle)  # Await here
            return await AsyncTop(middle).initialize()
        
        container.register(
            AsyncTop,
            factory=top_factory,
            is_async=True
        )
        
        # Act
        top = await container.resolve_async(AsyncTop)
        
        # Assert
        assert top.initialized
        assert top.middle.initialized
        assert top.middle.base.initialized
        assert top.value == "top"
        assert top.middle.value == "middle"
        assert top.middle.base.value == "base"

    @pytest.mark.asyncio
    async def test_create_instance_async_method(self):
        """Test the _create_instance_async private method."""
        # This test deliberately accesses a private method for testing
        # Arrange
        container = Container()
        
        class AsyncDependency:
            def __init__(self):
                self.value = "async_dep"
                self.initialized = False
            
            async def initialize(self):
                await asyncio.sleep(0.01)
                self.initialized = True
                return self
        
        class Service:
            def __init__(self, dep: AsyncDependency):
                self.dep = dep
        
        # Register dependency as async
        container.register(
            AsyncDependency,
            factory=lambda c: AsyncDependency().initialize(),
            is_async=True
        )
        
        # Register service normally
        container.register(Service)
        
        # Act - Use the private method directly
        instance = await container._create_instance_async(Service)
        
        # Assert
        assert isinstance(instance, Service)
        assert instance.dep.initialized
        assert instance.dep.value == "async_dep"
    
    def test_default_parameters(self):
        """Test handling of default parameters in constructors."""
        # Arrange
        container = Container()
        
        class ServiceWithDefaults:
            def __init__(self, name: str = "default", count: int = 0):
                self.name = name
                self.count = count
        
        # Act
        container.register(ServiceWithDefaults)
        instance = container.resolve(ServiceWithDefaults)
        
        # Assert
        assert instance.name == "default"
        assert instance.count == 0
    
    def test_resolution_strategy(self):
        """Test different resolution strategies."""
        # Arrange
        container = Container()
        
        class EagerService:
            def __init__(self):
                self.value = "eager"
        
        class LazyService:
            def __init__(self):
                self.value = "lazy"
        
        # Act
        container.register(
            EagerService,
            resolution_strategy=ResolutionStrategy.EAGER
        )
        
        container.register(
            LazyService,
            resolution_strategy=ResolutionStrategy.LAZY
        )
        
        # Resolve
        eager = container.resolve(EagerService)
        lazy = container.resolve(LazyService)
        
        # Assert
        assert eager.value == "eager"
        assert lazy.value == "lazy"