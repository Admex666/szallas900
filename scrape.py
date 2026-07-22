import asyncio
import re
import json
import sys
import time
import argparse
import html

# Ensure UTF-8 output encoding for terminal prints
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Global rate control
sem = None
requests_count = 0

async def fetch_page(url: str) -> str:
    """Fetches the HTML content of a URL using curl.exe subprocess with a semaphore, timeout and retries."""
    global requests_count
    async with sem:
        requests_count += 1
        for attempt in range(3):
            try:
                process = await asyncio.create_subprocess_exec(
                    "curl.exe", "-s", "--connect-timeout", "3", "-m", "2", url, "-H", f"User-Agent: {USER_AGENT}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=3.0)
                if process.returncode == 0:
                    return stdout.decode('utf-8', errors='ignore')
            except Exception:
                pass
        return ""

def parse_page(html_content: str):
    """Parses accommodation items and pagination from the HTML page."""
    articles = re.findall(r'(<article[^>]*class="[^"]*accommodation-item[^"]*"[^>]*>[\s\S]*?</article>)', html_content)
    items = []
    
    for article in articles:
        tag_match = re.match(r'(<article[^>]*>)', article)
        if not tag_match:
            continue
        opening_tag = tag_match.group(1)
        
        # Parse all data-attributes
        attrs = dict(re.findall(r'data-([a-zA-Z0-9\-]+)="([^"]*)"', opening_tag))
        
        # Map fields
        item_id = attrs.get('id') or attrs.get('item-id') or attrs.get('hotel-id')
        raw_name = attrs.get('hotel-name') or ""
        name = html.unescape(raw_name)
        category = attrs.get('hotel-type') or attrs.get('item-category')
        price = attrs.get('price')
        currency = attrs.get('currency')
        avg_rating = attrs.get('average-rating')
        rating_count = attrs.get('rating-count')
        score = attrs.get('score')
        
        # Extract lat/lng
        lat_match = re.search(r'data-latitude="([^"]*)"', article)
        lng_match = re.search(r'data-longitude="([^"]*)"', article)
        lat = lat_match.group(1) if lat_match else None
        lng = lng_match.group(1) if lng_match else None
        
        # Extract title link href
        href = None
        a_match = re.search(r'<a\s+([^>]*class="[^"]*accommodation-item__title[^"]*"[^>]*)>', article)
        if not a_match:
            a_match = re.search(r'<a\s+([^>]*href="[^"]+"[^>]*class="[^"]*accommodation-item__title[^"]*"[^>]*)>', article)
        if a_match:
            attrs_str = a_match.group(1)
            href_match = re.search(r'href="([^"]+)"', attrs_str)
            if href_match:
                href = href_match.group(1).lstrip('/')
        
        items.append({
            'id': item_id,
            'name': name,
            'category': category,
            'price': float(price) if price else None,
            'currency': currency,
            'average_rating': float(avg_rating) if avg_rating else None,
            'rating_count': int(rating_count) if rating_count else None,
            'score': float(score) if score else None,
            'latitude': float(lat) if lat else None,
            'longitude': float(lng) if lng else None,
            'href': href
        })
        
    # Parse pagination
    pages_match = re.search(r'class="pagination-container__label"\s*>\s*\d+\s*/\s*(\d+)\s*</span>', html_content)
    total_pages = int(pages_match.group(1)) if pages_match else 1
    
    return items, total_pages

async def scrape_date_range(town_id: str, adults: int, checkin: str, checkout: str):
    """Scrapes only page 1 for a single checkin/checkout date range."""
    base_url = f"https://szallas.hu/{town_id}?adults={adults}&checkin={checkin}&checkout={checkout}&sort=CheapestPerPersonPerNightRate&sortdir=asc"
    
    html1 = await fetch_page(base_url)
    if not html1:
        print(f"[{checkin} -> {checkout}] Failed to retrieve page 1.")
        return []
        
    items, _ = parse_page(html1)
    
    # Label each item with its corresponding date range
    for item in items:
        item['checkin'] = checkin
        item['checkout'] = checkout
        
    print(f"[{checkin} -> {checkout}] Done. Scraped {len(items)} accommodations.")
    return items

async def main():
    parser = argparse.ArgumentParser(description="Szallas.hu August month scraping speed test")
    parser.add_argument('--town', type=str, default='sopron', help='Town ID (e.g. sopron)')
    parser.add_argument('--adults', type=int, default=2, help='Number of adults')
    parser.add_argument('--concurrency', type=int, default=10, help='Max concurrent requests')
    
    args = parser.parse_args()
    
    global sem
    sem = asyncio.Semaphore(args.concurrency)
    
    start_time = time.time()
    
    # Generate all 2-night checkin/checkout date ranges in August (days 1 to 29)
    date_ranges = []
    for day in range(1, 30):
        checkin = f"2026-08-{day:02d}"
        checkout = f"2026-08-{(day+2):02d}"
        date_ranges.append((checkin, checkout))
        
    print(f"Starting August 2026 speed test for town: {args.town}")
    print(f"Total date ranges to check: {len(date_ranges)}")
    print(f"Global request concurrency limit: {args.concurrency}\n")
    
    # Execute all scraping jobs concurrently
    tasks = [
        scrape_date_range(args.town, args.adults, checkin, checkout)
        for checkin, checkout in date_ranges
    ]
    results = await asyncio.gather(*tasks)
    
    all_scraped_items = []
    for r in results:
        all_scraped_items.extend(r)
        
    # Identify the 3 cheapest options (filtering out items where price <= 0)
    valid_items = [
        item for item in all_scraped_items 
        if item.get('price') is not None and item.get('price') > 0
    ]
    
    if valid_items:
        # Sort items by price ascending
        sorted_items = sorted(valid_items, key=lambda x: x['price'])
        
        # Take the top 3 cheapest items
        cheapest_3 = sorted_items[:3]
        
        print("\n" + "="*50)
        print("TOP 3 CHEAPEST ACCOMMODATIONS FOUND:")
        for idx, item in enumerate(cheapest_3, 1):
            href_val = item.get('href') or ""
            url = f"https://szallas.hu/{href_val}?checkin={item['checkin']}&checkout={item['checkout']}"
            print(f"\n{idx}. Name: {item['name']}")
            print(f"   Price: {item['price']:.0f} {item['currency']}")
            print(f"   Dates: {item['checkin']} -> {item['checkout']}")
            print(f"   Clickable Link: {url}")
        print("="*50 + "\n")
    else:
        print("\nNo priced accommodations found.\n")
        
    # Record elapsed time AFTER printing everything to include calculations & console output time
    elapsed_time = time.time() - start_time
    
    print("="*50)
    print("Scraping Completed Successfully!")
    print(f"Total time elapsed: {elapsed_time:.2f} seconds")
    print(f"Total HTTP requests made: {requests_count}")
    print(f"Total items scraped: {len(all_scraped_items)}")
    print(f"Average request speed: {requests_count / elapsed_time:.2f} requests/second")
    print(f"Average item processing speed: {len(all_scraped_items) / elapsed_time:.2f} items/second")
    print("="*50 + "\n")

if __name__ == '__main__':
    asyncio.run(main())
