class Item:
    """A cached item."""

    def __init__(self, key: str, value: str) -> None:
        self.key = key
        self.value = value


class Cache:
    """An in-memory cache."""

    def __init__(self) -> None:
        self._items: dict[str, Item] = {}

    def set_item(self, key: str, value: str) -> None:
        """Store an item."""
        self._items[key] = Item(key, value)

    def clear_all(self) -> None:
        """Remove every item."""
        self._items.clear()


def get_item(key: str, timeout: int = 30) -> Item:
    """Fetch an item from the cache."""
    raise NotImplementedError