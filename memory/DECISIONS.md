# decisions

## DEC-01: Use curl.exe Subprocesses for Scraping

### Context
Standard HTTP libraries like Python's `urllib`, `requests`, and Node's `fetch` trigger Cloudflare's bot protection, leading to HTTP 403 Forbidden responses. However, invoking `curl.exe` with a standard browser User-Agent returns the requested HTML successfully.

### Decision
Use Python's `asyncio.create_subprocess_exec` to spawn `curl.exe` tasks to fetch HTML pages concurrently.

### Expected Impact
Allows bypassing basic Cloudflare verification without maintaining heavy browser environments (Puppeteer/Playwright) or third-party C/C++ compilation packages (which may be slow to install or fail on Windows).
