from onitu.utils import IS_DARWIN

if IS_DARWIN:
    from .local_storage_darwin import start, plug
else:
    from .local_storage import start, plug

__all__ = ["start", "plug"]
