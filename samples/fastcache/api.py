from fastapi import FastAPI

from core import get_item

app = FastAPI()


@app.get("/items/{key}")
def read_item(key: str, timeout: int = 30):
    """Fetch one item over HTTP."""
    return get_item(key, timeout)


@app.post("/items", status_code=201)
def create_item(key: str, value: str):
    """Store one item over HTTP."""
    return {"key": key}