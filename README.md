# Wikimedia Etherpad Link Finder

Wikimedia Foundation is phasing out its [Etherpad](https://etherpad.wikimedia.org/) instance. Over the years, thousands of Etherpad links have been embedded across Wikimedia wikis — meeting notes, conference sessions, brainstorming documents, and more. Many of these contain valuable historical records of community discussions and decisions.

This tool queries any Wikimedia wiki's API to find **all pages that link to `etherpad.wikimedia.org`**, and generates outputs in multiple formats to help with preservation efforts.

## Quick start

```bash
# No dependencies needed — uses only Python standard library
python fetch_etherpad_links.py --wiki meta
```

## Usage

```bash
# Search Meta-Wiki (default)
python fetch_etherpad_links.py

# Search Wikimania wiki
python fetch_etherpad_links.py --wiki wikimania

# Search English Wikipedia
python fetch_etherpad_links.py --wiki en.wikipedia

# Search Wikimedia Commons
python fetch_etherpad_links.py --wiki commons

# Search French Wikisource
python fetch_etherpad_links.py --wiki fr.wikisource

# Search any wiki by API URL
python fetch_etherpad_links.py --url https://outreach.wikimedia.org/w/api.php

# Choose output formats
python fetch_etherpad_links.py --wiki meta --format json wikicode

# Custom output directory
python fetch_etherpad_links.py --wiki meta --output results/
```

## Wiki shortcuts

The following shortcuts are built in:

| Shortcut | Wiki |
|----------|------|
| `meta` | meta.wikimedia.org |
| `wikimania` | wikimania.wikimedia.org |
| `commons` | commons.wikimedia.org |
| `wikidata` | wikidata.org |
| `mediawiki` | mediawiki.org |
| `species` | species.wikimedia.org |
| `incubator` | incubator.wikimedia.org |
| `outreach` | outreach.wikimedia.org |
| `wikitech` | wikitech.wikimedia.org |

You can also use patterns like `en.wikipedia`, `fr.wikisource`, `de.wiktionary`, etc.

## Output formats

The tool generates four output files in the `output/` directory:

| File | Description |
|------|-------------|
| `*_etherpad_links.json` | Structured JSON with bidirectional mappings (URL → pages, page → URLs) |
| `*_etherpad_wikicode.txt` | MediaWiki wikicode ready to paste onto a wiki page, with navigation bar and clickable links |
| `*_etherpad_links.csv` | CSV with columns: Etherpad URL, wiki page title, wiki page URL |
| `*_etherpad_urls.txt` | Plain text list of unique Etherpad URLs (one per line), useful for scripting bulk downloads |

### Wikicode features

The generated wikicode includes:
- Summary statistics in a wikitable
- Clickable navigation bar (A–Z for most wikis, by-year for Wikimania)
- All Etherpad URLs displayed as full clickable links
- Wiki page titles linked back to the source page
- Table of contents via `__TOC__`

## How it works

The tool uses the [MediaWiki External URL Usage API](https://www.mediawiki.org/wiki/API:Exturlusage) (`list=exturlusage`) to find all pages that contain external links to `etherpad.wikimedia.org`. It queries both `http` and `https` protocols and paginates through all results.

No authentication is needed — this only queries publicly available data.

## Results so far

| Wiki | Unique Etherpad URLs | Pages with links |
|------|---------------------|-----------------|
| Meta-Wiki | 2,811 | 2,885 |
| Wikimania | 626 | 997 |

## Downloading Etherpad contents

Once you have the links JSON, use `download_etherpads.py` to bulk-download the actual pad contents:

```bash
# Step 1: Find all links
python fetch_etherpad_links.py --wiki wikimania

# Step 2: Download all pad contents
python download_etherpads.py output/wikimania_wikimedia_etherpad_links.json
```

### Downloader options

```bash
# Resume an interrupted download (skips already-downloaded files)
python download_etherpads.py output/links.json --resume

# Custom output directory
python download_etherpads.py output/links.json --output my_pads/

# Slower requests (be polite to the server)
python download_etherpads.py output/links.json --delay 1.0
```

The downloader saves each pad as a `.txt` file, plus a `_manifest.json` with statistics and a `_download_log.json` with any errors.

## Further preservation steps

Beyond downloading, you can also:

1. **Archive to the Wayback Machine** using the Save Page Now API

2. **Copy contents to wiki pages** for long-term preservation on-wiki

## Requirements

- Python 3.6+
- No external dependencies (uses only the Python standard library)

## License

CC0 1.0 Universal — Public Domain. See [LICENSE](LICENSE).
