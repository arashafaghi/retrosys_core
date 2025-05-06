# RetroSys Core

A powerful, flexible Python dependency injection framework with support for synchronous and asynchronous services.

## Overview

RetroSys Core provides a modern dependency injection system for Python applications, designed to:

- Simplify application architecture through dependency inversion
- Support both synchronous and asynchronous dependency resolution
- Provide lifecycle management (singleton, transient, and scoped instances)
- Support property and method injection alongside constructor injection
- Enable modular application design
- Facilitate testing through mock capabilities

The framework is designed to be lightweight yet powerful, with a focus on type safety and developer experience.

## Features

- **Multiple Injection Methods**:
  - Constructor injection (using type hints)
  - Property injection (using decorators)
  - Method injection (using decorators)

- **Lifecycle Management**:
  - Singleton: One instance per container
  - Transient: New instance each time it's requested
  - Scoped: One instance per scope (useful for web request contexts)

- **Async Support**:
  - Asynchronous dependency resolution
  - Async factory functions 
  - Async initialization and cleanup

- **Advanced Features**:
  - Contextual binding (register different implementations with context keys)
  - Automatic registration with `@injectable` decorator
  - Circular dependency detection
  - Lazy dependency resolution
  - Module system for organizing registrations
  - Mock capabilities for testing

## Installation

```bash
pip install retrosys-core
```

## Getting Started

### Basic Usage

Here's a simple example that demonstrates the basics of dependency injection:

```python
from retrosys.core.dependency_injection import Container, injectable

# Define service classes with @injectable decorator
@injectable()
class DatabaseService:
    def get_data(self):
        return ["item1", "item2", "item3"]

@injectable()
class UserService:
    def __init__(self, database_service: DatabaseService):
        self.database_service = database_service
        
    def get_user_data(self):
        return self.database_service.get_data()

# Create container and resolve services
container = Container()
user_service = container.resolve(UserService)
data = user_service.get_user_data()
print(data)  # Output: ["item1", "item2", "item3"]
```

### Lifecycle Management

Control how your services are instantiated:

```python
from retrosys.core.dependency_injection import Container, injectable, Lifecycle

@injectable(lifecycle=Lifecycle.SINGLETON)
class ConfigService:
    def __init__(self):
        print("ConfigService initialized")
        self.settings = {"api_url": "https://api.example.com"}

@injectable(lifecycle=Lifecycle.TRANSIENT)
class RequestHandler:
    def __init__(self, config: ConfigService):
        print("RequestHandler initialized")
        self.config = config

# Both handlers share the same ConfigService instance
container = Container()
handler1 = container.resolve(RequestHandler)
handler2 = container.resolve(RequestHandler)

# Output:
# ConfigService initialized
# RequestHandler initialized 
# RequestHandler initialized
```

### Property Injection

Use property injection when constructor injection isn't suitable:

```python
from retrosys.core.dependency_injection import Container, injectable, inject_property

@injectable()
class LogService:
    def log(self, message):
        print(f"LOG: {message}")

@injectable()
class UserController:
    # Property injection with getter/setter
    @inject_property(LogService)
    def logger(self):
        pass
    
    def create_user(self, username):
        # Logger will be automatically resolved when accessed
        self.logger.log(f"Creating user: {username}")
        return {"id": 1, "username": username}

container = Container()
controller = container.resolve(UserController)
controller.create_user("john")  # Output: LOG: Creating user: john
```

### Async Support

Use async for service initialization and resolution:

```python
import asyncio
from retrosys.core.dependency_injection import Container, injectable

@injectable(is_async=True)
class AsyncDatabaseService:
    async def __init__(self):
        # Simulate async initialization
        await asyncio.sleep(0.1)
        self.connection = "db_connection"
        print("Database connected")
        
    async def get_data(self):
        await asyncio.sleep(0.1)  # Simulate database query
        return ["async_item1", "async_item2"]

@injectable(is_async=True)
class AsyncUserService:
    def __init__(self, db: AsyncDatabaseService):
        self.db = db
        
    async def get_users(self):
        return await self.db.get_data()

async def main():
    container = Container()
    # Use resolve_async for async services
    user_service = await container.resolve_async(AsyncUserService)
    users = await user_service.get_users()
    print(users)

asyncio.run(main())
```

### Modules

Organize your registrations using modules:

```python
from retrosys.core.dependency_injection import Container, injectable, register_module

@injectable()
class Service1:
    pass

@injectable()
class Service2:
    pass

# Create a module class to group related services
container = Container()

@register_module(container)
class InfrastructureModule:
    # All injectable classes defined in this module will be registered
    @injectable()
    class DatabaseService:
        def get_connection(self):
            return "database_connection"
    
    @injectable()
    class CacheService:
        def cache(self, key, value):
            print(f"Caching {key}: {value}")

# Now you can resolve services defined in the module
db_service = container.resolve(InfrastructureModule.DatabaseService)
print(db_service.get_connection())  # Output: database_connection
```

### Testing with Mocks

Easily mock dependencies for testing:

```python
from retrosys.core.dependency_injection import Container, injectable
import unittest

@injectable()
class EmailService:
    def send_email(self, to, subject, body):
        # In production, this would send an actual email
        return True

@injectable()
class UserService:
    def __init__(self, email_service: EmailService):
        self.email_service = email_service
    
    def register_user(self, email):
        # Business logic...
        self.email_service.send_email(
            email, 
            "Welcome!", 
            "Thank you for registering."
        )
        return True

class TestUserService(unittest.TestCase):
    def test_register_user(self):
        # Create container in test mode
        container = Container().enable_test_mode()
        
        # Create a mock email service
        class MockEmailService:
            def __init__(self):
                self.emails_sent = []
                
            def send_email(self, to, subject, body):
                self.emails_sent.append((to, subject, body))
                return True
        
        # Register the mock
        mock_email = MockEmailService()
        container.mock(EmailService, mock_email)
        
        # Resolve the service under test with the mock
        user_service = container.resolve(UserService)
        
        # Execute the method being tested
        result = user_service.register_user("user@example.com")
        
        # Assertions
        self.assertTrue(result)
        self.assertEqual(len(mock_email.emails_sent), 1)
        self.assertEqual(mock_email.emails_sent[0][0], "user@example.com")
        
        # Clean up
        container.disable_test_mode()
```

## Advanced Usage

### Factory Registration

Use factory functions for complex initialization:

```python
from retrosys.core.dependency_injection import Container, Lifecycle

# Container instance
container = Container()

# Define a factory function
def create_database_connection(container):
    # Complex initialization logic
    connection_string = "db://example"
    max_connections = 10
    return {"connection": connection_string, "pool_size": max_connections}

# Register the factory
container.register_factory(
    dict,  # Service type
    create_database_connection,  # Factory function
    lifecycle=Lifecycle.SINGLETON,  # Lifecycle
    context_key="db_config"  # Optional context key
)

# Resolve with context key
db_config = container.resolve(dict, context_key="db_config")
print(db_config)  # Output: {'connection': 'db://example', 'pool_size': 10}
```

### Scoped Lifecycle

Manage dependencies for specific operations:

```python
from retrosys.core.dependency_injection import Container, injectable, Lifecycle

@injectable(lifecycle=Lifecycle.SCOPED)
class RequestContext:
    def __init__(self):
        self.user_id = None
        self.request_id = None

@injectable()
class UserRepository:
    def __init__(self, context: RequestContext):
        self.context = context
    
    def get_user_data(self):
        return f"Data for user {self.context.user_id}"

# Create container and scope
container = Container()
scope = container.create_scope()

# Configure scope-specific data
request_context = scope.resolve(RequestContext)
request_context.user_id = "user123"
request_context.request_id = "req456"

# Resolve service within scope
repo = scope.resolve(UserRepository)
print(repo.get_user_data())  # Output: Data for user user123

# Different scope gets different instance
scope2 = container.create_scope()
request_context2 = scope2.resolve(RequestContext)
request_context2.user_id = "user999"
repo2 = scope2.resolve(UserRepository)
print(repo2.get_user_data())  # Output: Data for user user999
```

## API Reference Highlights

### Main Components

- **Container**: The central dependency container
- **Lifecycle**: Enum defining service lifecycles (SINGLETON, TRANSIENT, SCOPED)
- **@injectable**: Decorator for auto-registration of services
- **@inject_property**: Decorator for property injection
- **@inject_method**: Decorator for method injection

### Container Methods

- **register**: Register a service with the container
- **register_instance**: Register an existing instance
- **register_factory**: Register a factory function
- **resolve**: Resolve a service instance
- **resolve_async**: Asynchronously resolve a service
- **create_scope**: Create a dependency scope
- **register_module**: Register a module with the container
- **enable_test_mode / disable_test_mode**: Methods for testing
- **mock**: Register a mock instance for testing

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
