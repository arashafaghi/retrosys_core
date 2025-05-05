import asyncio
import logging
import sys
from typing import List, Optional
from retrosys.core.dependency_injection import (
    Container, Module, Lifecycle, Lazy,
    injectable, inject_property, inject_method, register_module
)

#Set up logging
logging.basicConfig(level=logging.INFO)

#Define some interfaces and implementations
class IDatabase:
    async def connect(self) -> bool:
        pass
        
    async def query(self, sql: str) -> List[dict]:
        pass

class ILogger:
    def log(self, message: str) -> None:
        pass

class IUserRepository:
    async def get_all_users(self) -> List[dict]:
        pass
        
    async def get_user_by_id(self, user_id: int) -> Optional[dict]:
        pass

@injectable(lifecycle=Lifecycle.SINGLETON, is_async=True)
class PostgresDatabase(IDatabase):
    def __init__(self, connection_string: str = "postgres://localhost:5432/mydb"):
        self.connection_string = connection_string
        self.connected = False
        print(f"PostgresDatabase created with {connection_string}")
        
    async def connect(self) -> bool:
        print(f"Connecting to database at {self.connection_string}")
        #Simulate connection delay
        await asyncio.sleep(0.1)
        self.connected = True
        return True
        
    async def query(self, sql: str) -> List[dict]:
        if not self.connected:
            await self.connect()
        print(f"Executing query: {sql}")
        #Simulate query delay
        await asyncio.sleep(0.05)
       # Return dummy data
        if "users" in sql.lower():
            return [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]
        return []
        
    async def on_init(self) -> None:
        await self.connect()
        
    async def on_destroy(self) -> None:
        print("Closing database connection")
        self.connected = False

@injectable(lifecycle=Lifecycle.SINGLETON)
class ConsoleLogger(ILogger):
    def log(self, message: str) -> None:
        print(f"[LOG] {message}")
        
    def on_init(self) -> None:
        self.log("Logger initialized")
        
    def on_destroy(self) -> None:
        self.log("Logger shutting down")

@injectable(lifecycle=Lifecycle.SINGLETON, is_async=True)
class UserRepository(IUserRepository):
    def __init__(self, db: IDatabase, logger: ILogger):
        self.db = db
        self.logger = logger
        self.logger.log("UserRepository created")
        
    async def get_all_users(self) -> List[dict]:
        self.logger.log("Getting all users")
        return await self.db.query("SELECT * FROM users")
        
    async def get_user_by_id(self, user_id: int) -> Optional[dict]:
        self.logger.log(f"Getting user with ID {user_id}")
        results = await self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
        return results[0] if results else None

#Example with lazy resolution
@injectable(lifecycle=Lifecycle.TRANSIENT)
class UserService:
    def __init__(self, lazy_repo: Lazy[IUserRepository]):
        self.lazy_repo = lazy_repo
        print("UserService created with lazy repository")
        
    async def get_users(self) -> List[dict]:
       # Repository only resolved when needed
        repo = await self.lazy_repo.async_resolve()
        return await repo.get_all_users()

#Example with property injection
@injectable(lifecycle=Lifecycle.SINGLETON)
class AnalyticsService:
    def __init__(self):
        self.logger = None  # Will be injected
        print("AnalyticsService created")
        
    @inject_property(ILogger)
    def logger(self):
        pass
        
    def track_event(self, event_name: str, data: dict) -> None:
        if self.logger:
            self.logger.log(f"Event: {event_name}, Data: {data}")

#Example with method injection
@injectable(lifecycle=Lifecycle.SINGLETON)
class NotificationService:
    def __init__(self):
        print("NotificationService created")
        
    @inject_method({"user_repo": IUserRepository})
    def send_notification(self, user_repo: IUserRepository, user_id: int, message: str) -> bool:
        print(f"Sending notification to user {user_id}: {message}")
        return True

#Example with modules
@register_module(Container())
class DatabaseModule:
    @injectable(lifecycle=Lifecycle.SINGLETON, is_async=True)
    class TestDatabase(IDatabase):
        async def connect(self) -> bool:
            print("Connecting to test database")
            return True
            
        async def query(self, sql: str) -> List[dict]:
            print(f"Test DB Query: {sql}")
            return [{"id": 1, "name": "Test User"}]

from abc import ABC, abstractmethod

class iuser(ABC):
    @abstractmethod
    def __init__(self, logger: ILogger):
        pass
    @abstractmethod
    def some_method(self):
        pass
class User(iuser):
    def __init__(self, logger: ConsoleLogger):
        self.logger = logger
        print("User created")
        
        self.name = "Default User"
    def some_method(self):
        self.logger.log("something")

#
async def main():
    container = Container()
    container.register(IDatabase, PostgresDatabase, Lifecycle.SINGLETON, is_async=True)
    container.register(ILogger, ConsoleLogger)
    container.register(IUserRepository, UserRepository, is_async=True)
    container.register_factory(
        str, 
        lambda c: "postgres://localhost:5432/mydb", 
        Lifecycle.SINGLETON,
        context_key="connection_string"
    )
    
    # Register services with the @injectable decorator
    # These are already registered via their decorators
    
    # Create a module and register it
    db_module = Module("database")
    container.register_module(db_module)
    
    # Resolve and use services
    logger = container.resolve(ILogger)
    logger.log("Application starting")
    
    # Async services must be resolved with resolve_async
    user_repo = await container.resolve_async(IUserRepository)
    users = await user_repo.get_all_users()
    logger.log(f"Found {len(users)} users")
    
    # Test lazy resolution
    user_service = container.resolve(UserService)
    users_from_service = await user_service.get_users()
    logger.log(f"UserService found {len(users_from_service)} users")
    
    # Test property injection
    analytics = container.resolve(AnalyticsService)
    analytics.track_event("app_start", {"timestamp": "2023-01-01T12:00:00"})
    
    # Test method injection
    notifications = container.resolve(NotificationService)
    notifications.send_notification(user_repo, 1, "Hello from DI example!")
    
    # Test scoped services
    async with container.create_scope() as scope:
        scoped_repo = await scope.resolve_async(IUserRepository)
        scoped_user = await scoped_repo.get_user_by_id(1)
        logger.log(f"Found user in scope: {scoped_user['name']}")
    
    # Test testing mode
    container.enable_test_mode()
    
    # Create a mock
    class MockDatabase(IDatabase):
        async def connect(self) -> bool:
            return True
            
        async def query(self, sql: str) -> List[dict]:
            return [{"id": 999, "name": "Mock User"}]
    
    # Register the mock
    container.mock(IDatabase, MockDatabase())
    
    # Now when resolved, the mock will be used
    test_repo = await container.resolve_async(IUserRepository)
    test_users = await test_repo.get_all_users()
    logger.log(f"Mock found users: {test_users}")
    
    # Visualize the dependency graph
    #container.visualize_dependency_graph("di_graph.png")
    
    # Cleanup
    #await container.dispose()
    logger.log("Application shutting down")
    logger.log("____________________________________________________!")
    container.register(iuser, User, Lifecycle.SINGLETON) 
    u = container.resolve(iuser)
    u.some_method()

if __name__ == "__main__":
    asyncio.run(main())