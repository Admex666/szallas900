# Project: Szallas.hu scraping speed test

## Overview
This project is built to test and demonstrate how quickly we can scrape accommodation search results from `szallas.hu` for a given city and check-in/check-out dates in August 2026.

## Goals
- Build a robust, fast, and concurrent scraper using Python.
- Successfully bypass Cloudflare's bot detection using `curl.exe` process execution.
- Collect structured data (name, price, currency, rating, category, location) for all accommodations matching the search.
- Profile and analyze scraping performance (requests/second, data processing rate).

## Scope
- Focus on the search list page scraping.
- Parallel page fetching using `asyncio` and `curl.exe`.
- Parse page HTML content using fast regex and standard parsing patterns.

## Key Technologies
- **Python 3.13**
- **Standard Libraries**: `asyncio` for concurrency, `re` for extraction, `json` for output formatting.
- **System Commands**: `curl.exe` for HTTP/HTTPS requests (incorporating custom headers).
