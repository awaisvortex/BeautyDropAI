"""
AI Parser Service - Uses OpenAI to extract structured shop data from scraped content

Extracts:
- Shop information (name, description, address, contact)
- Services with prices and durations
- Operating schedule
"""
import json
import logging
from typing import Optional

from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)


# Schema for extracted data - matches our Django models
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "shop": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Business/salon name"},
                "description": {"type": "string", "description": "Brief description of the business"},
                "address": {"type": "string", "description": "Full street address"},
                "city": {"type": "string", "description": "City name"},
                "state": {"type": "string", "description": "State/province"},
                "postal_code": {"type": "string", "description": "ZIP/postal code"},
                "country": {"type": "string", "description": "Country, default to USA if not found"},
                "phone": {"type": "string", "description": "Phone number"},
                "email": {"type": "string", "description": "Email address"},
                "website": {"type": "string", "description": "Website URL"},
            },
            "required": ["name"]
        },
        "services": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Service name"},
                    "description": {"type": "string", "description": "Service description"},
                    "price": {"type": "number", "description": "Price in dollars"},
                    "duration_minutes": {"type": "integer", "description": "Duration in minutes"},
                    "category": {"type": "string", "description": "Service category (e.g., Haircut, Color, Nails)"},
                },
                "required": ["name", "price", "duration_minutes"]
            }
        },
        "schedule": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "day_of_week": {
                        "type": "string",
                        "enum": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
                        "description": "Day of the week"
                    },
                    "start_time": {"type": "string", "description": "Opening time in HH:MM format (24-hour)"},
                    "end_time": {"type": "string", "description": "Closing time in HH:MM format (24-hour)"},
                    "is_closed": {"type": "boolean", "description": "True if closed on this day"},
                },
                "required": ["day_of_week"]
            }
        },
        "deals": {
            "type": "array",
            "description": "Special deals/packages that bundle multiple services at a discounted price",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Deal name (e.g., 'Deal 1', 'Winter Special', 'Bridal Package')"},
                    "price": {"type": "number", "description": "Bundle price as number"},
                    "included_items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of services/items included in this deal"
                    },
                    "description": {"type": "string", "description": "Optional description of the deal"}
                },
                "required": ["name", "price", "included_items"]
            }
        }
    },
    "required": ["shop"]
}


SYSTEM_PROMPT = """You are an expert at extracting structured business information from website content.
You will be provided with website content in **Markdown** format (parsed from HTML).
You may also receive **SCREENSHOT IMAGES** of service/menu pages - extract ALL service information visible in these images.

Your task is to extract salon/beauty shop information including:

1. **Shop Details**: Name, description, full address (broken into components), phone, email, website
2. **Services**: List of ALL services with names, descriptions, prices (as numbers), and duration in minutes
3. **Schedule**: Operating hours for each day of the week - THIS IS CRITICAL
4. **Deals/Packages**: Special bundled offers with multiple services at a discounted price

IMPORTANT Guidelines:
- **Shop Name**: The business name is typically in the page title or header 1 (# Header). Look for "Salon Name", "Business Name & Co.", etc.

- **Services Extraction (CRITICAL - Extract ALL Services)**:
  - **From Category Pages**: When you see a heading like "Manicure Services" followed by bullet points:
    - The HEADING becomes the CATEGORY (e.g., "Manicure")
    - Each BULLET POINT becomes a separate SERVICE (e.g., "Nail Cutting", "Nail Filing And Shaping")
    - Example: "Manicure Services" section with bullets → multiple services with category="Manicure"
  - **Standalone Services**: If a heading like "Acrylic Nails" or "Body Waxing" has NO sub-bullets, it IS ITSELF a service
  - **From Images**: Carefully examine screenshots for service menus, price lists, treatment cards
  - **From Deal Items (IMPORTANT)**: Each item listed in a deal is ALSO a service. For example:
    - Deal says "Hair Cut + Blow Dry + Manicure" → Add "Hair Cut", "Blow Dry", "Manicure" as separate services
    - Student Deal includes "Whitening Mani, Whitening Pedi" → Add "Whitening Mani", "Whitening Pedi" as services
  - Extract EVERY service visible in images, text, AND deal items for the complete list
  - **If no price is visible, use 0 as the price - don't skip the service!**
  - **GOAL: You should typically extract 20+ services from a salon website. Extract EVERYTHING!**

- **Deals/Packages (IMPORTANT)**:
  - Look for "Deal 1", "Deal 2", "Package", "Special Offer", "Combo", "Bridal Package", "Winter Special", etc.
  - **DEALS ARE OFTEN DISPLAYED AS IMAGES/CARDS** showing bundled services with a special price
  - In homepage image galleries, look for deal cards with text like:
    - "Deal 1: Hair Cut + Blowdry + Manicure = Rs. 2500"
    - "Winter Freshness Package" with listed services
  - Extract the deal NAME (e.g., "Deal 1", "Winter Freshness")
  - Extract the bundle PRICE (the total price for the deal)
  - Extract ALL included_items - the list of services/treatments in the deal

- **Schedule/Opening Hours**: 
  - CRITICAL: Look carefully in the FOOTER section for "Opening hours", "Business hours", "Hours of operation", etc.
  - Common patterns: "Mon - Sun: 10 AM - 9 PM", "Monday-Sunday 11am-11pm", "Open 7 days 10:00-21:00"
  - If you find "10 AM - 9 PM", convert to 24-hour format: start_time="10:00", end_time="21:00"
  - If hours apply to all days (e.g., "Mon - Sun"), create entries for ALL 7 days with those SPECIFIC hours
  - NEVER leave start_time or end_time empty if hours are mentioned anywhere on the page
  - Check footer, contact page, and sidebar for hours information
  
- Extract as much information as you can find
- For prices, extract the numeric value only (e.g., 1500 not "Rs. 1,500" or "$45")
- For duration, assume 30 minutes if not specified, or convert to minutes (e.g., "1 hour" = 60)
- For schedule times, ALWAYS use 24-hour HH:MM format (e.g., "10:00", "21:00")
- If a day is closed, set is_closed to true and omit times
- Country defaults to "Pakistan" if addresses contain Pakistani city names (Lahore, Karachi, etc.), otherwise "USA"
- Be thorough - extract ALL services AND deals you can find from BOTH images and text

Return ONLY valid JSON matching the specified schema."""


def parse_with_ai(scraped_data: dict) -> dict:
    """
    Use OpenAI to extract structured shop data from scraped content.
    
    Args:
        scraped_data: Dict containing scraped content (text_content, schema_data, etc.)
        
    Returns:
        Structured data matching EXTRACTION_SCHEMA
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    # Prepare content for AI
    content_parts = []
    
    # Add page title and meta - EXPLICITLY highlight as business name source
    title = scraped_data.get('title', '')
    if title:
        # Extract likely business name from title (before dash or pipe)
        business_name = title.split(' - ')[0].split(' | ')[0].strip()
        content_parts.append(f"BUSINESS NAME (from page title): {business_name}")
        content_parts.append(f"Full Page Title: {title}")
    
    if scraped_data.get('meta_description'):
        content_parts.append(f"Description: {scraped_data['meta_description']}")
    
    # Add schema.org data if present (very useful!)
    if scraped_data.get('schema_data'):
        content_parts.append(f"Structured Data (Schema.org): {json.dumps(scraped_data['schema_data'], indent=2)}")
    
    # Add contact info with EXPLICIT operating hours
    contact_info = scraped_data.get('contact_info', {})
    if contact_info:
        content_parts.append(f"Contact Info Found: {json.dumps(contact_info)}")
        
        # Explicitly highlight operating hours if found
        hours_hints = contact_info.get('hours_hints', [])
        if hours_hints:
            content_parts.append(f"\n*** OPERATING HOURS DETECTED: {hours_hints} ***")
            content_parts.append("If hours show something like '11am-11pm Monday-Sunday', create schedule for ALL 7 days.")
    
    # Add source URL
    if scraped_data.get('source_url'):
        content_parts.append(f"Source URL: {scraped_data['source_url']}")
    
    # Add list of pages scraped
    if scraped_data.get('pages_scraped'):
        content_parts.append(f"Pages Scraped: {scraped_data['pages_scraped']}")
    
    # Add main text content (truncated if needed)
    text_content = scraped_data.get('text_content', '')
    max_text_length = 50000  # Increased to handle full page with footer (for schedule)
    if len(text_content) > max_text_length:
        text_content = text_content[:max_text_length] + "\n... [content truncated]"
    content_parts.append(f"\nPage Content:\n{text_content}")
    
    full_content = "\n\n".join(content_parts)
    
    # Get service menu images if available
    service_images = scraped_data.get('service_menu_images', [])
    
    logger.info(f"Sending content to AI for parsing ({len(full_content)} chars, {len(service_images)} images)")
    
    try:
        # Build message content with optional images
        user_content = []
        
        # Add images first if available (GPT-4 Vision)
        if service_images:
            user_content.append({
                "type": "text",
                "text": "I'm providing service/price menu images from a salon website. Extract ALL services with their prices from these images. Also extract shop info and schedule from the text content below."
            })
            
            # Send up to 10 images to capture all service menu sections
            for img_url in service_images[:10]:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": img_url, "detail": "high"}
                })
            
            user_content.append({
                "type": "text",
                "text": f"\n\nAdditional website text content:\n\n{full_content}"
            })
        else:
            user_content.append({
                "type": "text",
                "text": f"Extract shop information from this website content:\n\n{full_content}"
            })
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=16000,  # Increased for 100+ services
            )
        except Exception as img_error:
            # If image processing failed, retry without images
            if service_images and "image" in str(img_error).lower():
                logger.warning(f"Image processing failed, retrying without images: {img_error}")
                user_content = [{
                    "type": "text",
                    "text": f"Extract shop information from this website content:\n\n{full_content}"
                }]
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=16000,
                )
            else:
                raise
        
        result_text = response.choices[0].message.content
        logger.info(f"AI response received ({len(result_text)} chars)")
        
        # Parse JSON response
        extracted_data = json.loads(result_text)
        
        # Debug: log the structure of the response
        logger.info(f"AI response type: {type(extracted_data)}, keys: {list(extracted_data.keys()) if isinstance(extracted_data, dict) else 'not a dict'}")
        
        # Validate and clean the data
        extracted_data = validate_and_clean(extracted_data)
        
        return extracted_data
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}")
        raise ValueError(f"AI returned invalid JSON: {e}")
    except Exception as e:
        logger.error(f"AI parsing failed: {e}")
        raise


def validate_and_clean(data: dict) -> dict:
    """
    Validate and clean extracted data to match our model requirements.
    Handles alternative key names from AI responses.
    
    Args:
        data: Raw extracted data from AI
        
    Returns:
        Cleaned data ready for model creation
    """
    cleaned = {
        'shop': {},
        'services': [],
        'deals': [],
        'schedule': []
    }
    
    # Defensive: ensure data is a dict
    if not isinstance(data, dict):
        logger.warning(f"AI returned non-dict data type: {type(data)}")
        return cleaned
    
    # Handle alternative shop key names
    shop_data = data.get('shop') or data.get('shop_details') or {}
    
    # Defensive: ensure shop_data is a dict
    if not isinstance(shop_data, dict):
        logger.warning(f"Shop data is not a dict: {type(shop_data)}")
        shop_data = {}
        
    if shop_data:
        # Handle addresses array (use first address)
        address_parts = {}
        addresses = shop_data.get('addresses', [])
        if isinstance(addresses, list) and addresses:
            first_addr = addresses[0] if isinstance(addresses[0], dict) else {}
            address_parts = {
                'address': first_addr.get('street_address', first_addr.get('address', '')),
                'city': first_addr.get('city', ''),
                'state': first_addr.get('state', ''),
                'postal_code': first_addr.get('postal_code', first_addr.get('zip', '')),
                'country': first_addr.get('country', 'Pakistan'),
            }
        
        cleaned['shop'] = {
            'name': str(shop_data.get('name', '')).strip()[:255],
            'description': str(shop_data.get('description', '')).strip(),
            'address': str(address_parts.get('address') or shop_data.get('address', '')).strip()[:500],
            'city': str(address_parts.get('city') or shop_data.get('city', '')).strip()[:100],
            'state': str(address_parts.get('state') or shop_data.get('state', '')).strip()[:100],
            'postal_code': str(address_parts.get('postal_code') or shop_data.get('postal_code', '')).strip()[:20],
            'country': str(address_parts.get('country') or shop_data.get('country', 'Pakistan')).strip()[:100],
            'phone': str(shop_data.get('phone', '')).strip()[:20],
            'email': str(shop_data.get('email', '')).strip(),
            'website': str(shop_data.get('website', '')).strip(),
        }
        
        # Infer timezone from country and city
        country = cleaned['shop'].get('country', '').lower()
        city = cleaned['shop'].get('city', '').lower()
        
        # Country-based timezone mapping
        country_timezone_map = {
            'pakistan': 'Asia/Karachi',
            'india': 'Asia/Kolkata',
            'uae': 'Asia/Dubai',
            'united arab emirates': 'Asia/Dubai',
            'saudi arabia': 'Asia/Riyadh',
            'uk': 'Europe/London',
            'united kingdom': 'Europe/London',
            'canada': 'America/Toronto',
            'australia': 'Australia/Sydney',
        }
        
        # US city-based timezone mapping
        us_city_timezone_map = {
            'new york': 'America/New_York',
            'los angeles': 'America/Los_Angeles',
            'chicago': 'America/Chicago',
            'houston': 'America/Chicago',
            'phoenix': 'America/Phoenix',
            'philadelphia': 'America/New_York',
            'san antonio': 'America/Chicago',
            'san diego': 'America/Los_Angeles',
            'dallas': 'America/Chicago',
            'san francisco': 'America/Los_Angeles',
            'austin': 'America/Chicago',
            'seattle': 'America/Los_Angeles',
            'denver': 'America/Denver',
            'boston': 'America/New_York',
            'miami': 'America/New_York',
            'atlanta': 'America/New_York',
        }
        
        timezone = 'UTC'  # Default fallback
        
        if country in country_timezone_map:
            timezone = country_timezone_map[country]
        elif country in ['usa', 'united states', 'us', 'america']:
            # Check city for US
            for us_city, tz in us_city_timezone_map.items():
                if us_city in city:
                    timezone = tz
                    break
            else:
                timezone = 'America/New_York'  # Default for US
        
        cleaned['shop']['timezone'] = timezone
        
        # Remove empty values
        cleaned['shop'] = {k: v for k, v in cleaned['shop'].items() if v}
    
    # Clean services - handle both dict and malformed data
    services_data = data.get('services', [])
    if not isinstance(services_data, list):
        logger.warning(f"Services is not a list: {type(services_data)}")
        services_data = []
    
    logger.info(f"Processing {len(services_data)} raw services from AI response")
    
    for service in services_data:
        # Convert string services to dict format (AI sometimes just returns service names)
        if isinstance(service, str):
            service = {'name': service, 'price': 0, 'duration_minutes': 30}
        
        # Skip non-dict entries after conversion attempt
        if not isinstance(service, dict):
            continue
            
        if not service.get('name'):
            continue
            
        try:
            price = float(service.get('price', 0))
            duration = int(service.get('duration_minutes') or service.get('duration') or 30)
        except (ValueError, TypeError):
            price = 0
            duration = 30
            
        cleaned['services'].append({
            'name': str(service.get('name', '')).strip()[:255],
            'description': str(service.get('description', '')).strip(),
            'price': max(0, price),
            'duration_minutes': max(15, min(480, duration)),  # 15 min to 8 hours
            'category': str(service.get('category', '')).strip()[:100],
        })
    
    # Clean deals
    deals_data = data.get('deals', [])
    if not isinstance(deals_data, list):
        deals_data = []
    
    logger.info(f"Processing {len(deals_data)} raw deals from AI response")
        
    for deal in deals_data:
        # Skip non-dict entries
        if not isinstance(deal, dict):
            logger.debug(f"Skipping non-dict deal: {type(deal)}")
            continue
        
        # Log the deal structure for debugging
        logger.debug(f"Deal keys: {deal.keys()}, deal: {deal}")
            
        # Deal must have a name
        if not deal.get('name'):
            logger.debug(f"Skipping deal without name: {deal}")
            continue
        
        # Get included items - handle alternative key names
        # AI might use 'items', 'services', 'included_services' instead of 'included_items'
        included_items = (
            deal.get('included_items') or 
            deal.get('items') or 
            deal.get('services') or 
            deal.get('included_services') or
            []
        )
        
        if not isinstance(included_items, list):
            included_items = [str(included_items)]  # Convert to list if string
        
        # Filter empty items and convert to strings
        included_items = [str(item).strip() for item in included_items if item]
        
        # If no included items, skip this deal
        if not included_items:
            logger.debug(f"Skipping deal '{deal.get('name')}' - no included items found")
            continue
            
        try:
            price = float(deal.get('price', 0))
        except (ValueError, TypeError):
            price = 0
            
        cleaned['deals'].append({
            'name': str(deal.get('name', '')).strip()[:255],
            'description': str(deal.get('description', '')).strip(),
            'price': max(0, price),
            'included_items': included_items,
        })
        logger.info(f"Added deal: {deal.get('name')} with {len(included_items)} items")
    
    # Clean schedule - handle alternative key names
    valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    
    # Default times if not provided - use 09:00-21:00 as sensible defaults
    default_start = '09:00'
    default_end = '21:00'
    
    # Defensive: ensure schedule is a list
    schedule_data = data.get('schedule', [])
    if not isinstance(schedule_data, list):
        logger.warning(f"Schedule is not a list: {type(schedule_data)}")
        schedule_data = []
    
    for entry in schedule_data:
        # Defensive: skip non-dict entries
        if not isinstance(entry, dict):
            logger.debug(f"Skipping non-dict schedule entry: {type(entry)}")
            continue
            
        # Handle alternative day key names
        day = str(entry.get('day_of_week') or entry.get('day', '')).lower().strip()
        if day not in valid_days:
            continue
            
        schedule_entry = {
            'day_of_week': day,
            'is_closed': bool(entry.get('is_closed', False)),
        }
        
        if not schedule_entry['is_closed']:
            # Handle alternative time key names
            start_time = str(entry.get('start_time') or entry.get('open_time') or entry.get('opening_time', '')).strip()
            end_time = str(entry.get('end_time') or entry.get('close_time') or entry.get('closing_time', '')).strip()
            
            # Use default times if not provided
            if not start_time:
                start_time = default_start
            if not end_time:
                end_time = default_end
            
            schedule_entry['start_time'] = start_time
            schedule_entry['end_time'] = end_time
        
        cleaned['schedule'].append(schedule_entry)
    
    # FALLBACK: If no schedule was extracted, generate a default 7-day schedule
    # This ensures shops always have operating hours
    if not cleaned['schedule']:
        logger.warning("No schedule extracted from content, generating default 7-day schedule")
        for day in valid_days:
            cleaned['schedule'].append({
                'day_of_week': day,
                'start_time': default_start,
                'end_time': default_end,
                'is_closed': False,
            })
    
    logger.info(f"Cleaned data: shop={bool(cleaned['shop'])}, services={len(cleaned['services'])}, deals={len(cleaned['deals'])}, schedule={len(cleaned['schedule'])}")
    
    return cleaned

