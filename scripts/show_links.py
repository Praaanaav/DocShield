import sys
from pathlib import Path

from docheal.code_parser import parse_directory
from docheal.doc_parser import parse_docs_directory
from docheal.linker import build_links

root = Path(sys.argv[1])
chunks = parse_directory(root)
sections = parse_docs_directory(root)
links = build_links(chunks, sections)

print(f"{len(chunks)} code chunks, {len(sections)} doc sections, {len(links)} links\n")
for link in sorted(links, key=lambda item: (item.section_id, item.chunk_id)):
    print(f"{link.section_id}  ->  {link.chunk_id}  (score {link.score:.2f})")