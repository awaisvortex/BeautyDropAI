"""
Shop and service-related tools for the AI agent.
"""
from typing import Any, Dict
from django.db.models import Q
from .base import BaseTool


class SearchShopsTool(BaseTool):
    """Search for shops."""
    
    name = "search_shops"
    description = """
    Search for shops by name, city, or service type.
    Returns shop IDs that can be used with other shop tools.
    ALWAYS use this first to get shop IDs before calling get_shop_info, get_shop_services, etc.
    """
    allowed_roles = ["customer", "client", "staff", "guest"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (shop name, city, or service type)"
                },
                "city": {
                    "type": "string",
                    "description": "Optional: Filter by city"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results. Default: 10"
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.agent.services.embedding_service import EmbeddingService
        from apps.agent.services.pinecone_service import PineconeService
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            query = kwargs.get('query', '')
            city = kwargs.get('city', '')
            limit = min(kwargs.get('limit', 10), 20)
            
            logger.info(f"search_shops called with query='{query}', city='{city}'")
            
            # If no query, return all shops
            if not query and not city:
                shops = Shop.objects.filter(is_active=True).order_by('-average_rating')[:limit]
                shop_list = self._format_shops(shops)
                logger.info(f"search_shops (no query) found {len(shop_list)} shops")
                return {"success": True, "count": len(shop_list), "shops": shop_list}
            
            # Use semantic search with Pinecone
            try:
                embedding_service = EmbeddingService()
                pinecone_service = PineconeService()
                
                # Generate embedding for query
                query_embedding = embedding_service.get_embedding(query)
                
                # Build metadata filter for city if provided
                metadata_filter = None
                if city:
                    metadata_filter = {"city": {"$eq": city}}
                
                # Search in Pinecone
                results = pinecone_service.query(
                    embedding=query_embedding,
                    namespace=PineconeService.NAMESPACE_SHOPS,
                    top_k=limit,
                    filter=metadata_filter,
                    min_score=0.2  # Lower threshold for broader matches
                )
                
                logger.info(f"Pinecone returned {len(results)} semantic matches")
                
                if results:
                    # Get shop IDs from Pinecone results
                    shop_ids = [r['id'] for r in results]
                    shops = Shop.objects.filter(id__in=shop_ids, is_active=True)
                    
                    # Maintain Pinecone's relevance ordering
                    shop_dict = {str(s.id): s for s in shops}
                    ordered_shops = [shop_dict[sid] for sid in shop_ids if sid in shop_dict]
                    
                    shop_list = self._format_shops(ordered_shops)
                    logger.info(f"search_shops (semantic) found {len(shop_list)} shops")
                    return {"success": True, "count": len(shop_list), "shops": shop_list, "search_type": "semantic"}
                
            except Exception as e:
                logger.warning(f"Semantic search failed, falling back to keyword: {e}")
            
            # Fallback to keyword search
            shops = Shop.objects.filter(is_active=True)
            if query:
                from django.db.models import Q
                shops = shops.filter(
                    Q(name__icontains=query) |
                    Q(description__icontains=query) |
                    Q(city__icontains=query) |
                    Q(services__name__icontains=query) |
                    Q(services__category__icontains=query)
                ).distinct()
            if city:
                shops = shops.filter(city__icontains=city)
            
            shops = shops.order_by('-average_rating')[:limit]
            shop_list = self._format_shops(shops)
            logger.info(f"search_shops (keyword fallback) found {len(shop_list)} shops")
            return {"success": True, "count": len(shop_list), "shops": shop_list, "search_type": "keyword"}
            
        except Exception as e:
            logger.error(f"search_shops error: {e}")
            return {"success": False, "error": str(e)}
    
    def _format_shops(self, shops) -> list:
        """Format shop queryset to list of dicts."""
        return [
            {
                "id": str(s.id),
                "name": s.name,
                "city": s.city,
                "address": s.address,
                "rating": float(s.average_rating),
                "total_reviews": s.total_reviews,
                "is_verified": s.is_verified
            }
            for s in shops
        ]


class GetMyShopsTool(BaseTool):
    """Get shops owned by the current client."""
    
    name = "get_my_shops"
    description = """
    Get all shops owned/managed by the current client/shop owner.
    Returns a list of shops with their basic info.
    Use this to answer questions like 'how many shops do I have', 'list my shops', etc.
    Always list ALL shops returned by this tool in your response.
    If there are more than 5 shops, mention the total count and suggest visiting the shop browsing page to see all.
    """
    allowed_roles = ["client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "include_inactive": {
                    "type": "boolean",
                    "description": "Include inactive shops. Default: False"
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.clients.models import Client
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            client = Client.objects.get(user=user)
            
            include_inactive = kwargs.get('include_inactive', False)
            
            if include_inactive:
                shops = Shop.objects.filter(client=client)
            else:
                shops = Shop.objects.filter(client=client, is_active=True)
            
            total_count = shops.count()
            shops = shops.order_by('-created_at')[:5]  # Limit to 5 for display
            
            shop_list = []
            for s in shops:
                shop_list.append({
                    "id": str(s.id),
                    "name": s.name,
                    "address": s.address,
                    "city": s.city,
                    "phone": s.phone,
                    "is_active": s.is_active,
                    "is_verified": s.is_verified,
                    "average_rating": float(s.average_rating),
                    "total_reviews": s.total_reviews,
                    "created_at": s.created_at.isoformat() if s.created_at else None
                })
            
            logger.info(f"get_my_shops found {total_count} shops for client {client.id}")
            
            return {
                "success": True,
                "total_count": total_count,
                "showing": len(shop_list),
                "has_more": total_count > 5,
                "shops": shop_list,
                "message": f"You have {total_count} shop(s) set up." if total_count > 0 else "You haven't set up any shops yet."
            }
            
        except Client.DoesNotExist:
            return {"success": False, "error": "Client profile not found"}
        except Exception as e:
            logger.error(f"get_my_shops error: {e}")
            return {"success": False, "error": str(e)}


class GetShopInfoTool(BaseTool):
    """Get detailed shop information."""
    
    name = "get_shop_info"
    description = """
    Get detailed information about a specific shop.
    Includes location, contact, hours, and ratings.
    Requires shop_id (UUID) - use search_shops first to get the ID.
    """
    allowed_roles = ["customer", "client", "staff", "guest"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "shop_id": {
                    "type": "string",
                    "description": "UUID of the shop (get this from search_shops first)"
                },
                "shop_name": {
                    "type": "string",
                    "description": "Alternative: Shop name if UUID not available"
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.schedules.models import ShopSchedule
        
        try:
            # Try UUID first, then fall back to name search
            shop_id = kwargs.get('shop_id')
            shop_name = kwargs.get('shop_name')
            
            if shop_id:
                try:
                    shop = Shop.objects.get(id=shop_id, is_active=True)
                except (Shop.DoesNotExist, Exception):
                    # If UUID fails, try as name
                    shop = Shop.objects.filter(name__icontains=shop_id, is_active=True).first()
            elif shop_name:
                shop = Shop.objects.filter(name__icontains=shop_name, is_active=True).first()
            else:
                return {"success": False, "error": "Please provide shop_id or shop_name"}
            
            if not shop:
                return {"success": False, "error": "Shop not found"}
            
            # Get schedule
            schedules = ShopSchedule.objects.filter(shop=shop, is_active=True)
            hours = {}
            for s in schedules:
                hours[s.day_of_week] = {
                    "open": s.start_time.strftime("%I:%M %p"),
                    "close": s.end_time.strftime("%I:%M %p")
                }
            
            return {
                "success": True,
                "shop": {
                    "id": str(shop.id),
                    "name": shop.name,
                    "description": shop.description,
                    "address": shop.address,
                    "city": shop.city,
                    "state": shop.state,
                    "postal_code": shop.postal_code,
                    "phone": shop.phone,
                    "email": shop.email,
                    "website": shop.website,
                    "rating": float(shop.average_rating),
                    "total_reviews": shop.total_reviews,
                    "is_verified": shop.is_verified,
                    "timezone": shop.timezone,
                    "hours": hours
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}


class GetShopServicesTool(BaseTool):
    """Get services offered by a shop."""
    
    name = "get_shop_services"
    description = """
    Get all services offered by a shop.
    Includes names, descriptions, prices, and durations.
    Requires shop_id (UUID) - use search_shops first to get the ID.
    """
    allowed_roles = ["customer", "client", "staff", "guest"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "shop_id": {
                    "type": "string",
                    "description": "UUID of the shop (get this from search_shops first)"
                },
                "shop_name": {
                    "type": "string",
                    "description": "Alternative: Shop name if UUID not available"
                },
                "category": {
                    "type": "string",
                    "description": "Optional: Filter by category"
                }
            }
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.services.models import Service
        
        try:
            # Try UUID first, then fall back to name search
            shop_id = kwargs.get('shop_id')
            shop_name = kwargs.get('shop_name')
            
            if shop_id:
                try:
                    shop = Shop.objects.get(id=shop_id, is_active=True)
                except (Shop.DoesNotExist, Exception):
                    # If UUID fails, try as name
                    shop = Shop.objects.filter(name__icontains=shop_id, is_active=True).first()
            elif shop_name:
                shop = Shop.objects.filter(name__icontains=shop_name, is_active=True).first()
            else:
                return {"success": False, "error": "Please provide shop_id or shop_name"}
            
            if not shop:
                return {"success": False, "error": "Shop not found"}
            
            services = Service.objects.filter(shop=shop, is_active=True)
            
            category = kwargs.get('category')
            if category:
                services = services.filter(category__icontains=category)
            
            services = services.order_by('category', 'name')
            
            return {
                "success": True,
                "shop": shop.name,
                "services": [
                    {
                        "id": str(s.id),
                        "name": s.name,
                        "description": s.description,
                        "category": s.category,
                        "price": float(s.price),
                        "duration_minutes": s.duration_minutes
                    }
                    for s in services
                ]
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}


class GetShopStaffTool(BaseTool):
    """Get staff members at a shop."""
    
    name = "get_shop_staff"
    description = """
    Get staff members who work at a shop.
    Use to help customers choose a preferred stylist.
    """
    allowed_roles = ["customer", "client"]
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "shop_id": {
                    "type": "string",
                    "description": "UUID of the shop"
                },
                "service_id": {
                    "type": "string",
                    "description": "Optional: Filter by staff who provide this service"
                }
            },
            "required": ["shop_id"]
        }
    
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        from apps.shops.models import Shop
        from apps.staff.models import StaffMember
        
        try:
            shop = Shop.objects.get(id=kwargs['shop_id'], is_active=True)
            staff = StaffMember.objects.filter(shop=shop, is_active=True)
            
            service_id = kwargs.get('service_id')
            if service_id:
                staff = staff.filter(services__id=service_id)
            
            staff = staff.prefetch_related('services')
            
            return {
                "success": True,
                "shop": shop.name,
                "staff": [
                    {
                        "id": str(s.id),
                        "name": s.name,
                        "bio": s.bio,
                        "services": [srv.name for srv in s.services.filter(is_active=True)]
                    }
                    for s in staff
                ]
            }
            
        except Shop.DoesNotExist:
            return {"success": False, "error": "Shop not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
