# WhoBuiltMyRoad - Backend API

Public accountability platform for road infrastructure. **FastAPI + MongoDB + Cloudflare R2**.

## Features

- 🗺️ Display roads on OpenStreetMap with GeoJSON
- 👥 Public submissions (pending admin approval)
- 📸 Image uploads via Cloudflare R2
- 💬 Feedback/comments system
- 🔍 Place search using OpenStreetMap
- 🔐 JWT authentication
- 🛡️ Rate limiting

## Stack

**FastAPI** • **MongoDB** • **Cloudflare R2** • **JWT** • **Pydantic v2**

## Structure

```
app/
├── main.py           # FastAPI app
├── config.py         # Settings
├── database.py       # MongoDB
├── auth.py           # JWT auth
├── models.py         # DB models
├── schemas.py        # Schemas
├── routers/          # API endpoints
│   ├── auth.py
│   ├── roads.py
│   ├── admin.py
│   └── search.py
└── utils/
    ├── storage.py    # R2 storage
    ├── datetime_helper.py
    └── rate_limit.py
```

## Quick Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Environment

Copy `.env.example` to `.env` and configure:

```env
MONGODB_URL=mongodb://localhost:27017  # or MongoDB Atlas URL
MONGODB_DB_NAME=whobuiltmyroad_db

SECRET_KEY=<generate with: openssl rand -hex 32>
ADMIN_API_TOKEN=<generate with: openssl rand -hex 32>

R2_ENDPOINT_URL=https://YOUR-ACCOUNT-ID.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your-r2-access-key
R2_SECRET_ACCESS_KEY=your-r2-secret-key
R2_BUCKET_NAME=whobuiltmyroad
R2_PUBLIC_URL=https://pub-xxxxx.r2.dev
```

### 3. Run

```bash
uvicorn app.main:app --reload
```

API: `http://localhost:8000`

## API Endpoints

**Auth**
- `POST /auth/signup` - Register
- `POST /auth/login` - Login

**Roads** (Public)
- `GET /roads` - All approved roads
- `GET /roads/map` - GeoJSON for map
- `GET /roads/{id}` - Road details
- `GET /roads/{id}/feedback` - Feedback (separate load)

**Roads** (Authenticated)
- `POST /roads` - Submit road (pending approval)
- `PUT /roads/{id}` - Update road
- `POST /roads/{id}/image` - Upload image
- `POST /roads/{id}/feedback` - Add comment

**Admin** (API Token Required)
- `GET /admin/pending` - Pending roads
- `POST /admin/approve/{id}` - Approve
- `DELETE /admin/reject/{id}` - Reject

Use: `Authorization: Bearer YOUR_ADMIN_API_TOKEN`

**Search**
- `GET /search?q=place` - OpenStreetMap search

---

## What You Need to Configure

### ✅ Cloudflare R2 (Image Storage)
1. Go to https://dash.cloudflare.com/ → R2
2. Create bucket: `whobuiltmyroad`
3. Generate API token (Read & Write)
4. Enable public access for images
5. Add credentials to `.env`

### ✅ MongoDB
- **Local:** Install MongoDB, use `mongodb://localhost:27017`
- **Cloud:** Use MongoDB Atlas (free tier), get connection string

### ✅ OpenStreetMap
- **No setup needed!** Uses free Nominatim API

---

## Notes

- Admin endpoints use API token (not user login)
- Feedback loads separately from road data
- Images validated: jpg/png/webp, max 10MB
- All operations are async
- Rate limiting included

---

**Built with FastAPI + MongoDB + Cloudflare R2**

