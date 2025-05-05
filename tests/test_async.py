import pytest
import asyncio

from retrosys.core.dependency_injection import (
    Container, Lifecycle
)
from retrosys.core.dependency_injection.errors import AsyncInitializationError

class TestAsyncDependencies:
    @pytest.mark.asyncio
    async def test_async_service_resolution(self):
        # Arrange
        container = Container()
        
        class AsyncDatabase:
            def __init__(self):
                self.connected = False
                
            async def connect(self) -> bool:
                self.connected = True
                return True
                
        class Repository:
            def __init__(self, db: AsyncDatabase):
                self.db = db
                
            async def initialize(self) -> None:
                await self.db.connect()
                
        # Act
        container.register(AsyncDatabase, is_async=True)
        container.register(Repository, is_async=True)
        
        # This should fail since it's an async service
        with pytest.raises(AsyncInitializationError):
            container.resolve(Repository)
            
        # This should work
        repo = await container.resolve_async(Repository)
        
        # Assert
        assert isinstance(repo, Repository)
        assert isinstance(repo.db, AsyncDatabase)
    
    @pytest.mark.asyncio
    async def test_async_interface_implementation(self):
        # Arrange
        container = Container()
        
        class IAsyncService:
            async def method(self) -> str:
                pass
                
        class AsyncServiceImpl(IAsyncService):
            async def method(self) -> str:
                return "async result"
                
        # Act
        container.register(IAsyncService, AsyncServiceImpl, is_async=True)
        resolved = await container.resolve_async(IAsyncService)
        
        # Assert
        assert isinstance(resolved, AsyncServiceImpl)
        assert await resolved.method() == "async result"
    
    @pytest.mark.asyncio
    async def test_async_factory(self):
        # Arrange
        container = Container()
        
        class AsyncService:
            def __init__(self, value: str):
                self.value = value
                
        async def async_factory(c):
            # Simulate async work
            await asyncio.sleep(0.01)
            return AsyncService("async factory created")
                
        # Act
        container.register_factory(AsyncService, async_factory, is_async=True)
        resolved = await container.resolve_async(AsyncService)
        
        # Assert
        assert isinstance(resolved, AsyncService)
        assert resolved.value == "async factory created"
    
    @pytest.mark.asyncio
    async def test_async_singleton_lifecycle(self):
        # Arrange
        container = Container()
        
        class AsyncService:
            def __init__(self):
                self.id = id(self)
            
            async def initialize(self):
                # Async initialization work
                pass
                
        # Act
        container.register(AsyncService, lifecycle=Lifecycle.SINGLETON, is_async=True)
        instance1 = await container.resolve_async(AsyncService)
        instance2 = await container.resolve_async(AsyncService)
        
        # Assert
        assert instance1 is instance2  # Same instance