"""
Web scraping service - handles fetching and parsing website content

Supports:
- Multi-page crawling (homepage + services/contact/about pages)
- Generic website scraping
- Platform-specific scrapers for Google Business, Yelp, Booksy, StyleSeat, Vagaro
"""
import re
import json
import logging
import asyncio
from typing import Optional, Tuple, List, Set
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# Platform detection patterns
PLATFORM_PATTERNS = {
    'google_business': [
        r'google\.com/maps',
        r'maps\.google\.com',
        r'g\.page',
    ],
    'yelp': [
        r'yelp\.com',
        r'yelp\.[a-z]{2}',
    ],
    'booksy': [
        r'booksy\.com',
    ],
    'styleseat': [
        r'styleseat\.com',
    ],
    'vagaro': [
        r'vagaro\.com',
    ],
}

# Keywords to identify important pages for salon/service info
IMPORTANT_PAGE_KEYWORDS = [
    'service', 'services', 'menu', 'price', 'pricing', 'prices',
    'treatment', 'treatments', 'book', 'booking', 'appointment',
    'contact', 'about', 'hours', 'location', 'our-services',
]


class ScraperError(Exception):
    """Custom exception for scraping errors"""
    pass


def detect_platform(url: str) -> str:
    """
    Detect which platform a URL belongs to.
    
    Args:
        url: The URL to analyze
        
    Returns:
        Platform name (e.g., 'google_business', 'yelp') or 'generic'
    """
    url_lower = url.lower()
    
    for platform, patterns in PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url_lower):
                return platform
    
    return 'generic'


async def fetch_url_content(url: str, timeout: int = 30) -> str:
    """
    Fetch raw HTML content from a URL.
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        
    Returns:
        Raw HTML content
        
    Raises:
        ScraperError: If fetching fails
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        # Don't specify Accept-Encoding - let httpx handle decompression automatically
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers=headers,
            http2=False,  # Use HTTP/1.1 for better compatibility
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # Ensure we get text content, not binary
            content = response.text
            
            # Log content info for debugging
            logger.info(f"Fetched {len(content)} chars from {url}")
            
            return content
            
    except httpx.TimeoutException:
        raise ScraperError(f"Request timed out after {timeout} seconds")
    except httpx.HTTPStatusError as e:
        raise ScraperError(f"HTTP error {e.response.status_code}: {e.response.reason_phrase}")
    except httpx.RequestError as e:
        raise ScraperError(f"Request failed: {str(e)}")


def extract_text_content(html: str) -> str:
    """
    Extract readable text content from HTML.
    
    Args:
        html: Raw HTML string
        
    Returns:
        Cleaned text content
    """
    soup = BeautifulSoup(html, 'lxml')
    
    # Remove script and style elements
    for element in soup(['script', 'style', 'nav', 'footer', 'aside']):
        element.decompose()
    
    # Get text
    text = soup.get_text(separator='\n', strip=True)
    
    # Clean up whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = '\n'.join(lines)
    
    return text


def find_service_menu_images(html: str, base_url: str) -> List[str]:
    """
    Find URLs of images that likely contain service menus/price lists.
    
    Args:
        html: HTML content
        base_url: Base URL for resolving relative URLs
        
    Returns:
        List of image URLs that appear to be service menus
    """
    soup = BeautifulSoup(html, 'lxml')
    menu_images = []
    
    # Keywords that suggest service/price menu images
    menu_keywords = [
        'service', 'price', 'menu', 'haircut', 'facial', 'massage',
        'treatment', 'styling', 'manicure', 'pedicure', 'waxing',
        'body-care', 'hair-treatment', 'beard', 'mani-pedi'
    ]
    
    for img in soup.find_all('img', src=True):
        src = img.get('src', '')
        alt = img.get('alt', '').lower()
        
        # Check if image URL or alt text contains menu-related keywords
        src_lower = src.lower()
        is_menu_image = any(keyword in src_lower or keyword in alt for keyword in menu_keywords)
        
        # Also check for large images (likely content, not icons)
        width = img.get('width', '')
        height = img.get('height', '')
        is_large = False
        try:
            if (width and int(width) >= 400) or (height and int(height) >= 400):
                is_large = True
        except ValueError:
            pass
        
        if is_menu_image or (is_large and 'logo' not in src_lower and 'icon' not in src_lower):
            # Resolve to absolute URL
            full_url = urljoin(base_url, src)
            
            # Filter out obviously non-menu images
            if '.png' in full_url or '.jpg' in full_url or '.jpeg' in full_url:
                if 'logo' not in full_url.lower() and 'icon' not in full_url.lower():
                    menu_images.append(full_url)
    
    # Deduplicate while preserving order
    seen = set()
    unique_images = []
    for url in menu_images:
        if url not in seen:
            seen.add(url)
            unique_images.append(url)
    
    logger.info(f"Found {len(unique_images)} potential service menu images")
    return unique_images[:6]  # Limit to 6 images


def find_important_links(html: str, base_url: str) -> List[str]:
    """
    Find links to important pages (services, contact, about, etc.)
    
    Args:
        html: HTML content
        base_url: Base URL for resolving relative links
        
    Returns:
        List of absolute URLs to important pages
    """
    soup = BeautifulSoup(html, 'lxml')
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc
    
    important_links = set()
    
    for link in soup.find_all('a', href=True):
        href = link.get('href', '').strip()
        link_text = link.get_text(strip=True).lower()
        
        if not href or href.startswith('#') or href.startswith('javascript:'):
            continue
        
        # Resolve relative URLs
        full_url = urljoin(base_url, href)
        parsed_url = urlparse(full_url)
        
        # Only follow links on the same domain
        if parsed_url.netloc != base_domain:
            continue
        
        # Check if link text or URL contains important keywords
        href_lower = href.lower()
        is_important = any(
            keyword in href_lower or keyword in link_text
            for keyword in IMPORTANT_PAGE_KEYWORDS
        )
        
        if is_important:
            # Normalize URL (remove trailing slash, fragment)
            normalized = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
            if normalized.endswith('/'):
                normalized = normalized[:-1]
            important_links.add(normalized)
    
    logger.info(f"Found {len(important_links)} important links: {list(important_links)[:5]}")
    return list(important_links)[:5]  # Limit to 5 subpages


def extract_structured_html(html: str, source_url: str = '') -> dict:
    """
    Extract structured data from HTML including meta tags, schema.org data, etc.
    
    Args:
        html: Raw HTML string
        source_url: The source URL for context
        
    Returns:
        Dict with structured data found in the page
    """
    soup = BeautifulSoup(html, 'lxml')
    data = {
        'title': '',
        'meta_description': '',
        'schema_data': [],
        'contact_info': {},
        'text_content': '',
    }
    
    # Title
    title_tag = soup.find('title')
    if title_tag:
        data['title'] = title_tag.get_text(strip=True)
    
    # Meta description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc:
        data['meta_description'] = meta_desc.get('content', '')
    
    # Schema.org JSON-LD data
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            schema = json.loads(script.string)
            data['schema_data'].append(schema)
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Extract phone numbers
    page_text = soup.get_text()
    phone_pattern = r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}'
    phones = re.findall(phone_pattern, page_text)
    if phones:
        # Filter to likely phone numbers (at least 10 digits)
        valid_phones = [p for p in phones if len(re.sub(r'\D', '', p)) >= 10]
        if valid_phones:
            data['contact_info']['phones'] = valid_phones[:3]  # Max 3
    
    # Extract emails
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, page_text)
    if emails:
        data['contact_info']['emails'] = list(set(emails))[:3]  # Max 3, unique
    
    # Extract operating hours patterns (common formats)
    hours_patterns = [
        r'(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))\s*[-–to]+\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))',
        r'(\d{1,2}:\d{2})\s*[-–to]+\s*(\d{1,2}:\d{2})',
        r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[:\s]+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)',
    ]
    hours_found = []
    for pattern in hours_patterns:
        matches = re.findall(pattern, page_text, re.IGNORECASE)
        hours_found.extend(matches)
    if hours_found:
        data['contact_info']['hours_hints'] = hours_found[:10]
    
    # Text content
    data['text_content'] = extract_text_content(html)
    
    return data


async def scrape_multiple_pages(base_url: str, max_pages: int = 5) -> dict:
    """
    Scrape the main page and important subpages.
    
    Args:
        base_url: The starting URL
        max_pages: Maximum number of pages to scrape
        
    Returns:
        Combined structured data from all pages
    """
    logger.info(f"Starting multi-page scrape from: {base_url}")
    
    # Fetch main page
    main_html = await fetch_url_content(base_url)
    main_data = extract_structured_html(main_html, base_url)
    main_data['source_url'] = base_url
    
    # Find important links
    important_links = find_important_links(main_html, base_url)
    
    # Combine all content
    combined_data = {
        'title': main_data['title'],
        'meta_description': main_data['meta_description'],
        'schema_data': main_data['schema_data'],
        'contact_info': main_data['contact_info'],
        'text_content': f"=== MAIN PAGE ({base_url}) ===\n{main_data['text_content']}\n\n",
        'source_url': base_url,
        'pages_scraped': [base_url],
    }
    
    # Fetch subpages concurrently
    async def fetch_subpage(url: str) -> tuple:
        try:
            html = await fetch_url_content(url, timeout=15)
            return url, html, extract_structured_html(html, url)
        except Exception as e:
            logger.warning(f"Failed to fetch subpage {url}: {e}")
            return url, None, None
    
    # Limit concurrent requests
    subpage_tasks = [fetch_subpage(url) for url in important_links[:max_pages-1]]
    subpage_results = await asyncio.gather(*subpage_tasks)
    
    # Collect service menu images
    all_menu_images = []
    
    for url, html, data in subpage_results:
        if data:
            combined_data['pages_scraped'].append(url)
            
            # Add subpage text content with header
            page_name = url.split('/')[-1] or 'page'
            combined_data['text_content'] += f"=== {page_name.upper()} PAGE ({url}) ===\n{data['text_content']}\n\n"
            
            # Merge schema data
            combined_data['schema_data'].extend(data.get('schema_data', []))
            
            # Merge contact info
            for key, value in data.get('contact_info', {}).items():
                if key not in combined_data['contact_info']:
                    combined_data['contact_info'][key] = value
                elif isinstance(value, list):
                    # Merge and dedupe lists
                    existing = combined_data['contact_info'][key]
                    combined_data['contact_info'][key] = list(set(existing + value))
            
            # Find service menu images from this page
            if html and ('service' in url.lower() or 'menu' in url.lower() or 'price' in url.lower()):
                page_images = find_service_menu_images(html, url)
                all_menu_images.extend(page_images)
    
    # Deduplicate menu images
    seen = set()
    unique_images = []
    for img_url in all_menu_images:
        if img_url not in seen:
            seen.add(img_url)
            unique_images.append(img_url)
    
    combined_data['service_menu_images'] = unique_images[:6]  # Limit to 6
    logger.info(f"Scraped {len(combined_data['pages_scraped'])} pages total, found {len(combined_data['service_menu_images'])} menu images")
    
    return combined_data


async def scrape_website(url: str) -> Tuple[str, dict]:
    """
    Main scraping function - fetches URL and important subpages, extracts content.
    
    Args:
        url: URL to scrape
        
    Returns:
        Tuple of (platform, extracted_data)
    """
    logger.info(f"Scraping URL: {url}")
    
    # Detect platform
    platform = detect_platform(url)
    logger.info(f"Detected platform: {platform}")
    
    # For generic websites, do multi-page scraping
    if platform == 'generic':
        structured_data = await scrape_multiple_pages(url, max_pages=5)
    else:
        # For known platforms, just scrape the single page
        html = await fetch_url_content(url)
        structured_data = extract_structured_html(html, url)
        structured_data['source_url'] = url
        structured_data['pages_scraped'] = [url]
    
    structured_data['platform'] = platform
    
    return platform, structured_data


# Synchronous wrapper for Celery
def scrape_website_sync(url: str) -> Tuple[str, dict]:
    """
    Synchronous wrapper for scrape_website.
    Use this in Celery tasks.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(scrape_website(url))
