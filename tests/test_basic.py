from retrosys.core.dependency_injection import (
    Container, Lifecycle
)

class TestBasicRegistration:
    def test_register_interface_implementation(self):
        # Arrange
        container = Container()
        
        class IService:
            def method(self) -> str:
                pass
                
        class ServiceImpl(IService):
            def method(self) -> str:
                return "result"
                
        # Act
        container.register(IService, ServiceImpl)
        resolved = container.resolve(IService)
        
        # Assert
        assert isinstance(resolved, ServiceImpl)
        assert resolved.method() == "result"
    
    def test_register_concrete_class(self):
        # Arrange
        container = Container()
        
        class Service:
            def __init__(self, value: str = "default"):
                self.value = value
                
        # Act
        container.register(Service)
        resolved = container.resolve(Service)
        
        # Assert
        assert isinstance(resolved, Service)
        assert resolved.value == "default"
    
    def test_register_with_factory(self):
        # Arrange
        container = Container()
        
        class Service:
            def __init__(self, value: str):
                self.value = value
                
        # Act
        container.register_factory(Service, lambda c: Service("factory-created"))
        resolved = container.resolve(Service)
        
        # Assert
        assert isinstance(resolved, Service)
        assert resolved.value == "factory-created"
        
    def test_register_instance(self):
        # Arrange
        container = Container()
        
        class Service:
            def __init__(self, value: str):
                self.value = value
                
        instance = Service("pre-created")
                
        # Act
        container.register_instance(Service, instance)
        resolved = container.resolve(Service)
        
        # Assert
        assert resolved is instance  # Same instance
        assert resolved.value == "pre-created"

class TestLifecycleManagement:
    def test_singleton_lifecycle(self):
        # Arrange
        container = Container()
        
        class Service:
            def __init__(self):
                self.id = id(self)
                
        # Act
        container.register(Service, lifecycle=Lifecycle.SINGLETON)
        instance1 = container.resolve(Service)
        instance2 = container.resolve(Service)
        
        # Assert
        assert instance1 is instance2  # Same instance
        assert instance1.id == instance2.id
        
    def test_transient_lifecycle(self):
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
        assert instance1 is not instance2  # Different instances
        assert instance1.id != instance2.id

class TestConstructorInjection:
    def test_simple_dependency_injection(self):
        # Arrange
        container = Container()
        
        class Logger:
            def log(self, message: str) -> None:
                pass
                
        class Service:
            def __init__(self, logger: Logger):
                self.logger = logger
                
        # Act
        container.register(Logger)
        container.register(Service)
        resolved = container.resolve(Service)
        
        # Assert
        assert isinstance(resolved, Service)
        assert isinstance(resolved.logger, Logger)