"""Dependency Injection Container.

Simple DI container for managing service instances and their dependencies.
"""

from collections.abc import Callable
from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)


class Container:
    """Simple dependency injection container.

    Provides lazy instantiation and singleton management for services.

    Usage:
        Container.register(IQueryService, QueryService)
        service = Container.resolve(IQueryService)
    """

    _registry: dict[type, type | Callable] = {}
    _instances: dict[type, Any] = {}
    _factories: dict[type, Callable] = {}

    @classmethod
    def register(
        cls,
        interface: type,
        implementation: type | Callable[..., Any],
        singleton: bool = True,
    ) -> None:
        """Register an implementation for an interface.

        Args:
            interface: Abstract interface type
            implementation: Concrete implementation class or factory
            singleton: Whether to cache the instance (default: True)
        """
        cls._registry[interface] = implementation

        if not singleton:
            cls._factories[interface] = implementation

        logger.debug(f"Registered: {interface.__name__} -> {implementation}")

    @classmethod
    def resolve(cls, interface: type, **kwargs: Any) -> Any:
        """Resolve an interface to its implementation.

        Args:
            interface: Abstract interface type to resolve
            **kwargs: Arguments to pass to the initializer if creating a new instance

        Returns:
            Instance of the implementation

        Raises:
            KeyError: If interface is not registered
        """
        # Check if already resolved as singleton
        if interface in cls._instances:
            return cls._instances[interface]

        # Check for factory (non-singleton)
        if interface in cls._factories:
            factory = cls._factories[interface]
            return factory(**kwargs)

        # Create new instance
        if interface not in cls._registry:
            raise KeyError(f"No implementation registered for {interface.__name__}")

        implementation = cls._registry[interface]

        if callable(implementation) and not isinstance(implementation, type):
            # Factory function
            instance = implementation(**kwargs)
        else:
            # Class
            instance = implementation(**kwargs)

        # Cache if it's meant to be a singleton (default)
        if interface not in cls._factories:
            cls._instances[interface] = instance
            logger.debug(f"Created singleton instance: {interface.__name__}")
        else:
            logger.debug(f"Created transient instance: {interface.__name__}")

        return instance

    @classmethod
    def reset(cls) -> None:
        """Reset all registrations and instances (useful for testing)."""
        cls._registry.clear()
        cls._instances.clear()
        cls._factories.clear()
        logger.info("Container reset")

    @classmethod
    def is_registered(cls, interface: type) -> bool:
        """Check if an interface is registered."""
        return interface in cls._registry


def inject(interface: type) -> Callable[[Callable], Callable]:
    """Decorator to inject dependencies.

    Usage:
        @inject(IQueryService)
        async def handler(request, service: IQueryService):
            ...
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            if interface.__name__.lower() not in kwargs:
                kwargs["service"] = Container.resolve(interface)
            return await func(*args, **kwargs)

        return wrapper

    return decorator
