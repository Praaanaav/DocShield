# fastcache usage

## Fetching items

Use `get_item(key, timeout=30)` to fetch an item. If the item isn't
found within 30 seconds, a `TimeoutError` is raised.

## Storing items

Create a `Cache` and call `cache.set_item("a", "1")` to store a value.

## Clearing the cache

Call `Cache.clear_all()` to remove every item.

## Installation

Run `pip install fastcache`.