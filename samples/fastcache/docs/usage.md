# fastcache usage

## Fetching items

Use `get_item(key, timeout=30)` to fetch an item. If the item isn't
found within 30 seconds, a `TimeoutError` is raised.

## Storing items

Create a `Cache` and call `cache.set_item("a", "1")` to store a value.

## Clearing the cache

Call `Cache.clear_all()` to remove every item.
## REST API

Fetch an item over HTTP with `GET /items/{key}`. Store one with `POST /items`.

## Configuration

Set `MAX_ITEMS` to limit how many items are kept (default 1000). The
time-to-live comes from `DEFAULT_TTL`, which defaults to 300 seconds.
## Installation

Run `pip install fastcache`.