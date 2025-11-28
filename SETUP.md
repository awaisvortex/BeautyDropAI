# Django Salon Booking System - Setup Guide

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- PostgreSQL 15+
- Redis 7+
- Clerk account (for authentication)
- Stripe account (for payments)

### 1. Clone and Setup Virtual Environment

```bash
# Navigate to project directory
cd d:\Vortex

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

The `.env` file has been created with default values. Update the following:

#### Clerk Configuration

1. Go to [Clerk Dashboard](https://dashboard.clerk.com/)
2. Create a new application or use existing
3. Navigate to API Keys
4. Copy your keys and update `.env`:
   ```
   CLERK_SECRET_KEY=sk_test_your_secret_key
   CLERK_PUBLISHABLE_KEY=pk_test_your_publishable_key
   ```

#### Configure Google OAuth in Clerk

1. In Clerk Dashboard, go to "User & Authentication" → "Social Connections"
2. Enable Google
3. Follow Clerk's instructions to configure Google OAuth
4. Users can now sign in with Google!

#### Stripe Configuration

1. Go to [Stripe Dashboard](https://dashboard.stripe.com/)
2. Get your API keys from Developers → API keys
3. Update `.env`:
   ```
   STRIPE_SECRET_KEY=sk_test_your_secret_key
   STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key
   ```
4. For webhooks, use Stripe CLI or configure webhook endpoint in dashboard

#### Database Configuration

1. Create PostgreSQL database:
   ```sql
   CREATE DATABASE salon_booking_db;
   ```
2. Update `.env` with your database credentials:
   ```
   DB_NAME=salon_booking_db
   DB_USER=your_postgres_user
   DB_PASSWORD=your_postgres_password
   DB_HOST=localhost
   DB_PORT=5432
   ```

#### Redis Configuration

- Ensure Redis is running on localhost:6379
- Or update `REDIS_URL` in `.env`

### 4. Run Migrations

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate
```

### 5. Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

### 6. Seed Database (Optional)

```bash
python scripts/seed_data.py
```

This creates:

- Sample client user: `client@example.com`
- Sample customer user: `customer@example.com`
- Sample shop with services
- Sample schedules

### 7. Generate Time Slots

```bash
# Generate slots for all shops for next 30 days
python scripts/generate_slots.py

# Or for specific shop
python scripts/generate_slots.py <shop_id> 30
```

### 8. Run Development Server

```bash
python manage.py runserver
```

The API will be available at: `http://localhost:8000`

### 9. Access API Documentation

- Swagger UI: `http://localhost:8000/api/docs/`
- API Schema: `http://localhost:8000/api/schema/`
- Admin Panel: `http://localhost:8000/admin/`

## 📚 API Endpoints

### Authentication

- `GET /api/v1/auth/me/` - Get current user
- `PUT /api/v1/auth/profile/` - Update profile
- `POST /api/v1/auth/set-role/` - Set user role (client/customer)
- `GET /api/v1/auth/health/` - Health check

### Clients

- `GET /api/v1/clients/` - List clients
- `POST /api/v1/clients/` - Create client
- `GET /api/v1/clients/{id}/` - Get client details
- `PUT /api/v1/clients/{id}/` - Update client

### Shops

- `GET /api/v1/shops/` - List shops
- `POST /api/v1/shops/` - Create shop
- `GET /api/v1/shops/{id}/` - Get shop details
- `PUT /api/v1/shops/{id}/` - Update shop
- `DELETE /api/v1/shops/{id}/` - Delete shop

### Services

- `GET /api/v1/services/` - List services
- `POST /api/v1/services/` - Create service
- `GET /api/v1/services/{id}/` - Get service details
- `PUT /api/v1/services/{id}/` - Update service

### Schedules

- `GET /api/v1/schedules/` - List schedules
- `POST /api/v1/schedules/` - Create schedule
- `GET /api/v1/schedules/{id}/` - Get schedule details

### Bookings

- `GET /api/v1/bookings/` - List bookings
- `POST /api/v1/bookings/` - Create booking
- `GET /api/v1/bookings/{id}/` - Get booking details
- `PUT /api/v1/bookings/{id}/` - Update booking

### Subscriptions

- `GET /api/v1/subscriptions/` - List subscriptions
- `POST /api/v1/subscriptions/` - Create subscription

### Customers

- `GET /api/v1/customers/` - List customers
- `POST /api/v1/customers/` - Create customer

### Notifications

- `GET /api/v1/notifications/` - List notifications

## 🔐 Authentication Flow

### For Frontend Integration

1. **User signs up/logs in via Clerk** (supports Google OAuth)

   - Use Clerk's frontend SDK
   - User can choose email/password or Google sign-in

2. **Get JWT token from Clerk**

   ```javascript
   const token = await clerk.session.getToken();
   ```

3. **Send token with API requests**

   ```javascript
   fetch("http://localhost:8000/api/v1/auth/me/", {
     headers: {
       Authorization: `Bearer ${token}`,
     },
   });
   ```

4. **Backend automatically creates/updates user**

   - Middleware validates token with Clerk
   - Creates user in database on first login
   - Syncs user data from Clerk

5. **Set user role** (first time only)
   ```javascript
   fetch("http://localhost:8000/api/v1/auth/set-role/", {
     method: "POST",
     headers: {
       Authorization: `Bearer ${token}`,
       "Content-Type": "application/json",
     },
     body: JSON.stringify({ role: "client" }), // or 'customer'
   });
   ```

## 🏗️ Project Structure

```
d:\Vortex\
├── apps/                      # Django apps
│   ├── authentication/        # Clerk auth integration
│   ├── clients/              # Salon owners
│   ├── customers/            # End users
│   ├── shops/                # Salon shops
│   ├── services/             # Services offered
│   ├── schedules/            # Availability scheduling
│   ├── bookings/             # Appointment bookings
│   ├── subscriptions/        # Payment & subscriptions
│   ├── notifications/        # Notifications
│   └── core/                 # Shared utilities
├── config/                   # Django configuration
│   ├── settings/             # Environment-specific settings
│   ├── urls.py              # Root URL config
│   ├── wsgi.py              # WSGI config
│   └── asgi.py              # ASGI config
├── infrastructure/           # External integrations
│   ├── integrations/
│   │   ├── clerk/           # Clerk client
│   │   └── stripe/          # Stripe client
│   └── cache/               # Redis client
├── scripts/                  # Utility scripts
│   ├── seed_data.py         # Database seeding
│   └── generate_slots.py    # Time slot generation
├── manage.py                # Django management
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables
└── README.md               # This file
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=apps

# Run specific app tests
pytest apps/authentication/tests/
```

## 🚢 Deployment

### Production Checklist

1. Update `.env` for production:

   - Set `DEBUG=False`
   - Set `DJANGO_SETTINGS_MODULE=config.settings.production`
   - Use strong `SECRET_KEY`
   - Configure `ALLOWED_HOSTS`

2. Collect static files:

   ```bash
   python manage.py collectstatic
   ```

3. Use production database and Redis

4. Configure Stripe webhooks for production

5. Use gunicorn for serving:
   ```bash
   gunicorn config.wsgi:application
   ```

## 📝 Notes

- **Clerk handles all authentication** - no passwords stored in Django
- **Google OAuth** is configured through Clerk dashboard
- **Stripe handles all payments** - no card data stored
- **Redis is used for caching** and session storage
- **PostgreSQL is required** for production
- **Time slots are generated** via script, not automatically

## 🆘 Troubleshooting

### Clerk Authentication Issues

- Verify API keys are correct
- Check that Clerk application is in correct mode (development/production)
- Ensure Google OAuth is enabled in Clerk dashboard

### Database Connection Issues

- Verify PostgreSQL is running
- Check database credentials in `.env`
- Ensure database exists

### Redis Connection Issues

- Verify Redis is running: `redis-cli ping`
- Check Redis URL in `.env`

### Migration Issues

- Delete migrations: `find . -path "*/migrations/*.py" -not -name "__init__.py" -delete`
- Recreate: `python manage.py makemigrations`
- Apply: `python manage.py migrate`

## 📞 Support

For issues or questions:

1. Check the API documentation at `/api/docs/`
2. Review Clerk documentation for auth issues
3. Review Stripe documentation for payment issues

## 🎉 You're Ready!

Your Django salon booking system is now set up with:

- ✅ Clerk authentication with Google OAuth
- ✅ Stripe payment integration
- ✅ Complete REST API
- ✅ Cal.com-like scheduling
- ✅ Role-based access control
- ✅ Redis caching
- ✅ PostgreSQL database

Start building your frontend and connect to the API!
