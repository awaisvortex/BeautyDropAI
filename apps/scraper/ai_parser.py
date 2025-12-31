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
        }
    },
    "required": ["shop"]
}


SYSTEM_PROMPT = """You are an expert at extracting structured business information from website content.
Your task is to extract salon/beauty shop information including:

1. **Shop Details**: Name, description, full address (broken into components), phone, email, website
2. **Services**: List of services with names, descriptions, prices (as numbers), and duration in minutes
3. **Schedule**: Operating hours for each day of the week

IMPORTANT Guidelines:
- **Shop Name**: The business name is typically in the page title or header. Look for "Salon Name", "Business Name & Co.", etc.
- **Schedule**: Look for operating hours like "11am - 11pm" or "Monday - Sunday" patterns. If times like "11am-11pm Monday-Sunday" are found, apply the same hours to ALL 7 days.
- Extract as much information as you can find
- For prices, extract the numeric value only (e.g., 1500 not "Rs. 1,500" or "$45")
- For duration, assume 30 minutes if not specified, or convert to minutes (e.g., "1 hour" = 60)
- For schedule times, use 24-hour HH:MM format (e.g., "11:00", "23:00")
- If the schedule says "Monday - Sunday" with specific hours, create entries for ALL 7 days with those hours
- If a day is closed, set is_closed to true and omit times
- Country defaults to "Pakistan" if addresses contain Pakistani city names (Lahore, Karachi, etc.), otherwise "USA"
- Be thorough - extract ALL services you can find, even if they don't have complete info

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
    max_text_length = 15000  # Keep reasonable for token limits
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
            
            for img_url in service_images[:4]:  # Limit to 4 images to control costs
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
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,  # Low temperature for consistent extraction
            max_tokens=8000,  # Increased for more services
        )
        
        result_text = response.choices[0].message.content
        logger.info(f"AI response received ({len(result_text)} chars)")
        
        # Parse JSON response
        extracted_data = json.loads(result_text)
        
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
        'schedule': []
    }
    
    # Handle alternative shop key names
    shop_data = data.get('shop') or data.get('shop_details') or {}
    if shop_data:
        # Handle addresses array (use first address)
        address_parts = {}
        if 'addresses' in shop_data and shop_data['addresses']:
            first_addr = shop_data['addresses'][0]
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
        # Remove empty values
        cleaned['shop'] = {k: v for k, v in cleaned['shop'].items() if v}
    
    # Clean services
    for service in data.get('services', []):
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
    
    # Clean schedule - handle alternative key names
    valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    
    # Default times if not provided - use 09:00-21:00 as sensible defaults
    default_start = '09:00'
    default_end = '21:00'
    
    for entry in data.get('schedule', []):
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
    
    logger.info(f"Cleaned data: shop={bool(cleaned['shop'])}, services={len(cleaned['services'])}, schedule={len(cleaned['schedule'])}")
    
    return cleaned

