<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# BeautyDrop AI - Django Backend

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Overview](#overview)
4. [System Architecture](#system-architecture)
5. [Database Schema](#database-schema)
6. [Folder Structure](#folder-structure)
7. [Authentication Flow](#authentication-flow)
8. [API Endpoints](#api-endpoints)
9. [Key Features & Modules](#key-features--modules)

---

## Quick Start

### Prerequisites

- Python 3.13.7+
- Clerk account (for authentication)
- Stripe account (for payments)

### Installation

1. **Clone the repository**

2. **Create and activate virtual environment**

3. **Install dependencies**

4. **Set up environment variables**

Create a `.env` file in the project root:

```bash
# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/beautydrop_db

# Redis (optional)
REDIS_URL=redis://localhost:6379/0

# Clerk Authentication
CLERK_SECRET_KEY=your_clerk_secret_key
CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key
CLERK_API_URL=https://api.clerk.com/v1

# Stripe Payments
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=your_stripe_publishable_key
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

5. **Create PostgreSQL database**
6. **Run migrations**
7. **Create superuser (optional)**
8. **Run the development server**

```bash
python manage.py runserver 0.0.0.0:8002
```

The API will be available at `http://localhost:8002`

### Access API Documentation

- **Swagger UI**: http://localhost:8002/api/docs/
### Authentication for Testing

In Swagger, use one of:

- **Bearer Token**: Paste Clerk JWT token (production)
- **X-Clerk-User-ID** header: Enter `clerk_user_id` directly (development only)

---

## Overview

This is a comprehensive backend architecture for a two-sided marketplace salon booking platform built with Django. The system supports:

- **Client Side**: Salon owners managing multiple shops, services, and availability schedules
- **User Side**: Customers browsing salons and booking appointments
- **Subscription Management**: Payment processing for both clients and users
- **Clerk Authentication**: Secure authentication for both user types

---

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

---

## Database Schema

```mermaid
erDiagram
    User ||--o{ Client : "can be"
    User ||--o{ Customer : "can be"
    User {
        string clerk_user_id PK
        string email UK
        string first_name
        string last_name
        string role
        boolean is_active
        boolean email_verified
        datetime created_at
    }

    Client ||--o{ Shop : "owns"
    Client {
        uuid id PK
        string clerk_user_id FK
        string business_name
        string phone
        datetime created_at
        datetime updated_at
    }

    Customer {
        uuid id PK
        string clerk_user_id FK
        string phone
        datetime created_at
        datetime updated_at
    }

    Shop ||--o{ Service : "offers"
    Shop ||--o{ Schedule : "has"
    Shop ||--o{ StaffMember : "employs"
    Shop {
        uuid id PK
        uuid client_id FK
        string name
        string address
        string city
        string state
        string postal_code
        string phone
        string email
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

    StaffMember ||--o{ StaffServiceAssignment : "assigned to"
    StaffMember {
        uuid id PK
        uuid shop_id FK
        string name
        string phone
        string email
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    StaffServiceAssignment {
        uuid id PK
        uuid staff_member_id FK
        uuid service_id FK
        datetime created_at
    }

    Schedule ||--o{ TimeSlot : "contains"
    Schedule {
        uuid id PK
        uuid shop_id FK
        string day_of_week
        time start_time
        time end_time
        integer slot_duration_minutes
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    TimeSlot ||--o| Booking : "booked by"
    TimeSlot {
        uuid id PK
        uuid schedule_id FK
        uuid staff_member_id FK
        datetime start_time
        datetime end_time
        string status
        datetime created_at
        datetime updated_at
    }

    Customer ||--o{ Booking : "makes"
    Booking ||--|| Service : "for"
    Booking ||--|| StaffMember : "with"
    Booking {
        uuid id PK
        uuid customer_id FK
        uuid shop_id FK
        uuid service_id FK
        uuid time_slot_id FK
        uuid staff_member_id FK
        string status
        decimal price
        text customer_notes
        text staff_notes
        datetime created_at
        datetime updated_at
    }

    User ||--o{ Subscription : "subscribes"
    Subscription {
        uuid id PK
        string clerk_user_id FK
        string plan_type
        string status
        decimal amount
        string stripe_subscription_id
        datetime start_date
        datetime end_date
        datetime created_at
        datetime updated_at
    }

    User ||--o{ Notification : "receives"
    Notification {
        uuid id PK
        string clerk_user_id FK
        string notification_type
        string title
        text message
        boolean is_read
        datetime created_at
    }
```

---

## Folder Structure

```
BeautyDropAI/
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
│   │   └── production.py                  # Prod environment
│   ├── urls.py                            # Root URL configuration
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/                                   # All Django apps
│   │
│   ├── authentication/                     # Clerk authentication
│   │   ├── models.py                      # User model (clerk_user_id as PK)
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── middleware.py                  # Clerk JWT validation
│   │   ├── auth_backends.py               # ClerkJWTAuthentication
│   │   ├── managers.py                    # Custom user manager
│   │   ├── admin.py
│   │   └── services/
│   │       ├── clerk_service.py           # Clerk SDK integration
│   │       ├── clerk_api.py               # Clerk API client
│   │       ├── token_service.py           # Token validation
│   │       └── user_data_service.py       # Real-time user data from Clerk
│   │
│   ├── core/                              # Shared utilities
│   │   ├── models.py                      # BaseModel, UUIDModel
│   │   ├── pagination.py
│   │   ├── exceptions.py
│   │   ├── schema.py                      # DRF Spectacular customization
│   │   └── utils/
│   │       └── constants.py
│   │
│   ├── payments/                          # Payment processing (NEW)
│   │   ├── models.py                      # Payment models (future)
│   │   ├── admin.py
│   │   ├── services/
│   │   │   └── stripe_service.py          # Stripe integration
│   │   └── apps.py
│   │
│   ├── clients/                           # Salon owners
│   │   ├── models.py                      # Client profile
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── admin.py
│   │
│   ├── customers/                         # End users
│   │   ├── models.py                      # Customer profile
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── admin.py
│   │
│   ├── shops/                             # Shop management
│   │   ├── models.py                      # Shop model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── filters.py
│   │   └── admin.py
│   │
│   ├── services/                          # Services offered by shops
│   │   ├── models.py                      # Service model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── admin.py
│   │
│   ├── staff/                             # Staff management
│   │   ├── models.py                      # StaffMember, StaffServiceAssignment
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── admin.py
│   │
│   ├── schedules/                         # Availability scheduling
│   │   ├── models.py                      # Schedule, TimeSlot
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── admin.py
│   │
│   ├── bookings/                          # Booking management
│   │   ├── models.py                      # Booking model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── admin.py
│   │
│   ├── subscriptions/                     # Subscription management
│   │   ├── models.py                      # Subscription model
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── admin.py
│   │
│   └── notifications/                     # Notifications
│       ├── models.py                      # Notification model
│       ├── serializers.py
│       ├── views.py
│       ├── urls.py
│       └── admin.py
│
└── scripts/                               # Management scripts
    ├── __init__.py
    └── seed_data.py
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

---

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

---

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

---

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

---

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

---

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

| Feature                   | Free | Basic | Premium   |
| :------------------------ | :--- | :---- | :-------- |
| Shops (Client)            | 1    | 3     | Unlimited |
| Bookings/Month (Customer) | 2    | 10    | Unlimited |
| Calendar Integration      | ❌   | ❌    | ✅        |
| Priority Support          | ❌   | ✅    | ✅        |
| Analytics Dashboard       | ❌   | ✅    | ✅        |

---

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

---

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

---

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

---

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

---

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

---

## CI/CD & Deployment

### 🚀 Current Status: LIVE & WORKING

**Service URL**: https://beautydrop-api-497422674710.us-east1.run.app  
**Platform**: Google Cloud Run (us-east1)  
**Status**: ✅ All features deployed and operational

📊 **Full Status**: See [`DEPLOYMENT_STATUS.md`](DEPLOYMENT_STATUS.md) for complete deployment info

### Deployment Options

**Option 1: Manual Deployment** (✅ Ready to use now)
```bash
./deploy-latest.sh
```

**Option 2: Automated CI/CD** (⏳ Requires admin setup)

This project includes a GitHub Actions CI/CD pipeline that automatically:
- Runs tests and linting on every PR
- Builds Docker image on `main` branch pushes
- Pushes to Google Artifact Registry
- Deploys to Google Cloud Run

**Pipeline Status**: [![CI/CD](https://github.com/awaisvortex/BeautyDropAI/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/awaisvortex/BeautyDropAI/actions/workflows/ci-cd.yml)

### Setup CI/CD (Optional - Requires Admin)

CI/CD requires admin permissions. If you have them, run:
```bash
./scripts/setup-workload-identity.sh  # Recommended (no keys needed)
# OR
./scripts/setup-cicd.sh               # Fallback (uses service account keys)
```

Then add GitHub secrets as shown in the script output.

⚠️ **Permission Issues?** See [`CI_CD_SETUP_NEEDED.md`](CI_CD_SETUP_NEEDED.md)

📚 **Detailed Guides**: 
- [`CI_CD_QUICKSTART.md`](CI_CD_QUICKSTART.md) - Quick reference
- [`.github/workflows/README.md`](.github/workflows/README.md) - Complete setup
- [`DEPLOYMENT_STATUS.md`](DEPLOYMENT_STATUS.md) - Current status

### Manual Deployment (No Admin Required)

Deploy anytime using:
```bash
./deploy-latest.sh
```

This works right now without any additional setup.

📚 **Manual Guide**: [`DEPLOYMENT.md`](DEPLOYMENT.md)

---

## Technology Stack Summary

| Component      | Technology              |
| :------------- | :---------------------- |
| Framework      | Django 4.2+             |
| Database       | PostgreSQL 15+          |
| Cache          | Redis 7+                |
| Authentication | Clerk                   |
| Payment        | Stripe                  |
| Task Queue     | Celery + Redis          |
| API            | Django REST Framework   |
| Testing        | Pytest                  |
| Deployment     | Docker + Google Cloud Run |

---

This architecture provides a solid foundation for a scalable, modular salon booking system. Each module is independent and can be extended without affecting others. The structure supports future integrations like Google Calendar while maintaining clean separation of concerns.

#   B e a u t y D r o p A I 
 
 




