<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Django Salon Booking System - Backend Architecture

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Database Schema](#database-schema)
4. [Folder Structure](#folder-structure)
5. [Authentication Flow](#authentication-flow)
6. [API Endpoints](#api-endpoints)
7. [Key Features \& Modules](#key-features--modules)

***

## Overview

This is a comprehensive backend architecture for a two-sided marketplace salon booking platform built with Django. The system supports:

- **Client Side**: Salon owners managing multiple shops, services, and availability schedules
- **User Side**: Customers browsing salons and booking appointments
- **Subscription Management**: Payment processing for both clients and users
- **Clerk Authentication**: Secure authentication for both user types

***

## System Architecture

```mermaid
graph TB
    subgraph "Client Applications"
        WebApp[Web Application]
        MobileApp[Mobile Application]
    end

    subgraph "API Gateway Layer"
        NGINX[NGINX/Load Balancer]
    end

    subgraph "Django Backend"
        Auth[Authentication Service<br/>Clerk Integration]
        ClientAPI[Client API<br/>Shop Management]
        UserAPI[User API<br/>Booking System]
        SubAPI[Subscription API<br/>Payment Processing]
        ScheduleAPI[Schedule API<br/>Availability Management]
        NotifAPI[Notification Service]
    end

    subgraph "Database Layer"
        PostgreSQL[(PostgreSQL<br/>Main Database)]
        Redis[(Redis<br/>Cache & Sessions)]
    end

    subgraph "External Services"
        Clerk[Clerk Auth]
        Stripe[Stripe/Payment Gateway]
        EmailService[Email Service]
        CalendarSync[Google Calendar API<br/>Future Integration]
    end

    WebApp --> NGINX
    MobileApp --> NGINX
    NGINX --> Auth
    NGINX --> ClientAPI
    NGINX --> UserAPI
    NGINX --> SubAPI
    NGINX --> ScheduleAPI
    
    Auth --> Clerk
    ClientAPI --> PostgreSQL
    UserAPI --> PostgreSQL
    SubAPI --> PostgreSQL
    ScheduleAPI --> PostgreSQL
    SubAPI --> Stripe
    NotifAPI --> EmailService
    
    ClientAPI --> Redis
    UserAPI --> Redis
    ScheduleAPI --> Redis
    
    ScheduleAPI -.->|Future| CalendarSync
```


***

## Database Schema

```mermaid
erDiagram
    User ||--o{ Client : "can be"
    User ||--o{ Customer : "can be"
    User {
        uuid id PK
        string clerk_user_id UK
        string email UK
        string role
        datetime created_at
        datetime updated_at
        boolean is_active
    }

    Client ||--o{ Shop : "owns"
    Client {
        uuid id PK
        uuid user_id FK
        string business_name
        string phone
        json subscription_details
        datetime subscription_expires_at
    }

    Shop ||--o{ Service : "offers"
    Shop ||--o{ ShopSchedule : "has"
    Shop {
        uuid id PK
        uuid client_id FK
        string name
        string address
        string city
        string postal_code
        json contact_details
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    Service {
        uuid id PK
        uuid shop_id FK
        string name
        text description
        decimal price
        integer duration_minutes
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    ShopSchedule ||--o{ TimeSlot : "contains"
    ShopSchedule {
        uuid id PK
        uuid shop_id FK
        string day_of_week
        time start_time
        time end_time
        integer slot_duration_minutes
        boolean is_active
    }

    TimeSlot ||--o| Booking : "booked by"
    TimeSlot {
        uuid id PK
        uuid schedule_id FK
        datetime start_datetime
        datetime end_datetime
        string status
        datetime created_at
    }

    Customer ||--o{ Booking : "makes"
    Customer {
        uuid id PK
        uuid user_id FK
        string phone
        json subscription_details
        datetime subscription_expires_at
    }

    Booking ||--|| Service : "for"
    Booking {
        uuid id PK
        uuid customer_id FK
        uuid shop_id FK
        uuid service_id FK
        uuid time_slot_id FK
        datetime booking_datetime
        string status
        decimal total_price
        text notes
        datetime created_at
        datetime updated_at
    }

    Subscription ||--o| Client : "subscribed by"
    Subscription ||--o| Customer : "subscribed by"
    Subscription {
        uuid id PK
        uuid user_id FK
        string user_type
        string plan_type
        decimal amount
        string payment_provider_id
        datetime start_date
        datetime end_date
        string status
        datetime created_at
    }

    Payment ||--|| Subscription : "for"
    Payment {
        uuid id PK
        uuid subscription_id FK
        decimal amount
        string payment_method
        string transaction_id
        string status
        datetime payment_date
    }
```


***

## Folder Structure

```
salon_booking_system/
│
├── manage.py
├── requirements.txt
├── .env
├── .gitignore
├── README.md
│
├── config/                                 # Project configuration
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py                        # Base settings
│   │   ├── development.py                 # Dev environment
│   │   ├── production.py                  # Prod environment
│   │   └── testing.py                     # Test environment
│   ├── urls.py                            # Root URL configuration
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/                                   # All Django apps
│   │
│   ├── authentication/                     # Clerk authentication integration
│   │   ├── __init__.py
│   │   ├── models.py                      # User model (extends AbstractUser)
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── middleware.py                  # Clerk JWT validation
│   │   ├── permissions.py                 # Custom permissions
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── clerk_service.py          # Clerk API integration
│   │   │   └── token_service.py          # Token validation
│   │   └── tests/
│   │
│   ├── clients/                           # Client (Salon Owner) management
│   │   ├── __init__.py
│   │   ├── models.py                      # Client model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── permissions.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── client_service.py
│   │   └── tests/
│   │
│   ├── shops/                             # Shop management
│   │   ├── __init__.py
│   │   ├── models.py                      # Shop model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── permissions.py
│   │   ├── filters.py                     # Django filters for search
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── shop_service.py
│   │   └── tests/
│   │
│   ├── services/                          # Services offered by shops
│   │   ├── __init__.py
│   │   ├── models.py                      # Service model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── permissions.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── service_management.py
│   │   └── tests/
│   │
│   ├── schedules/                         # Availability scheduling (Cal.com-like)
│   │   ├── __init__.py
│   │   ├── models.py                      # ShopSchedule, TimeSlot models
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── permissions.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── schedule_generator.py     # Generate time slots
│   │   │   ├── availability_checker.py   # Check slot availability
│   │   │   └── calendar_sync.py          # Future: Google Calendar integration
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   └── time_utils.py             # Time zone handling
│   │   └── tests/
│   │
│   ├── bookings/                          # Booking management
│   │   ├── __init__.py
│   │   ├── models.py                      # Booking model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── permissions.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── booking_service.py        # Booking logic
│   │   │   └── cancellation_service.py   # Cancellation handling
│   │   ├── signals.py                     # Post-booking notifications
│   │   └── tests/
│   │
│   ├── customers/                         # Customer management
│   │   ├── __init__.py
│   │   ├── models.py                      # Customer model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── permissions.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── customer_service.py
│   │   └── tests/
│   │
│   ├── subscriptions/                     # Subscription management
│   │   ├── __init__.py
│   │   ├── models.py                      # Subscription, Payment models
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── permissions.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── subscription_service.py   # Subscription logic
│   │   │   ├── payment_service.py        # Payment processing
│   │   │   └── stripe_service.py         # Stripe integration
│   │   ├── webhooks.py                    # Payment webhooks
│   │   └── tests/
│   │
│   ├── notifications/                     # Notification system
│   │   ├── __init__.py
│   │   ├── models.py                      # Notification model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── email_service.py
│   │   │   ├── sms_service.py            # Future: SMS notifications
│   │   │   └── push_notification.py      # Future: Push notifications
│   │   └── tests/
│   │
│   └── core/                              # Shared utilities
│       ├── __init__.py
│       ├── models.py                      # Abstract base models
│       ├── serializers.py                 # Base serializers
│       ├── permissions.py                 # Global permissions
│       ├── pagination.py                  # Custom pagination
│       ├── exceptions.py                  # Custom exceptions
│       ├── validators.py                  # Custom validators
│       └── utils/
│           ├── __init__.py
│           ├── helpers.py
│           └── constants.py
│
├── infrastructure/                        # Infrastructure code
│   ├── __init__.py
│   ├── cache/
│   │   ├── __init__.py
│   │   └── redis_client.py
│   ├── storage/
│   │   ├── __init__.py
│   │   └── file_storage.py
│   └── integrations/
│       ├── __init__.py
│       ├── clerk/
│       │   ├── __init__.py
│       │   └── client.py
│       ├── stripe/
│       │   ├── __init__.py
│       │   └── client.py
│       └── google_calendar/              # Future integration
│           ├── __init__.py
│           └── client.py
│
├── scripts/                               # Management scripts
│   ├── __init__.py
│   ├── seed_data.py
│   └── generate_slots.py
│
└── tests/                                 # Integration tests
    ├── __init__.py
    ├── integration/
    └── e2e/
```


***

## Authentication Flow

```mermaid
sequenceDiagram
    participant Client/User
    participant Frontend
    participant Django API
    participant Clerk
    participant Database

    Client/User->>Frontend: Login/Signup
    Frontend->>Clerk: Authenticate
    Clerk-->>Frontend: JWT Token
    Frontend->>Django API: Request with JWT Token
    Django API->>Clerk: Validate Token
    Clerk-->>Django API: Token Valid + User Info
    
    alt User doesn't exist in Django DB
        Django API->>Database: Create User Record
        Database-->>Django API: User Created
    end
    
    Django API->>Database: Fetch/Update User
    Database-->>Django API: User Data
    Django API-->>Frontend: Response with User Data
    Frontend-->>Client/User: Display Dashboard
```


### Authentication Middleware Flow

```mermaid
flowchart TD
    A[Request Received] --> B{Has Authorization Header?}
    B -->|No| C[Return 401 Unauthorized]
    B -->|Yes| D[Extract JWT Token]
    D --> E[Validate with Clerk API]
    E --> F{Token Valid?}
    F -->|No| G[Return 401 Invalid Token]
    F -->|Yes| H[Extract Clerk User ID]
    H --> I{User exists in DB?}
    I -->|No| J[Create User Record]
    I -->|Yes| K[Fetch User from DB]
    J --> L[Attach User to Request]
    K --> L
    L --> M[Continue to View]
```


***

## API Endpoints

### Authentication Module

```
POST   /api/v1/auth/register/           # Register new user
POST   /api/v1/auth/login/              # Login (handled by Clerk)
POST   /api/v1/auth/logout/             # Logout
GET    /api/v1/auth/me/                 # Get current user info
PUT    /api/v1/auth/profile/            # Update profile
```


### Client Module

```
POST   /api/v1/clients/                 # Create client profile
GET    /api/v1/clients/me/              # Get client profile
PUT    /api/v1/clients/me/              # Update client profile
GET    /api/v1/clients/dashboard/       # Client dashboard stats
```


### Shop Module

```
POST   /api/v1/shops/                   # Create shop
GET    /api/v1/shops/                   # List all shops (public)
GET    /api/v1/shops/{id}/              # Get shop details
PUT    /api/v1/shops/{id}/              # Update shop
DELETE /api/v1/shops/{id}/              # Delete shop
GET    /api/v1/shops/my-shops/          # Client's shops
GET    /api/v1/shops/{id}/services/     # Shop services
GET    /api/v1/shops/search/            # Search shops by location/name
```


### Service Module

```
POST   /api/v1/services/                # Add service to shop
GET    /api/v1/services/{id}/           # Get service details
PUT    /api/v1/services/{id}/           # Update service
DELETE /api/v1/services/{id}/           # Delete service
GET    /api/v1/services/shop/{shop_id}/ # All services for a shop
```


### Schedule Module (Cal.com-like)

```
POST   /api/v1/schedules/               # Create shop schedule
GET    /api/v1/schedules/shop/{shop_id}/           # Get shop schedules
PUT    /api/v1/schedules/{id}/                     # Update schedule
DELETE /api/v1/schedules/{id}/                     # Delete schedule
GET    /api/v1/schedules/{id}/available-slots/    # Get available slots
POST   /api/v1/schedules/generate-slots/          # Generate time slots
GET    /api/v1/schedules/calendar-view/{shop_id}/ # Calendar view
```


### Booking Module

```
POST   /api/v1/bookings/                # Create booking
GET    /api/v1/bookings/                # List user's bookings
GET    /api/v1/bookings/{id}/           # Get booking details
PUT    /api/v1/bookings/{id}/           # Update booking
DELETE /api/v1/bookings/{id}/cancel/    # Cancel booking
GET    /api/v1/bookings/shop/{shop_id}/ # Shop's bookings (client)
GET    /api/v1/bookings/upcoming/       # Upcoming bookings
GET    /api/v1/bookings/history/        # Booking history
```


### Customer Module

```
POST   /api/v1/customers/               # Create customer profile
GET    /api/v1/customers/me/            # Get customer profile
PUT    /api/v1/customers/me/            # Update customer profile
GET    /api/v1/customers/favorites/     # Favorite shops
POST   /api/v1/customers/favorites/{shop_id}/ # Add favorite
```


### Subscription Module

```
POST   /api/v1/subscriptions/           # Create subscription
GET    /api/v1/subscriptions/me/        # Get current subscription
PUT    /api/v1/subscriptions/upgrade/   # Upgrade plan
POST   /api/v1/subscriptions/cancel/    # Cancel subscription
GET    /api/v1/subscriptions/plans/     # Available plans
POST   /api/v1/subscriptions/webhooks/  # Payment webhooks
GET    /api/v1/subscriptions/invoices/  # Payment history
```


***

## Key Features \& Modules

### 1. Authentication Module

**Purpose**: Handle user authentication via Clerk

**Key Components**:

- Custom middleware for JWT validation
- User model with Clerk integration
- Role-based access control (Client/Customer)
- Permission classes for API endpoints

**Integration Points**:

- Clerk API for token validation
- User creation on first authentication
- Session management via Redis

***

### 2. Schedule Management (Cal.com-like)

```mermaid
flowchart TD
    A[Client Creates Schedule] --> B[Define Weekly Availability]
    B --> C[Set Day of Week]
    C --> D[Set Start & End Time]
    D --> E[Set Slot Duration]
    E --> F[Generate Time Slots]
    F --> G[Store in Database]
    
    H[User Views Shop] --> I[Fetch Shop Schedules]
    I --> J[Generate Available Slots]
    J --> K{Check Slot Status}
    K -->|Available| L[Display to User]
    K -->|Booked| M[Mark as Unavailable]
    
    L --> N[User Selects Slot]
    N --> O[Create Booking]
    O --> P[Update Slot Status]
```

**Schedule Features**:

- Weekly recurring schedules
- Day-specific availability
- Custom slot durations
- Holiday/blackout dates (future)
- Buffer time between appointments (future)
- Multiple schedules per shop (future)

***

### 3. Booking Flow

```mermaid
sequenceDiagram
    participant Customer
    participant Frontend
    participant API
    participant Database
    participant Notification

    Customer->>Frontend: Browse Shops
    Frontend->>API: GET /api/v1/shops/
    API-->>Frontend: Shop List
    
    Customer->>Frontend: Select Shop
    Frontend->>API: GET /api/v1/schedules/calendar-view/{shop_id}
    API->>Database: Fetch Available Slots
    Database-->>API: Available Slots
    API-->>Frontend: Calendar Data
    
    Customer->>Frontend: Select Service & Slot
    Frontend->>API: POST /api/v1/bookings/
    API->>Database: Check Slot Availability
    
    alt Slot Available
        Database-->>API: Slot Available
        API->>Database: Create Booking & Lock Slot
        Database-->>API: Booking Created
        API->>Notification: Send Confirmation
        Notification-->>Customer: Email/SMS Confirmation
        API-->>Frontend: Booking Success
    else Slot Unavailable
        Database-->>API: Slot Taken
        API-->>Frontend: Booking Failed
    end
```


***

### 4. Subscription Management

```mermaid
flowchart TD
    A[User/Client] --> B{Choose Plan}
    B --> C[Free Trial]
    B --> D[Basic Plan]
    B --> E[Premium Plan]
    
    C --> F[Create Subscription]
    D --> F
    E --> F
    
    F --> G[Redirect to Stripe]
    G --> H[Process Payment]
    H --> I{Payment Success?}
    
    I -->|Yes| J[Activate Subscription]
    I -->|No| K[Show Error]
    
    J --> L[Store in Database]
    L --> M[Send Confirmation]
    M --> N[Enable Features]
    
    O[Webhook from Stripe] --> P{Event Type?}
    P -->|payment_succeeded| Q[Extend Subscription]
    P -->|payment_failed| R[Mark as Overdue]
    P -->|subscription_cancelled| S[Deactivate Features]
```

**Subscription Plans** (Example):


| Feature | Free | Basic | Premium |
| :-- | :-- | :-- | :-- |
| Shops (Client) | 1 | 3 | Unlimited |
| Bookings/Month (Customer) | 2 | 10 | Unlimited |
| Calendar Integration | ❌ | ❌ | ✅ |
| Priority Support | ❌ | ✅ | ✅ |
| Analytics Dashboard | ❌ | ✅ | ✅ |


***

### 5. Modular Integration Points

```mermaid
graph LR
    A[Core System] --> B[Google Calendar]
    A --> C[Apple Calendar]
    A --> D[Outlook Calendar]
    A --> E[SMS Provider]
    A --> F[Email Service]
    A --> G[Analytics]
    A --> H[CRM Integration]
```

**Future Integration Modules**:

- `apps/integrations/google_calendar/` - Sync bookings with Google Calendar
- `apps/integrations/apple_calendar/` - iCal support
- `apps/analytics/` - Business analytics for clients
- `apps/reviews/` - Customer review system
- `apps/payments/` - Multiple payment gateways

***

## Scalability Considerations

### 1. Database Optimization

- **Indexing**: Add indexes on frequently queried fields (shop location, dates, clerk_user_id)
- **Connection Pooling**: Use pgBouncer for PostgreSQL
- **Read Replicas**: For read-heavy operations (shop browsing)


### 2. Caching Strategy

```mermaid
flowchart LR
    A[Request] --> B{Cache Hit?}
    B -->|Yes| C[Return from Redis]
    B -->|No| D[Query Database]
    D --> E[Store in Redis]
    E --> F[Return Response]
    C --> F
```

**Cache Keys**:

- Shop details: `shop:{shop_id}`
- Available slots: `slots:{shop_id}:{date}`
- User subscriptions: `subscription:{user_id}`


### 3. Asynchronous Tasks

Use **Celery** for:

- Sending notifications
- Generating time slots
- Processing payments
- Syncing with external calendars


### 4. API Versioning

- Current: `/api/v1/`
- Future: `/api/v2/` for breaking changes

***

## Security Considerations

1. **Authentication**:
    - JWT validation via Clerk
    - Token expiration handling
    - Refresh token mechanism
2. **Authorization**:
    - Role-based permissions (Client vs Customer)
    - Shop ownership verification
    - Booking ownership verification
3. **Data Protection**:
    - Encrypted passwords (handled by Clerk)
    - HTTPS only in production
    - Rate limiting on API endpoints
    - SQL injection protection (Django ORM)
4. **Payment Security**:
    - PCI compliance via Stripe
    - Webhook signature verification
    - No card data stored locally

***

## Environment Variables

```bash
# Django Settings
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=your-domain.com

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/salon_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Clerk
CLERK_SECRET_KEY=your-clerk-secret-key
CLERK_PUBLISHABLE_KEY=your-clerk-publishable-key

# Stripe
STRIPE_SECRET_KEY=your-stripe-secret-key
STRIPE_WEBHOOK_SECRET=your-webhook-secret

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587

# Future: Google Calendar
GOOGLE_CALENDAR_CLIENT_ID=your-client-id
GOOGLE_CALENDAR_CLIENT_SECRET=your-client-secret
```


***

## Next Steps

1. **Set up Django project** with the folder structure
2. **Configure Clerk authentication** middleware
3. **Create database models** as per schema
4. **Implement schedule generation** logic (Cal.com-like)
5. **Build API endpoints** module by module
6. **Integrate Stripe** for subscriptions
7. **Add notification system**
8. **Write comprehensive tests**
9. **Deploy to staging** environment

***

## Technology Stack Summary

| Component | Technology |
| :-- | :-- |
| Framework | Django 4.2+ |
| Database | PostgreSQL 15+ |
| Cache | Redis 7+ |
| Authentication | Clerk |
| Payment | Stripe |
| Task Queue | Celery + Redis |
| API | Django REST Framework |
| Testing | Pytest |
| Deployment | Docker + Docker Compose |


***

This architecture provides a solid foundation for a scalable, modular salon booking system. Each module is independent and can be extended without affecting others. The structure supports future integrations like Google Calendar while maintaining clean separation of concerns.

#   B e a u t y D r o p A I  
 