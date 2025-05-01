from enum import Enum, auto
from typing import Any, Callable, Awaitable, TypeVar, Protocol, Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .service_descriptor import ServiceDescriptor

T = TypeVar('T')

class Lifecycle(Enum):
    """Defines how dependencies are instantiated and cached."""
    SINGLETON = auto()  # One instance per container
    TRANSIENT = auto()  # New instance per resolution
    SCOPED = auto()     # One instance per scope (e.g., request)

class ResolutionStrategy(Enum):
    """Strategy for resolving dependencies."""
    EAGER = auto()  # Resolve immediately
    LAZY = auto()   # Resolve only when needed

class ContainerProtocol(Protocol):
    """Protocol defining what a Container needs to implement for dependencies."""
    def resolve(self, service_type: Type[T], context_key: str = "") -> T: ...
    async def resolve_async(self, service_type: Type[T], context_key: str = "") -> T: ...
    def create_child_container(self) -> 'ContainerProtocol': ...
    def _get_descriptor(self, service_type: Type, context_key: str = "") -> Optional['ServiceDescriptor']: ...


FactoryCallable = Callable[[ContainerProtocol], Any]
AsyncFactoryCallable = Callable[[ContainerProtocol], Awaitable[Any]]