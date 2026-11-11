"""Check documentation links, anchors, search content and runtime assets.

Instructions: build with `uv run --group docs mkdocs build --strict`, then run
`uv run --group docs python tools/check_docs.py`. Pass --site-dir for a build
outside the default site/ directory. No public links are requested.
This structural check does not substitute for visual browser testing.
"""

import argparse
import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import markdown

PROJECT = Path(__file__).resolve().parents[1]


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.assets = []
        self.ids = set()

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag in ("script", "img") and attrs.get("src"):
            self.assets.append(attrs["src"])
        if tag == "link" and attrs.get("rel") in ("stylesheet", "icon"):
            self.assets.append(attrs["href"])


def check(site):
    sources = [PROJECT / "README.md", *sorted((PROJECT / "docs").glob("*.md"))]
    pages = sorted(site.glob("*.html"))
    for source in sources[1:]:
        assert (site / source.with_suffix(".html").name).is_file(), f"Missing page: {source.name}"
    cache = {}

    def references(path):
        if path not in cache:
            text = path.read_text(encoding="utf-8")
            if path.suffix == ".md":
                text = markdown.markdown(text, extensions=["fenced_code", "tables", "toc"])
            parsed = References()
            parsed.feed(text)
            cache[path] = parsed
        return cache[path]

    count = anchors = 0
    for page in sources + pages:
        parsed = references(page)
        for value in parsed.assets:
            assert not urlsplit(value).scheme and not urlsplit(value).netloc, (
                f"External runtime asset in {page.name}: {value}"
            )
        for value in parsed.links + parsed.assets:
            parts = urlsplit(value)
            if parts.scheme or parts.netloc:
                continue
            if parts.path.startswith("/"):
                target = site / unquote(parts.path).lstrip("/")
            else:
                target = (page.parent / unquote(parts.path)).resolve() if parts.path else page
            assert target.is_file(), f"Broken local reference in {page.name}: {value}"
            if parts.fragment and target.suffix in (".html", ".md"):
                assert unquote(parts.fragment) in references(target).ids, (
                    f"Missing anchor in {page.name}: {value}"
                )
                anchors += 1
            count += 1
    data = json.loads((site / "search/search_index.json").read_text(encoding="utf-8"))
    full_text = " ".join(entry["text"] + " " + entry["title"] for entry in data["docs"])
    for term in ("refresh", "Chromium", "max-late-ms", "loopback", "notebook", "Python API"):
        assert term in full_text, f"Missing search content: {term}"
    return {
        "status": "passed",
        "html_pages": len(pages),
        "markdown_sources": len(sources),
        "local_references": count,
        "anchors_checked": anchors,
        "search_entries": len(data["docs"]),
        "external_runtime_assets": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", type=Path, default=PROJECT / "site")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(check(args.site_dir.resolve()), indent=2))
        return 0
    except (AssertionError, OSError, ValueError) as exc:
        print(f"Documentation check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
