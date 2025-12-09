"""
Staff services for handling staff-related business logic
"""
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def handle_staff_signup(clerk_user_data: dict) -> bool:
    """
    Handle staff member signup from Clerk webhook.
    Links the Clerk user to the StaffMember record.
    
    Called when a user signs up via invitation link with role='staff' in metadata.
    
    Args:
        clerk_user_data: User data from Clerk webhook
        
    Returns:
        True if staff was linked successfully, False otherwise
    """
    from apps.staff.models import StaffMember
    from apps.authentication.models import User
    
    public_metadata = clerk_user_data.get('public_metadata', {})
    
    # Check if this is a staff signup
    if public_metadata.get('role') != 'staff':
        return False
    
    staff_member_id = public_metadata.get('staff_member_id')
    if not staff_member_id:
        logger.warning("Staff signup webhook missing staff_member_id in metadata")
        return False
    
    try:
        staff_member = StaffMember.objects.get(id=staff_member_id)
        
        # Check if already linked
        if staff_member.user is not None:
            logger.info(f"Staff member {staff_member_id} already has linked user")
            return True
        
        # Get email from Clerk user data
        email_addresses = clerk_user_data.get('email_addresses', [])
        primary_email = next(
            (email['email_address'] for email in email_addresses 
             if email.get('id') == clerk_user_data.get('primary_email_address_id')),
            email_addresses[0]['email_address'] if email_addresses else staff_member.email
        )
        
        # Create or get User record
        user, created = User.objects.get_or_create(
            clerk_user_id=clerk_user_data['id'],
            defaults={
                'email': primary_email,
                'first_name': clerk_user_data.get('first_name', ''),
                'last_name': clerk_user_data.get('last_name', ''),
                'role': 'staff',
                'email_verified': True,
                'is_active': True
            }
        )
        
        if not created:
            # Update existing user with staff role
            user.role = 'staff'
            user.save(update_fields=['role'])
        
        # Link user to staff member
        staff_member.user = user
        staff_member.invite_status = 'accepted'
        staff_member.invite_accepted_at = timezone.now()
        staff_member.save(update_fields=['user', 'invite_status', 'invite_accepted_at'])
        
        logger.info(f"Successfully linked staff member {staff_member_id} to user {user.clerk_user_id}")
        return True
        
    except StaffMember.DoesNotExist:
        logger.error(f"Staff member {staff_member_id} not found for signup")
        return False
    except Exception as e:
        logger.error(f"Error linking staff member: {str(e)}")
        return False


def get_staff_by_user(user) -> 'StaffMember':
    """
    Get StaffMember profile for a user.
    
    Args:
        user: User instance
        
    Returns:
        StaffMember instance or None
    """
    from apps.staff.models import StaffMember
    
    try:
        return StaffMember.objects.select_related('shop').get(user=user)
    except StaffMember.DoesNotExist:
        return None
