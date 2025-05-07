Examples
========

This section provides examples of how to use the RetroSys Core dependency injection system.

Basic Usage
----------

Here's a simple example that demonstrates the basics of dependency injection:

.. code-block:: python

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

Lifecycle Management
-------------------

Control how your services are instantiated:

.. code-block:: python

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

Property Injection
-----------------

Use property injection when constructor injection isn't suitable:

.. code-block:: python

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

Async Support
------------

Use async for service initialization and resolution:

.. code-block:: python

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

Modules
-------

Organize your registrations using modules:

.. code-block:: python

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

Testing with Mocks
-----------------

Easily mock dependencies for testing:

.. code-block:: python

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

Advanced Usage: Factory Registration
------------------------------------

Use factory functions for complex initialization:

.. code-block:: python

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

Advanced Usage: Scoped Lifecycle
--------------------------------

Manage dependencies for specific operations:

.. code-block:: python

    from retrosys.core.dependency_injection import Container, injectable, Lifecycle

    @injectable(lifecycle=Lifecycle.SCOPED)
    class RequestContext:
        def __init__(self):
            self.user_id = None
            self.request_id = None

    @injectable(lifecycle=Lifecycle.SCOPED)
    class UserRepository:
        def __init__(self, context: RequestContext):
            self.context = context
            print(f"UserRepository created with context: {id(context)}")

        def get_user_data(self):
            return f"Data for user {self.context.user_id}"


    # Create container
    container = Container()
    
    # First scope
    scope1 = container.create_scope()
    context1 = scope1.resolve(RequestContext)
    print(f"Context1 ID: {id(context1)}")
    context1.user_id = "user123"
    
    # Resolve repository in the same scope
    repo1 = scope1.resolve(UserRepository)
    print(f"Repo1 using context ID: {id(repo1.context)}")
    print(repo1.get_user_data())
    
    # Second scope
    scope2 = container.create_scope()
    context2 = scope2.resolve(RequestContext)
    print(f"Context2 ID: {id(context2)}")
    context2.user_id = "user999"
    
    # Resolve repository in the second scope
    repo2 = scope2.resolve(UserRepository)
    print(f"Repo2 using context ID: {id(repo2.context)}")
    print(await repo2.get_user_data())