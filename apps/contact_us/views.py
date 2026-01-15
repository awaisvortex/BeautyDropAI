"""
Views for contact us form submissions.
"""
import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema

from .models import ContactQuery, BusinessType, TeamSize, BestTimeToReach
from .serializers import ContactQueryCreateSerializer, ContactQueryResponseSerializer

logger = logging.getLogger(__name__)


class ContactQueryView(APIView):
    """
    API endpoint for submitting contact/consultation form.
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary='Submit Contact Form',
        description='Submit a consultation request form. All fields are required. '
                    'An email notification will be sent to the configured recipient.',
        request=ContactQueryCreateSerializer,
        responses={
            201: ContactQueryResponseSerializer,
            400: {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'details': {'type': 'object'}
                },
                'example': {
                    'error': 'Validation failed',
                    'details': {
                        'email': ['Please enter a valid email address']
                    }
                }
            }
        },
        tags=['Contact Us'],
    )
    def post(self, request):
        """
        Handle contact form submission.
        Creates a database entry and sends email notification.
        """
        serializer = ContactQueryCreateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Validation failed',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create the contact query record
        contact_query = serializer.save()
        
        # Send email notification
        email_sent = self._send_notification_email(contact_query)
        
        # Update email sent status
        contact_query.email_sent = email_sent
        contact_query.save(update_fields=['email_sent'])
        
        # Return response
        response_serializer = ContactQueryResponseSerializer(contact_query)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    def _send_notification_email(self, contact_query: ContactQuery) -> bool:
        """
        Send notification email with contact query details.
        
        Args:
            contact_query: ContactQuery instance with form data
            
        Returns:
            bool: True if email was sent successfully
        """
        recipient_email = getattr(
            settings,
            'CONTACT_FORM_RECIPIENT_EMAIL',
            'awais@vortexnow.ai'
        )
        
        subject = "Contact Query"
        
        # Build HTML email content
        html_content = self._build_email_html(contact_query)
        text_content = self._build_email_text(contact_query)
        
        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email]
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)
            
            logger.info(
                f"Contact query email sent successfully to {recipient_email} "
                f"for query {contact_query.id}"
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to send contact query email to {recipient_email}: {e}"
            )
            return False
    
    def _build_email_html(self, contact_query: ContactQuery) -> str:
        """Build HTML email content with all form data."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                h1 {{
                    color: #2563EB;
                    border-bottom: 2px solid #2563EB;
                    padding-bottom: 10px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                th, td {{
                    padding: 12px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                th {{
                    background-color: #f8f9fa;
                    font-weight: 600;
                    width: 35%;
                }}
                .highlight {{
                    background-color: #fff3cd;
                }}
                .footer {{
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #ddd;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <h1>New Consultation Request</h1>
            <p>A new consultation request has been submitted through the Beauty Drop AI website.</p>
            
            <table>
                <tr>
                    <th>Query ID</th>
                    <td>{contact_query.id}</td>
                </tr>
                <tr>
                    <th>First Name</th>
                    <td>{contact_query.first_name}</td>
                </tr>
                <tr>
                    <th>Last Name</th>
                    <td>{contact_query.last_name}</td>
                </tr>
                <tr class="highlight">
                    <th>Email</th>
                    <td><a href="mailto:{contact_query.email}">{contact_query.email}</a></td>
                </tr>
                <tr class="highlight">
                    <th>Phone Number</th>
                    <td><a href="tel:{contact_query.phone_number}">{contact_query.phone_number}</a></td>
                </tr>
                <tr>
                    <th>Salon/Spa Name</th>
                    <td>{contact_query.salon_name}</td>
                </tr>
                <tr>
                    <th>Business Type</th>
                    <td>{contact_query.get_business_type_display()}</td>
                </tr>
                <tr>
                    <th>Team Size</th>
                    <td>{contact_query.get_team_size_display()}</td>
                </tr>
                <tr>
                    <th>Best Time to Reach</th>
                    <td>{contact_query.get_best_time_to_reach_display()}</td>
                </tr>
            </table>
            
            <h2>Challenges Described</h2>
            <p style="background-color: #f8f9fa; padding: 15px; border-radius: 5px;">
                {contact_query.challenges}
            </p>
            
            <div class="footer">
                <p>Submitted on: {timezone.now().strftime('%B %d, %Y at %I:%M %p UTC')}</p>
                <p>This is an automated message from Beauty Drop AI.</p>
            </div>
        </body>
        </html>
        """
    
    def _build_email_text(self, contact_query: ContactQuery) -> str:
        """Build plain text email content."""
        return f"""
New Consultation Request
========================

Query ID: {contact_query.id}

Contact Information:
- First Name: {contact_query.first_name}
- Last Name: {contact_query.last_name}
- Email: {contact_query.email}
- Phone Number: {contact_query.phone_number}

Business Information:
- Salon/Spa Name: {contact_query.salon_name}
- Business Type: {contact_query.get_business_type_display()}
- Team Size: {contact_query.get_team_size_display()}

Best Time to Reach: {contact_query.get_best_time_to_reach_display()}

Challenges Described:
{contact_query.challenges}

---
Submitted on: {timezone.now().strftime('%B %d, %Y at %I:%M %p UTC')}
This is an automated message from Beauty Drop AI.
        """
