
import os
import django
import sys
from unittest.mock import MagicMock, patch

# Setup Django environment
sys.path.append('/Users/softwareengineer/Documents/Vortex/BeautyDropAI')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.authentication.models import User
from apps.shops.models import Shop
from apps.customers.models import Customer
from apps.clients.models import Client
from apps.staff.models import StaffMember
from apps.voice.voice_agents import ShopVoiceAgent

def test_role_detection_and_tools():
    print("=== Testing Role Detection and Tool Access ===\n")

    # 1. Create Mock Objects
    shop = MagicMock(spec=Shop)
    shop.id = "shop-123"
    shop.client_id = "client-user-id"
    shop.name = "Test Salon"

    # --- Customer User ---
    customer_user = MagicMock(spec=User)
    customer_user.email = "customer@example.com"
    customer_user.role = "customer"
    # Mock related objects access (Django reverse relations)
    customer_user.client_profile = None 
    customer_user.staff_profile = None
    # We need to mock how hasattr checks work or how the code accesses them
    # The code uses hasattr(user, 'client_profile') etc.
    # MagicMock usually returns a Mock for any attribute, which truthy.
    # We need to simulate DoesNotExist or attribute errors if needed, 
    # but specific code: 
    # if hasattr(self.user, 'client_profile'): client = self.user.client_profile 
    # checks if attribute exists.
    
    # Let's adjust mock setup to be more specific or use real objects if db access is allowed 
    # but script is safer with mocks for logic verification if we can.
    # Actually, using real DB objects in a test transaction would be better but simple mocks are faster
    # to verify the logic flow in ShopVoiceAgent._determine_role

    # --- Test Customer Role ---
    print("Testing Customer Role:")
    # Mocking behaviors for customer
    # Ensure hasattr(customer_user, 'client_profile') is False or raises AttributeError
    del customer_user.client_profile 
    del customer_user.staff_profile 
    
    agent = ShopVoiceAgent(session_id="test", shop=shop, user=customer_user)
    role = agent._determine_role()
    print(f"Detected Role: {role} (Expected: customer)")
    
    tools = agent.get_tool_names()
    print(f"Tools available: {len(tools)}")
    if 'create_booking' in tools and 'get_shop_bookings' not in tools:
        print("PASS: Customer has correct tools")
    else:
        print(f"FAIL: Incorrect tools for customer: {tools}")
    print()


    # --- Test Client (Owner) Role ---
    print("Testing Client (Owner) Role:")
    client_user = MagicMock(spec=User)
    client_user.email = "owner@example.com"
    client_user.role = "client"
    
    # Fix the shop-client relationship check
    # Code: if self.shop.client_id == client.id:
    client_profile = MagicMock(spec=Client)
    client_profile.id = "client-user-id" # Matches shop.client_id
    client_user.client_profile = client_profile
    del client_user.staff_profile
    
    agent = ShopVoiceAgent(session_id="test", shop=shop, user=client_user)
    role = agent._determine_role()
    print(f"Detected Role: {role} (Expected: client)")
    
    tools = agent.get_tool_names()
    if 'get_shop_bookings' in tools and 'create_service' in tools:
        print("PASS: Client has correct tools")
    else:
        print(f"FAIL: Incorrect tools for client: {tools}")
    print()


    # --- Test Staff Role ---
    print("Testing Staff Role:")
    staff_user = MagicMock(spec=User)
    staff_user.email = "staff@example.com"
    staff_user.role = "staff"
    
    staff_profile = MagicMock(spec=StaffMember)
    staff_profile.shop_id = "shop-123" # Matches shop.id
    staff_user.staff_profile = staff_profile
    del staff_user.client_profile # Ensure not owner
    
    agent = ShopVoiceAgent(session_id="test", shop=shop, user=staff_user)
    role = agent._determine_role()
    print(f"Detected Role: {role} (Expected: staff)")
    
    tools = agent.get_tool_names()
    if 'get_my_schedule' in tools and 'complete_booking' in tools:
        print("PASS: Staff has correct tools")
    else:
        print(f"FAIL: Incorrect tools for staff: {tools}")
    print()

if __name__ == "__main__":
    try:
        test_role_detection_and_tools()
        print("\nVerification Script Completed Successfully.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
