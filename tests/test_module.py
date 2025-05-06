import pytest
import asyncio
from typing import List, Optional, Generic, TypeVar
import logging

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test_module")

from retrosys.core.dependency_injection import (
    Container, Module, Lifecycle, injectable, 
    inject_property, inject_method, register_module
)
from retrosys.core.dependency_injection.errors import (
    CircularDependencyError, DependencyNotFoundError
)

class TestModuleBasics:
    def test_module_creation(self):
        # Arrange
        module = Module("test-module")
        
        # Assert
        assert module.name == "test-module"
        assert module._container is not None
        assert module.parent_container is None
    
    def test_module_registration_with_container(self):
        # Arrange
        container = Container()
        module = Module("test-module")
        
        # Act
        container.register_module(module)
        
        # Assert
        assert module.parent_container == container
        assert "test-module" in container._modules
    
    def test_module_with_registered_service(self):
        # Arrange
        container = Container()
        module = Module("services")
        
        class IService:
            def get_value(self) -> str:
                pass
        
        class ServiceImpl(IService):
            def get_value(self) -> str:
                return "module service"
        
        # Act
        logger.debug("Registering IService in module")
        module.register(IService, ServiceImpl)
        logger.debug("Registering module in container")
        container.register_module(module)
        
        # Assert
        logger.debug("Checking if container recognizes service from module")
        descriptor = container._get_descriptor(IService)
        logger.debug(f"Descriptor found: {descriptor is not None}")
        
        logger.debug("Resolving service")
        service = container.resolve(IService)
        logger.debug(f"Service resolved: {service is not None}")
        
        assert isinstance(service, ServiceImpl)
        assert service.get_value() == "module service"
    
    def test_module_instance_registration(self):
        # Arrange
        container = Container()
        module = Module("instances")
        
        class Service:
            def __init__(self, value: str):
                self.value = value
        
        instance = Service("predefined")
        
        # Act
        module.register_instance(Service, instance)
        container.register_module(module)
        
        # Assert
        resolved = container.resolve(Service)
        assert resolved is instance
        assert resolved.value == "predefined"
    
    def test_module_factory_registration(self):
        # Arrange
        container = Container()
        module = Module("factories")
        
        class Service:
            def __init__(self, value: str = "default"):
                self.value = value
        
        # Act
        module.register_factory(Service, lambda c: Service("factory-created"))
        container.register_module(module)
        
        # Assert
        service = container.resolve(Service)
        assert isinstance(service, Service)
        assert service.value == "factory-created"

class TestModuleHierarchy:
    def test_parent_container_resolution(self):
        # Arrange
        container = Container()
        module = Module("child")
        
        class ParentService:
            def get_name(self) -> str:
                return "parent"
        
        # Register in parent container
        container.register(ParentService)
        
        # Act
        container.register_module(module)
        
        # Assert - Module should resolve from parent
        service = module.resolve(ParentService)
        assert service is not None
        assert service.get_name() == "parent"
    
    def test_module_priority_over_parent(self):
        # Arrange
        container = Container()
        module = Module("override")
        
        class Service:
            def __init__(self, name: str):
                self.name = name
            
            def get_name(self) -> str:
                return self.name
        
        # Register in both parent and module
        container.register_instance(Service, Service("parent"))
        module.register_instance(Service, Service("module"))
        
        # Act
        container.register_module(module)
        
        # Assert
        parent_service = container.resolve(Service)
        module_service = module.resolve(Service)
        
        assert parent_service.get_name() == "parent"
        assert module_service.get_name() == "module"
    
    def test_multiple_modules(self):
        # Arrange
        container = Container()
        module1 = Module("module1")
        module2 = Module("module2")
        
        class Service1:
            pass
            
        class Service2:
            pass
        
        # Act
        module1.register(Service1)
        module2.register(Service2)
        container.register_module(module1)
        container.register_module(module2)
        
        # Assert
        service1 = container.resolve(Service1)
        service2 = container.resolve(Service2)
        
        assert isinstance(service1, Service1)
        assert isinstance(service2, Service2)

class TestAsyncModules:
    @pytest.mark.asyncio
    async def test_async_module_resolution(self):
        # Arrange
        container = Container()
        module = Module("async-module")
        
        class AsyncService:
            def __init__(self):
                self.initialized = False
            
            async def initialize(self):
                self.initialized = True
        
        # Act
        module.register(AsyncService, is_async=True)
        container.register_module(module)
        
        # Assert
        service = await container.resolve_async(AsyncService)
        assert service is not None
        assert isinstance(service, AsyncService)
        
        await service.initialize()
        assert service.initialized == True
    
    @pytest.mark.asyncio
    async def test_async_module_with_parent_container(self):
        # Arrange
        container = Container()
        module = Module("child")
        
        class AsyncParentService:
            async def perform(self) -> str:
                return "parent-async"
        
        # Register in parent
        container.register(AsyncParentService, is_async=True)
        container.register_module(module)
        
        # Act & Assert - Module should resolve from parent
        service = await module.resolve_async(AsyncParentService)
        assert service is not None
        result = await service.perform()
        assert result == "parent-async"

class TestModuleDecorator:
    def test_register_module_decorator(self):
        # Arrange
        container = Container()
        
        @register_module(container)
        class ServicesModule:
            @injectable()
            class ConfigService:
                def __init__(self):
                    self.settings = {"app_name": "Test App"}
                
                def get_setting(self, name: str) -> str:
                    return self.settings.get(name, "")
            
            @injectable()
            class LogService:
                def log(self, message: str):
                    pass
        
        # Act & Assert
        config = container.resolve(ServicesModule.ConfigService)
        assert config is not None
        assert config.get_setting("app_name") == "Test App"
        
        log_service = container.resolve(ServicesModule.LogService)
        assert log_service is not None
    
    def test_module_decorator_with_property_injection(self):
        # Arrange
        container = Container()
        
        @injectable()
        class Logger:
            def log(self, message: str):
                return f"LOG: {message}"
        
        # Register Logger at the container level so it can be resolved
        container.register(Logger)
        
        # Create a module with a service that depends on Logger
        @register_module(container)
        class AppModule:
            @injectable()
            class UserService:
                def __init__(self):
                    self._logger = None  # Backing field for the logger property
                
                # This references the Logger class from the outer scope
                @inject_property(Logger)
                def logger(self):
                    pass
                
                def create_user(self, username: str):
                    # Logger should be injected by the DI container
                    return self.logger.log(f"Created user {username}")
        
        # Act - resolve the UserService from the container
        user_service = container.resolve(AppModule.UserService)
        
        # Assert - verify that the property injection worked
        result = user_service.create_user("testuser")
        assert result == "LOG: Created user testuser"