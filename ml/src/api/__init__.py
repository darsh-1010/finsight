"""API module for Financial Intelligence."""

from importlib import import_module

__all__ = ["app", "create_app"]


def __getattr__(name: str):
    """Lazy-load the FastAPI application objects on demand."""
    if name in {"app", "create_app"}:
        main_module = import_module(".main", __name__)
        return getattr(main_module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
