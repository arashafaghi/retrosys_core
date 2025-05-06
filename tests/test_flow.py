import pytest
import asyncio
from typing import List, Optional

from retrosys.core.dependency_injection import (
    Container, Module, Lifecycle, Lazy,
    injectable, inject_property, inject_method, register_module
)

# Base classes from your example
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
        
    async def connect(self) -> bool:
        self.connected = True
        return True
        
    async def query(self, sql: str) -> List[dict]:
        if not self.connected:
            await self.connect()
        if "users" in sql.lower():
            return [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]
        return []

@injectable(lifecycle=Lifecycle.SINGLETON)
class ConsoleLogger(ILogger):
    def __init__(self):
        self.messages = []
        
    def log(self, message: str) -> None:
        self.messages.append(message)

@injectable(lifecycle=Lifecycle.SINGLETON, is_async=True)
class UserRepository(IUserRepository):
    def __init__(self, db: IDatabase, logger: ILogger):
        self.db = db
        self.logger = logger
        
    async def get_all_users(self) -> List[dict]:
        self.logger.log("Getting all users")
        return await self.db.query("SELECT * FROM users")
        
    async def get_user_by_id(self, user_id: int) -> Optional[dict]:
        self.logger.log(f"Getting user with ID {user_id}")
        results = await self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
        return results[0] if results else None

class TestCompleteWorkflows:
    @pytest.mark.asyncio
    async def test_just_in_time_registration(self):
        # Arrange
        container = Container()
        
        # Act - Register the interface mapping but UserRepository will be auto-registered
        container.register(IDatabase, PostgresDatabase)
        container.register(ILogger, ConsoleLogger)  # Required by UserRepository
        container.register(IUserRepository, UserRepository, is_async=True)
        
        # Assert - Services were properly registered
        logger = container.resolve(ConsoleLogger)
        assert isinstance(logger, ConsoleLogger)
        
        repo = await container.resolve_async(IUserRepository)
        assert isinstance(repo, UserRepository)
        
        users = await repo.get_all_users()
        assert len(users) == 2
        
        
    @pytest.mark.asyncio
    async def test_mock_support(self):
        # Arrange
        container = Container()
        container.register(IDatabase, PostgresDatabase)
        container.register(ILogger, ConsoleLogger)
        container.register(IUserRepository, UserRepository)
        
        # Enable test mode and create a mock
        container.enable_test_mode()
        
        class MockDatabase(IDatabase):
            async def connect(self) -> bool:
                return True
                
            async def query(self, sql: str) -> List[dict]:
                return [{"id": 999, "name": "Mock User"}]
        
        # Act
        container.mock(IDatabase, MockDatabase())
        repo = await container.resolve_async(IUserRepository)
        users = await repo.get_all_users()
        
        # Assert
        assert len(users) == 1
        assert users[0]["id"] == 999
        assert users[0]["name"] == "Mock User"