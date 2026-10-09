import sys
from pathlib import Path

from docheal.index import build_index, save_index

root = Path(sys.argv[1])
output = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".docheal/index.json")

index = build_index(root)
save_index(index, output)
print(
    f"Saved {len(index.chunks)} chunks, {len(index.sections)} sections, "
    f"{len(index.links)} links to {output}"
)