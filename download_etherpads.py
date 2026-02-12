#!/usr/bin/env python3
"""
Wikimedia Etherpad Downloader

Downloads the text content of all Etherpads found by fetch_etherpad_links.py.
Uses the Etherpad /export/txt endpoint to retrieve pad contents.

Usage:
    # First, generate the links JSON:
    python fetch_etherpad_links.py --wiki wikimania

    # Then download all pads:
    python download_etherpads.py output/wikimania_wikimedia_etherpad_links.json

    # Or specify a custom output directory:
    python download_etherpads.py output/wikimania_wikimedia_etherpad_links.json --output downloaded_pads/

    # Adjust delay between requests (default: 0.3s):
    python download_etherpads.py output/wikimania_wikimedia_etherpad_links.json --delay 0.5

    # Resume a previous download (skip already downloaded files):
    python download_etherpads.py output/wikimania_wikimedia_etherpad_links.json --resume
"""

import json
import urllib.request
import urllib.parse
import os
import re
import sys
import time
import argparse
from datetime import datetime


USER_AGENT = "WikimediaEtherpadArchiver/1.0 (https://github.com/nethahussain/EtherpadArchives)"


def extract_pad_info(url: str) -> dict | None:
    """Extract pad name and build export URL from an Etherpad URL."""
    url = url.rstrip("/")

    pad_name = None
    export_url = None

    if "/p/" in url:
        pad_name = url.split("/p/", 1)[1]
        if pad_name:
            export_url = f"https://etherpad.wikimedia.org/p/{pad_name}/export/txt"
    elif "etherpad.wikimedia.org/" in url:
        remainder = url.split("etherpad.wikimedia.org/", 1)[1]
        if remainder.startswith("ep/pad/view/"):
            # Old format: http://etherpad.wikimedia.org/ep/pad/view/ro.xxx/latest
            pad_name = remainder.replace("ep/pad/view/", "").replace("/latest", "").replace("/", "_")
            export_url = f"https://etherpad.wikimedia.org/p/{pad_name}/export/txt"
        elif remainder and remainder != "p":
            pad_name = remainder
            export_url = f"https://etherpad.wikimedia.org/p/{pad_name}/export/txt"

    if not pad_name or not pad_name.strip():
        return None

    # Sanitize for filename
    safe_name = re.sub(r'[^\w\-.]', '_', urllib.parse.unquote(pad_name))
    if len(safe_name) > 200:
        safe_name = safe_name[:200]

    return {
        "pad_name": pad_name,
        "export_url": export_url,
        "safe_filename": safe_name + ".txt",
        "original_url": url,
    }


def download_pad(pad_info: dict, output_dir: str, timeout: int = 15) -> dict:
    """Download a single pad. Returns a result dict."""
    filepath = os.path.join(output_dir, pad_info["safe_filename"])

    try:
        req = urllib.request.Request(
            pad_info["export_url"],
            headers={"User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="replace")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        is_empty = content.strip() == ""
        return {
            "status": "empty" if is_empty else "ok",
            "size": len(content),
            "filepath": filepath,
        }

    except urllib.error.HTTPError as e:
        return {"status": "http_error", "error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"status": "url_error", "error": str(e.reason)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Download Etherpad contents from a links JSON file.",
        epilog="Run fetch_etherpad_links.py first to generate the JSON input file.",
    )
    parser.add_argument(
        "input_json",
        help="Path to the *_etherpad_links.json file from fetch_etherpad_links.py",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output directory for downloaded pads (default: downloaded_pads/<wiki_name>/)",
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=0.3,
        help="Delay between requests in seconds (default: 0.3)",
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=15,
        help="Request timeout in seconds (default: 15)",
    )
    parser.add_argument(
        "--resume", "-r",
        action="store_true",
        help="Skip already downloaded files (resume interrupted download)",
    )

    args = parser.parse_args()

    # Load data
    with open(args.input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    urls = sorted(data.get("etherpad_urls", {}).keys())

    if not urls:
        print("No Etherpad URLs found in the input file.")
        sys.exit(1)

    # Determine output directory
    if args.output:
        output_dir = args.output
    else:
        basename = os.path.splitext(os.path.basename(args.input_json))[0]
        wiki_name = basename.replace("_etherpad_links", "")
        output_dir = os.path.join("downloaded_pads", wiki_name)

    os.makedirs(output_dir, exist_ok=True)

    print(f"╔══════════════════════════════════════════════╗")
    print(f"║   Wikimedia Etherpad Downloader              ║")
    print(f"╚══════════════════════════════════════════════╝")
    print(f"  Input:    {args.input_json}")
    print(f"  Output:   {output_dir}/")
    print(f"  URLs:     {len(urls)}")
    print(f"  Delay:    {args.delay}s")
    print(f"  Resume:   {'yes' if args.resume else 'no'}")
    print()

    # Process URLs
    stats = {"ok": 0, "empty": 0, "skipped": 0, "failed": 0}
    errors = []

    for i, url in enumerate(urls):
        pad_info = extract_pad_info(url)

        if not pad_info:
            print(f"  [{i+1:>4}/{len(urls)}] SKIP (no pad name): {url}")
            stats["skipped"] += 1
            continue

        # Resume support
        if args.resume:
            filepath = os.path.join(output_dir, pad_info["safe_filename"])
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                print(f"  [{i+1:>4}/{len(urls)}] EXISTS: {pad_info['pad_name']}")
                stats["skipped"] += 1
                continue

        result = download_pad(pad_info, output_dir, timeout=args.timeout)

        if result["status"] == "ok":
            print(f"  [{i+1:>4}/{len(urls)}] OK ({result['size']:>7} bytes): {pad_info['pad_name']}")
            stats["ok"] += 1
        elif result["status"] == "empty":
            print(f"  [{i+1:>4}/{len(urls)}] EMPTY: {pad_info['pad_name']}")
            stats["empty"] += 1
        else:
            print(f"  [{i+1:>4}/{len(urls)}] FAIL: {pad_info['pad_name']} — {result.get('error', 'unknown')}")
            stats["failed"] += 1
            errors.append({
                "url": url,
                "export_url": pad_info["export_url"],
                "pad_name": pad_info["pad_name"],
                "error": result.get("error", "unknown"),
            })

        # Rate limiting
        time.sleep(args.delay)

    # Summary
    print(f"\n{'='*50}")
    print(f"  DOWNLOAD COMPLETE")
    print(f"  Success:  {stats['ok']}")
    print(f"  Empty:    {stats['empty']}")
    print(f"  Skipped:  {stats['skipped']}")
    print(f"  Failed:   {stats['failed']}")
    print(f"  Total:    {len(urls)}")
    print(f"{'='*50}")

    # Save error log
    error_log = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "input_file": args.input_json,
        "total_urls": len(urls),
        "stats": stats,
        "errors": errors,
    }
    error_path = os.path.join(output_dir, "_download_log.json")
    with open(error_path, "w", encoding="utf-8") as f:
        json.dump(error_log, f, indent=2, ensure_ascii=False)
    print(f"\n  Download log saved to {error_path}")

    # Save manifest
    files = [f for f in sorted(os.listdir(output_dir)) if not f.startswith("_")]
    manifest = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source_file": args.input_json,
        "total_urls": len(urls),
        "downloaded": stats["ok"],
        "empty": stats["empty"],
        "failed": stats["failed"],
        "skipped": stats["skipped"],
        "files": files,
    }
    manifest_path = os.path.join(output_dir, "_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"  Manifest saved to {manifest_path}")


if __name__ == "__main__":
    main()
