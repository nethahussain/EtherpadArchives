#!/usr/bin/env python3
"""
Wikimedia Etherpad Link Finder

Finds all links to etherpad.wikimedia.org on any Wikimedia wiki
using the MediaWiki External URL Usage API.

Usage:
    python fetch_etherpad_links.py                          # Default: meta.wikimedia.org
    python fetch_etherpad_links.py --wiki wikimania         # wikimania.wikimedia.org
    python fetch_etherpad_links.py --wiki en.wikipedia      # en.wikipedia.org
    python fetch_etherpad_links.py --wiki commons.wikimedia # commons.wikimedia.org
    python fetch_etherpad_links.py --url https://my.wiki.org/w/api.php  # Custom API URL

Output:
    output/<wikiname>_etherpad_links.json       - Structured JSON data
    output/<wikiname>_etherpad_wikicode.txt     - MediaWiki wikicode (ready to paste)
    output/<wikiname>_etherpad_urls.txt         - Plain list of unique Etherpad URLs
    output/<wikiname>_etherpad_links.csv        - CSV with Etherpad URL, page title, page URL
"""

import json
import csv
import urllib.request
import urllib.parse
import time
import argparse
import os
import sys
from collections import defaultdict


# ──────────────────────────────────────────────
# Wiki name → API URL resolution
# ──────────────────────────────────────────────

WIKI_SHORTCUTS = {
    "meta":       "https://meta.wikimedia.org/w/api.php",
    "wikimania":  "https://wikimania.wikimedia.org/w/api.php",
    "commons":    "https://commons.wikimedia.org/w/api.php",
    "wikidata":   "https://www.wikidata.org/w/api.php",
    "mediawiki":  "https://www.mediawiki.org/w/api.php",
    "wikibooks":  "https://en.wikibooks.org/w/api.php",
    "wikisource": "https://en.wikisource.org/w/api.php",
    "wikinews":   "https://en.wikinews.org/w/api.php",
    "wikiquote":  "https://en.wikiquote.org/w/api.php",
    "wikiversity":"https://en.wikiversity.org/w/api.php",
    "wikivoyage": "https://en.wikivoyage.org/w/api.php",
    "wiktionary": "https://en.wiktionary.org/w/api.php",
    "species":    "https://species.wikimedia.org/w/api.php",
    "incubator":  "https://incubator.wikimedia.org/w/api.php",
    "outreach":   "https://outreach.wikimedia.org/w/api.php",
    "wikitech":   "https://wikitech.wikimedia.org/w/api.php",
}


def resolve_api_url(wiki_name: str) -> str:
    """Resolve a wiki shortcut or name pattern to an API URL."""
    name = wiki_name.lower().strip()

    # Direct shortcut match
    if name in WIKI_SHORTCUTS:
        return WIKI_SHORTCUTS[name]

    # Pattern: "xx.wikipedia" → https://xx.wikipedia.org/w/api.php
    if "." in name:
        parts = name.split(".", 1)
        lang = parts[0]
        project = parts[1]
        if project in ("wikipedia", "wikibooks", "wikisource", "wikinews",
                        "wikiquote", "wikiversity", "wikivoyage", "wiktionary"):
            return f"https://{lang}.{project}.org/w/api.php"
        if project == "wikimedia":
            return f"https://{lang}.wikimedia.org/w/api.php"

    # Assume it's a Wikipedia language code
    return f"https://{name}.wikipedia.org/w/api.php"


def get_wiki_base_url(api_url: str) -> str:
    """Derive the wiki's base page URL from its API URL."""
    # https://meta.wikimedia.org/w/api.php → https://meta.wikimedia.org/wiki/
    return api_url.replace("/w/api.php", "/wiki/")


def get_wiki_label(api_url: str) -> str:
    """Derive a short label for filenames from the API URL."""
    from urllib.parse import urlparse
    host = urlparse(api_url).hostname  # e.g. meta.wikimedia.org
    return host.replace(".org", "").replace(".", "_").replace("www_", "")


# ──────────────────────────────────────────────
# API fetching
# ──────────────────────────────────────────────

USER_AGENT = "WikimediaEtherpadFinder/1.0 (https://github.com; etherpad preservation)"


def fetch_etherpad_links(api_url: str, delay: float = 0.5) -> list:
    """Fetch all external links to etherpad.wikimedia.org from a wiki."""
    all_results = []

    for protocol in ("http", "https"):
        eucontinue = None
        while True:
            params = {
                "action": "query",
                "list": "exturlusage",
                "euquery": "etherpad.wikimedia.org",
                "eulimit": "500",
                "euprotocol": protocol,
                "format": "json",
            }
            if eucontinue:
                params["eucontinue"] = eucontinue

            url = api_url + "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode())
            except Exception as e:
                print(f"  Error fetching {url}: {e}", file=sys.stderr)
                break

            results = data.get("query", {}).get("exturlusage", [])
            all_results.extend(results)
            print(f"  Fetched {len(results):>4} results  "
                  f"(protocol={protocol}, total so far: {len(all_results)})")

            if "continue" in data:
                eucontinue = data["continue"].get("eucontinue")
            else:
                break

            time.sleep(delay)

    return all_results


# ──────────────────────────────────────────────
# Data processing
# ──────────────────────────────────────────────

def process_results(raw_results: list) -> dict:
    """Organize raw API results into structured data."""
    etherpad_urls = {}
    pages_with_etherpads = {}

    for r in raw_results:
        url = r["url"]
        page = r["title"]

        if url not in etherpad_urls:
            etherpad_urls[url] = set()
        etherpad_urls[url].add(page)

        if page not in pages_with_etherpads:
            pages_with_etherpads[page] = set()
        pages_with_etherpads[page].add(url)

    return {
        "summary": {
            "total_results": len(raw_results),
            "unique_etherpad_urls": len(etherpad_urls),
            "unique_wiki_pages": len(pages_with_etherpads),
        },
        "etherpad_urls": {
            url: sorted(list(pages))
            for url, pages in sorted(etherpad_urls.items())
        },
        "pages_with_etherpads": {
            page: sorted(list(urls))
            for page, urls in sorted(pages_with_etherpads.items())
        },
    }


# ──────────────────────────────────────────────
# Output generators
# ──────────────────────────────────────────────

def write_json(data: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved JSON        → {path}")


def write_url_list(data: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        for url in sorted(data["etherpad_urls"].keys()):
            f.write(url + "\n")
    print(f"  Saved URL list    → {path}")


def write_csv(data: dict, wiki_base_url: str, path: str):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Etherpad URL", "Wiki Page", "Wiki Page URL"])
        for page, urls in sorted(data["pages_with_etherpads"].items()):
            page_url = wiki_base_url + page.replace(" ", "_")
            for url in sorted(urls):
                writer.writerow([url, page, page_url])
    print(f"  Saved CSV         → {path}")


def write_wikicode(data: dict, wiki_base_url: str, wiki_label: str, path: str):
    """Generate MediaWiki wikicode with clickable links and navigation."""
    pages_with_etherpads = data["pages_with_etherpads"]
    summary = data["summary"]
    sorted_pages = sorted(pages_with_etherpads.keys())

    # Determine if pages are year-prefixed (like Wikimania)
    year_prefixed = sum(1 for p in sorted_pages if p[:4].isdigit()) > len(sorted_pages) * 0.5

    # Group pages
    groups = defaultdict(list)
    if year_prefixed:
        for page in sorted_pages:
            if page[:4].isdigit():
                groups[page[:4]].append(page)
            else:
                prefix = page.split(":")[0] if ":" in page else "Other"
                groups[prefix].append(page)
    else:
        for page in sorted_pages:
            letter = page[0].upper() if page else "?"
            groups[letter].append(page)

    sorted_groups = sorted(groups.keys())

    # Determine if pages are local (Meta-Wiki wikilinks) or external
    is_meta = "meta.wikimedia.org" in wiki_base_url

    def section_title(g):
        if year_prefixed and g.isdigit():
            return f"Wikimania {g}"
        return g

    # Build nav bar
    nav_parts = []
    for g in sorted_groups:
        title = section_title(g)
        anchor = title.replace(" ", "_")
        nav_parts.append(f"[[#{anchor}|{title}]]")
    nav_bar = " '''·''' ".join(nav_parts)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"= Etherpad Links on {wiki_label} =\n\n")
        f.write(
            f"This page catalogs all external links to "
            f"<code>etherpad.wikimedia.org</code> found on "
            f"[{wiki_base_url} {wiki_label}]. "
            f"Wikimedia Foundation is phasing out Etherpad; this inventory "
            f"is intended to facilitate archiving before the service is "
            f"discontinued.\n\n"
        )

        # Summary table
        f.write("{| class=\"wikitable\"\n|-\n! Statistic !! Count\n")
        f.write(f"|-\n| Unique Etherpad URLs || '''{summary['unique_etherpad_urls']:,}'''\n")
        f.write(f"|-\n| Wiki pages with Etherpad links || '''{summary['unique_wiki_pages']:,}'''\n")
        f.write(f"|-\n| Total link instances (incl. duplicates) || '''{summary['total_results']:,}'''\n")
        f.write("|}\n\n")

        # Nav bar
        f.write(
            f'<div style="text-align:center; background:#f8f9fa; '
            f'border:1px solid #a2a9b1; padding:8px; margin:10px 0; '
            f'font-size:120%;">\n'
            f"'''Navigate:''' {nav_bar}\n</div>\n\n"
        )
        f.write("__TOC__\n\n")

        # Sections
        for group in sorted_groups:
            pages = sorted(groups[group])
            page_count = len(pages)
            url_count = sum(len(pages_with_etherpads[p]) for p in pages)
            title = section_title(group)

            f.write(f"\n== {title} ==\n")
            f.write(f"'''{page_count}''' pages, '''{url_count}''' Etherpad links\n\n")

            for page_title in pages:
                urls = sorted(pages_with_etherpads[page_title])

                if is_meta:
                    f.write(f"=== [[{page_title}]] ===\n")
                else:
                    safe_title = urllib.parse.quote(
                        page_title.replace(" ", "_"), safe="/:@!$&'()*+,;=-._~"
                    )
                    f.write(
                        f"=== [{wiki_base_url}{safe_title} {page_title}] ===\n"
                    )

                for url in urls:
                    f.write(f"* [{url} {url}]\n")
                f.write("\n")

    print(f"  Saved wikicode    → {path}")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Find all Etherpad links on a Wikimedia wiki.",
        epilog="Examples:\n"
               "  python fetch_etherpad_links.py --wiki meta\n"
               "  python fetch_etherpad_links.py --wiki wikimania\n"
               "  python fetch_etherpad_links.py --wiki en.wikipedia\n"
               "  python fetch_etherpad_links.py --wiki commons\n"
               "  python fetch_etherpad_links.py --url https://custom.wiki/w/api.php\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--wiki", "-w",
        default="meta",
        help="Wiki shortcut or pattern (default: meta). "
             "Examples: meta, wikimania, commons, en.wikipedia, fr.wikisource. "
             f"Shortcuts: {', '.join(sorted(WIKI_SHORTCUTS.keys()))}",
    )
    parser.add_argument(
        "--url", "-u",
        help="Direct MediaWiki API URL (overrides --wiki). "
             "Example: https://my.wiki.org/w/api.php",
    )
    parser.add_argument(
        "--output", "-o",
        default="output",
        help="Output directory (default: output/)",
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=0.5,
        help="Delay between API requests in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--format", "-f",
        nargs="+",
        default=["json", "wikicode", "csv", "urls"],
        choices=["json", "wikicode", "csv", "urls"],
        help="Output formats (default: all)",
    )

    args = parser.parse_args()

    # Resolve API URL
    if args.url:
        api_url = args.url
    else:
        api_url = resolve_api_url(args.wiki)

    wiki_base_url = get_wiki_base_url(api_url)
    wiki_label = get_wiki_label(api_url)

    print(f"╔══════════════════════════════════════════════╗")
    print(f"║   Wikimedia Etherpad Link Finder             ║")
    print(f"╚══════════════════════════════════════════════╝")
    print(f"  Wiki:     {wiki_label}")
    print(f"  API URL:  {api_url}")
    print(f"  Base URL: {wiki_base_url}")
    print()

    # Fetch
    print("Fetching Etherpad links...")
    raw_results = fetch_etherpad_links(api_url, delay=args.delay)

    if not raw_results:
        print("\nNo Etherpad links found on this wiki.")
        sys.exit(0)

    # Process
    print("\nProcessing results...")
    data = process_results(raw_results)
    summary = data["summary"]

    print(f"\n  ┌─────────────────────────────────────────┐")
    print(f"  │  Unique Etherpad URLs:  {summary['unique_etherpad_urls']:>6,}          │")
    print(f"  │  Wiki pages with links: {summary['unique_wiki_pages']:>6,}          │")
    print(f"  │  Total link instances:  {summary['total_results']:>6,}          │")
    print(f"  └─────────────────────────────────────────┘")

    # Write outputs
    os.makedirs(args.output, exist_ok=True)
    prefix = os.path.join(args.output, f"{wiki_label}_etherpad")

    print(f"\nWriting outputs to {args.output}/...")

    if "json" in args.format:
        write_json(data, f"{prefix}_links.json")

    if "urls" in args.format:
        write_url_list(data, f"{prefix}_urls.txt")

    if "csv" in args.format:
        write_csv(data, wiki_base_url, f"{prefix}_links.csv")

    if "wikicode" in args.format:
        write_wikicode(data, wiki_base_url, wiki_label, f"{prefix}_wikicode.txt")

    print("\nDone!")


if __name__ == "__main__":
    main()
