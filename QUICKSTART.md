# Django Salon Booking System - Quick Reference

## 🚀 Quick Start Commands

```bash
# Setup
cd d:\Vortex
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Database
python manage.py makemigrations
python manage.py migrate

# Seed data (optional)
python scripts/seed_data.py

# Generate time slots
python scripts/generate_slots.py

# Run server
python manage.py runserver
```

## 🔑 Environment Variables to Configure

```env
# Clerk (Required)
CLERK_SECRET_KEY=sk_test_...
CLERK_PUBLISHABLE_KEY=pk_test_...

# Stripe (Required)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Database (Required)
DB_NAME=salon_booking_db
DB_USER=postgres
DB_PASSWORD=your_password
```

## 📍 Important URLs

- **API Base**: `http://localhost:8000/api/v1/`
- **API Docs**: `http://localhost:8000/api/docs/`
- **Admin**: `http://localhost:8000/admin/`
- **Health Check**: `http://localhost:8000/api/v1/auth/health/`

## 🔐 Clerk Setup for Google OAuth

1. Go to [Clerk Dashboard](https://dashboard.clerk.com/)
2. Select your application
3. Navigate to: **User & Authentication** → **Social Connections**
4. Click **Add connection** → Select **Google**
5. Follow the setup wizard
6. Enable the connection
7. Done! Users can now sign in with Google

## 📱 Frontend Integration Example

```javascript
// Install Clerk
npm install @clerk/clerk-react

// Setup Clerk Provider
import { ClerkProvider } from '@clerk/clerk-react';

<ClerkProvider publishableKey="pk_test_...">
  <App />
</ClerkProvider>

// Use in components
import { useAuth } from '@clerk/clerk-react';

function MyComponent() {
  const { getToken } = useAuth();

  const fetchData = async () => {
    const token = await getToken();
    const response = await fetch('http://localhost:8000/api/v1/auth/me/', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await response.json();
  };
}
```

## 📊 Database Models

| Model        | Purpose                           |
| ------------ | --------------------------------- |
| User         | Authentication (Clerk integrated) |
| Client       | Salon owner profile               |
| Customer     | End user profile                  |
| Shop         | Salon location                    |
| Service      | Services offered                  |
| ShopSchedule | Weekly availability               |
| TimeSlot     | Bookable time slots               |
| Booking      | Appointments                      |
| Subscription | Payment plans                     |
| Payment      | Payment records                   |
| Notification | User notifications                |

## 🛣️ API Endpoints Quick Reference

### Auth

- `GET /api/v1/auth/me/`
- `PUT /api/v1/auth/profile/`
- `POST /api/v1/auth/set-role/`

### Clients

- `GET/POST /api/v1/clients/`
- `GET/PUT/DELETE /api/v1/clients/{id}/`

### Shops

- `GET/POST /api/v1/shops/`
- `GET/PUT/DELETE /api/v1/shops/{id}/`

### Services

- `GET/POST /api/v1/services/`
- `GET/PUT/DELETE /api/v1/services/{id}/`

### Schedules

- `GET/POST /api/v1/schedules/`
- `GET/PUT/DELETE /api/v1/schedules/{id}/`

### Bookings

- `GET/POST /api/v1/bookings/`
- `GET/PUT/DELETE /api/v1/bookings/{id}/`

### Subscriptions

- `GET/POST /api/v1/subscriptions/`
- `GET /api/v1/subscriptions/{id}/`

## 🔧 Common Tasks

### Create a new shop

```bash
POST /api/v1/shops/
{
  "name": "My Salon",
  "address": "123 Main St",
  "city": "New York",
  "postal_code": "10001",
  "phone": "+1234567890"
}
```

### Create a schedule

```bash
POST /api/v1/schedules/
{
  "shop": "shop_uuid",
  "day_of_week": "monday",
  "start_time": "09:00",
  "end_time": "18:00",
  "slot_duration_minutes": 30
}
```

### Create a booking

```bash
POST /api/v1/bookings/
{
  "shop": "shop_uuid",
  "service": "service_uuid",
  "time_slot": "slot_uuid",
  "notes": "First time customer"
}
```

## 🐛 Troubleshooting

### Clerk Auth Not Working

- Check API keys in `.env`
- Verify token format: `Bearer <token>`
- Check Clerk dashboard for application status

### Database Connection Failed

- Ensure PostgreSQL is running
- Verify credentials in `.env`
- Check if database exists

### Redis Connection Failed

- Ensure Redis is running: `redis-cli ping`
- Check `REDIS_URL` in `.env`

### Migrations Error

- Delete migration files (except `__init__.py`)
- Run `python manage.py makemigrations`
- Run `python manage.py migrate`

## 📚 Documentation Files

- [SETUP.md](file:///d:/Vortex/SETUP.md) - Complete setup guide
- [README.md](file:///d:/Vortex/README.md) - Architecture documentation
- [Walkthrough](file:///C:/Users/Mg/.gemini/antigravity/brain/d6103398-8222-4e3c-88a2-c449991febb9/walkthrough.md) - Implementation details

## 🎯 Next Steps

1. ✅ Install dependencies
2. ✅ Configure Clerk (enable Google OAuth)
3. ✅ Configure Stripe
4. ✅ Setup database
5. ✅ Run migrations
6. ✅ Seed data
7. ✅ Generate time slots
8. ✅ Build frontend
9. ✅ Deploy to production

## 💡 Tips

- Use Swagger docs at `/api/docs/` for API testing
- Check Django admin at `/admin/` for data management
- Use `scripts/seed_data.py` for development data
- Generate slots regularly with `scripts/generate_slots.py`
- Monitor logs in `logs/django.log`

---

**You're all set! Start building your frontend and connect to the API.** 🚀
