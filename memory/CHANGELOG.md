# Changelog

## [2026-07-22]
- Initialized workspace structure.
- Conducted connection research and discovered curl.exe bypass for Cloudflare 403 Forbidden responses.
- Setup canonical project memory files.
- Implemented asynchronous scraper in `scrape.py` using Python `asyncio` and `curl.exe` subprocesses.
- Parsed accommodation cards' data attributes and coordinates.
- Modified `scrape.py` to loop over all 2-night date combinations in August concurrently.
- Refactored `scrape.py` to run fully in memory (removed file writing), decode HTML entities in hotel names, filter out `price <= 0` results, enforce UTF-8 stdout console printing, and print the cheapest bookable accommodation with a clickable direct URL.
- Added top 3 cheapest accommodations printout and modified performance duration tracking to start at the beginning of `main()` and end only after all outputs are printed, capturing all calculations and string operations.
- Ran full performance speed test for Győr in August 2026 (29 combinations, 87 total HTTP requests, 3422 items scraped) in 15.20 seconds (~225.15 items/second).
- Created Streamlit web application `app.py` providing an interactive UI containing parameter configuration, real-time scraping progress bar, metrics cards, top 3 deal cards with direct booking links, monthly price trend charts, and searchable dataframes.
- Added cross-platform curl compatibility to dynamically run on Windows (`curl.exe`) or Linux (`curl` in Streamlit Cloud).
- Created deployment dependencies configuration files: `requirements.txt` and `packages.txt`.
- Verified local Streamlit instance boots and runs on port `8501`.
- Hotfixed keyword argument error in `app.py` (`unsafe_style_type` -> `unsafe_allow_html`).
- Refactored `app.py`'s `fetch_page` to use `asyncio.to_thread` with synchronous `subprocess.run` to bypass Windows event loop background thread limitations for subprocesses in Streamlit.
- Updated the Streamlit metric cards layout in `app.py` to output the exact time taken by different processes (scraping, calculation/sorting, and total elapsed duration).
- Optimized both `scrape.py` and `app.py` to only scrape page 1 of search results for each date range, reducing total HTTP requests to 29 (down from 87) and significantly accelerating execution speed.
- Implemented a 2-second timeout and 3-attempt retry loop on all `curl` calls in both `scrape.py` and `app.py` to automatically abort and restart straggler requests, completely resolving the random end-of-run slowdown issue.
- Added optional proxy configuration parameter in `app.py`'s UI sidebar and automatic Cloudflare bot protection/datacenter IP block detection, displaying diagnostic explanations and workaround guidance (proxy or local run) to the user when hosted in Streamlit Cloud.
- Fixed a bug where proxy requests timed out due to the strict 2-second local timeout, dynamically adjusting max request time to 6 seconds when a proxy is configured.
