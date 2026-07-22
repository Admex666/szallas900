import streamlit as st
import asyncio
import re
import time
import argparse
import html
import platform
import subprocess
import pandas as pd

# Set page configuration
st.set_page_config(
    page_title="Szallas.hu Scraper & Deal Finder",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .reportview-container {
        background: #f0f2f6;
    }
    .card {
        padding: 20px;
        border-radius: 10px;
        background-color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Detect OS to select curl command
CURL_CMD = "curl.exe" if platform.system() == "Windows" else "curl"

def fetch_page_sync(url: str, proxy: str = None) -> str:
    """Synchronously fetches the HTML content of a URL using curl with timeout, retries, and optional proxy."""
    cmd = [CURL_CMD, "-s", "--connect-timeout", "3", "-m", "2"]
    if proxy:
        cmd.extend(["-x", proxy])
    cmd.extend([url, "-H", f"User-Agent: {USER_AGENT}"])
    
    for attempt in range(3):
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=3
            )
            if res.returncode == 0:
                return res.stdout.decode('utf-8', errors='ignore')
        except Exception:
            pass
    return ""

async def fetch_page(url: str, sem: asyncio.Semaphore, proxy: str = None) -> str:
    """Fetches the HTML content of a URL using subprocess in a thread pool."""
    async with sem:
        return await asyncio.to_thread(fetch_page_sync, url, proxy)

def parse_page(html_content: str):
    """Parses accommodation items and pagination from the HTML page."""
    articles = re.findall(r'(<article[^>]*class="[^"]*accommodation-item[^"]*"[^>]*>[\s\S]*?</article>)', html_content)
    items = []
    
    for article in articles:
        tag_match = re.match(r'(<article[^>]*>)', article)
        if not tag_match:
            continue
        opening_tag = tag_match.group(1)
        
        attrs = dict(re.findall(r'data-([a-zA-Z0-9\-]+)="([^"]*)"', opening_tag))
        
        item_id = attrs.get('id') or attrs.get('item-id') or attrs.get('hotel-id')
        raw_name = attrs.get('hotel-name') or ""
        name = html.unescape(raw_name)
        category = attrs.get('hotel-type') or attrs.get('item-category')
        price = attrs.get('price')
        currency = attrs.get('currency')
        avg_rating = attrs.get('average-rating')
        rating_count = attrs.get('rating-count')
        score = attrs.get('score')
        
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
        
    pages_match = re.search(r'class="pagination-container__label"\s*>\s*\d+\s*/\s*(\d+)\s*</span>', html_content)
    total_pages = int(pages_match.group(1)) if pages_match else 1
    
    return items, total_pages

def check_cloudflare_block(html_content: str) -> bool:
    """Checks if the HTML content is a Cloudflare block page."""
    lowered = html_content.lower()
    return "cloudflare" in lowered and ("access denied" in lowered or "attention required" in lowered or "ray id" in lowered)

async def scrape_date_range(town_id: str, adults: int, checkin: str, checkout: str, sem: asyncio.Semaphore, proxy: str, progress_callback):
    """Scrapes only page 1 for a single checkin/checkout date range."""
    base_url = f"https://szallas.hu/{town_id}?adults={adults}&checkin={checkin}&checkout={checkout}&sort=CheapestPerPersonPerNightRate&sortdir=asc"
    
    html1 = await fetch_page(base_url, sem, proxy)
    if not html1:
        progress_callback(0, False)
        return []
        
    is_blocked = check_cloudflare_block(html1)
    if is_blocked:
        progress_callback(0, True)
        return []
        
    items, _ = parse_page(html1)
    for item in items:
        item['checkin'] = checkin
        item['checkout'] = checkout
        
    progress_callback(1, False)
    return items

async def run_scraper(town_id: str, adults: int, concurrency: int, proxy: str, progress_bar, status_text):
    """Runs the scraper for all 2-night stay combinations in August 2026."""
    sem = asyncio.Semaphore(concurrency)
    
    date_ranges = []
    for day in range(1, 30):
        checkin = f"2026-08-{day:02d}"
        checkout = f"2026-08-{(day+2):02d}"
        date_ranges.append((checkin, checkout))
        
    completed_ranges = 0
    total_requests_made = 0
    cf_blocked_detected = False
    
    def on_range_complete(requests_in_range, was_cf_blocked):
        nonlocal completed_ranges, total_requests_made, cf_blocked_detected
        completed_ranges += 1
        total_requests_made += requests_in_range
        if was_cf_blocked:
            cf_blocked_detected = True
        progress_bar.progress(completed_ranges / len(date_ranges))
        status_text.text(f"Scraped {completed_ranges}/{len(date_ranges)} date ranges... (Requests made: {total_requests_made})")

    tasks = [
        scrape_date_range(town_id, adults, checkin, checkout, sem, proxy, on_range_complete)
        for checkin, checkout in date_ranges
    ]
    
    results = await asyncio.gather(*tasks)
    
    all_items = []
    for r in results:
        all_items.extend(r)
        
    return all_items, total_requests_made, cf_blocked_detected

def main():
    st.title("🏨 Szallas.hu Scraper & Deal Finder")
    st.markdown("Scrape all 2-night accommodations in August 2026 concurrently to compare pricing and discover the best deals!")
    
    # Sidebar config
    st.sidebar.header("Scraping Parameters")
    town_id = st.sidebar.text_input("Town ID (szallas.hu path)", value="sopron").strip().lower()
    adults = st.sidebar.number_input("Number of Adults", min_value=1, max_value=10, value=2)
    concurrency = st.sidebar.slider("Max Concurrent Requests", min_value=1, max_value=50, value=15)
    proxy = st.sidebar.text_input("Proxy URL (Optional, e.g. http://host:port)", value="").strip()
    
    st.sidebar.markdown("""
    ---
    ### How to deploy to Streamlit Cloud
    1. Upload this codebase to GitHub.
    2. Go to [share.streamlit.io](https://share.streamlit.io).
    3. Link your repository and set `app.py` as the entrypoint.
    """)
    
    if st.sidebar.button("🚀 Start Scraping", use_container_width=True):
        if not town_id:
            st.error("Please enter a valid Town ID!")
            return
            
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        
        start_time = time.time()
        
        # Run async scraper in event loop
        with st.spinner("Scraping in progress..."):
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            all_scraped_items, total_requests, cf_blocked = loop.run_until_complete(
                run_scraper(town_id, adults, concurrency, proxy, progress_bar, status_text)
            )
            
        scrape_duration = time.time() - start_time
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
        
        if not all_scraped_items:
            if cf_blocked:
                st.error("🚫 **Cloudflare Bot Protection Detected**")
                st.info("""
                Szallas.hu blocked the requests because they originate from a cloud data center IP address (Streamlit Cloud).
                
                **How to fix:**
                1. **Run locally**: Run the application on your own computer where it uses your home residential IP:
                   `python -m streamlit run app.py`
                2. **Use a proxy**: Enter a valid residential proxy URL in the sidebar proxy input field to route requests through trusted IPs.
                """)
            else:
                st.error("No accommodations found. Please verify the Town ID or try again.")
            return
            
        # Start calculation timer
        calc_start_time = time.time()
        
        # Filter valid items
        df_all = pd.DataFrame(all_scraped_items)
        df_valid = df_all[df_all['price'].notna() & (df_all['price'] > 0)].copy()
        
        if df_valid.empty:
            st.warning("No accommodations with valid pricing (> 0 HUF) were found.")
            return
            
        # 1. Top 3 Cheapest Cards
        df_sorted = df_valid.sort_values(by='price')
        cheapest_3 = df_sorted.head(3)
        
        # 2. Price Chart over the Month
        df_trend = df_valid.groupby('checkin')['price'].min().reset_index()
        df_trend = df_trend.rename(columns={'checkin': 'Check-in Date', 'price': 'Cheapest Price (HUF)'})
        
        # 3. Complete Data Table
        df_display = df_valid[[
            'name', 'price', 'currency', 'checkin', 'checkout', 
            'average_rating', 'rating_count', 'category', 'latitude', 'longitude'
        ]].rename(columns={
            'name': 'Name',
            'price': 'Price',
            'currency': 'Currency',
            'checkin': 'Check-in',
            'checkout': 'Check-out',
            'average_rating': 'Rating',
            'rating_count': 'Ratings Count',
            'category': 'Category',
            'latitude': 'Latitude',
            'longitude': 'Longitude'
        })
        
        calc_duration = time.time() - calc_start_time
        total_duration = time.time() - start_time
        
        # Display Stats
        col1, col2, col3 = st.columns(3)
        col1.metric("Scraping time (Szállások letöltése)", f"{scrape_duration:.3f} s")
        col2.metric("Calculation time (Számítások, rendezés)", f"{calc_duration:.3f} s")
        col3.metric("Total time (Összes eltelt idő)", f"{total_duration:.3f} s")
        
        # 1. Top 3 Cheapest Cards Rendering
        st.markdown("## 🏷️ Top 3 Cheapest Stays Found")
        
        cols = st.columns(3)
        for idx, (_, item) in enumerate(cheapest_3.iterrows()):
            with cols[idx]:
                st.markdown(f"""
                <div class="card">
                    <h3>🏆 #{idx+1} {item['name']}</h3>
                    <p><b>Category:</b> {item['category']}</p>
                    <p><b>Rating:</b> {item['average_rating']} ({item['rating_count']} reviews)</p>
                    <p><b>Dates:</b> {item['checkin']} to {item['checkout']}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Render button
                href_val = item['href'] if pd.notna(item['href']) else ""
                url = f"https://szallas.hu/{href_val}?checkin={item['checkin']}&checkout={item['checkout']}"
                st.link_button(f"Book for {item['price']:.0f} {item['currency']}", url, use_container_width=True)
        
        # 2. Price Chart Rendering
        st.markdown("## 📈 Cheapest Price Trend by Checkin Date")
        st.line_chart(df_trend.set_index('Check-in Date'))
        
        # 3. Complete Data Table Rendering
        st.markdown("## 🔍 Browse All Offers")
        st.dataframe(df_display, use_container_width=True)

if __name__ == '__main__':
    main()
