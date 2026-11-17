# Backend Setup & Deployment Guide

## Quick Start

### 1. Prerequisites
- Python 3.8+
- pip (Python package manager)
- Virtual environment (recommended)

### 2. Installation

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy example file
cp .env.example .env

# Edit .env with your settings
# JWT_SECRET_KEY should be a long random string
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4. Initialize Database

```bash
# Tables are automatically created on startup
# Just run the server!
```

### 5. Run Development Server

```bash
# Using FastAPI's dev server (recommended)
fastapi dev app/main.py

# Or using uvicorn directly
uvicorn app.main:app --reload

# Or using Python directly
python -m app.main
```

Server will be available at: **http://localhost:8000**

### 6. Access API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## Project Structure Explanation

```
backend/
  app/
    __init__.py
    main.py
    core/       # config.py, security.py, exceptions.py
    db/         # base.py, session.py, init/ (existing SQL scripts)
    modules/    # auth, users, posts, comments, feed, moderation, notifications
  alembic/
  scripts/
  tests/
  pyproject.toml
  Dockerfile
```

## Key Components

### Database (app/db/session.py)
- SQLAlchemy engine and session factory
- Dependency injection via `get_db()`
- Uses Microsoft SQL Server via `pyodbc` and ODBC Driver 18

### Models (app/modules/*/models.py)
- **User**: Stores user credentials and profile
- **Post**: Blog posts/discussions
- **Comment**: Replies to posts
- **Follow**: Social graph relationships
- **Bookmark**: User's saved posts

All models have:
- UUID primary keys
- Timestamps (created_at, updated_at)
- Foreign key relationships with cascade deletes

### Schemas (app/modules/*/schemas.py)
- Pydantic v2 models for request/response validation
- Automatic OpenAPI documentation
- Type safety and data validation

### Authentication (app/modules/auth/dependencies.py)
- JWT token generation and validation
- OAuth2PasswordBearer scheme
- `get_current_user()` dependency for protected endpoints

### Routers (app/modules/*/router.py)
- **posts.py**: Create, read, update, delete posts
- **comments.py**: Comment management
- **follow.py**: Follow/unfollow users and lists
- **feed.py**: Personalized feed from followed users

## Security Implementation

### ✅ Never Trust Client Input
```python
# WRONG - NEVER DO THIS:
@router.post("/posts")
def create_post(post: PostCreate, current_user: User, db: Session):
    post.author_id = request.body.author_id  # ❌ SECURITY ISSUE!
    
# RIGHT - ALWAYS DO THIS:
@router.post("/posts")
def create_post(post: PostCreate, current_user: User, db: Session):
    db_post = Post(
        author_id=current_user.id  # ✅ ALWAYS USE current_user
    )
```

### ✅ Verify Ownership
```python
if post.author_id != current_user.id:
    raise HTTPException(status_code=403, detail="Forbidden")
```

### ✅ Use get_current_user() Dependency
```python
# This dependency validates JWT token
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # Extract and validate user from JWT
    return user
```

## API Testing

### Using Swagger UI (Interactive)
1. Go to http://localhost:8000/docs
2. Authorize with "Authorize" button
3. Click "Try it out" on any endpoint

### Using cURL

#### Create Post
```bash
curl -X POST http://localhost:8000/api/posts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {your_token}" \
  -d '{"title": "My Post", "content": "Content here"}'
```

#### Get Posts
```bash
curl http://localhost:8000/api/posts?skip=0&limit=10
```

#### Follow User
```bash
curl -X POST http://localhost:8000/api/follow/{user_id} \
  -H "Authorization: Bearer {your_token}"
```

### Using Python Requests
```python
import requests

token = "your_jwt_token_here"
headers = {"Authorization": f"Bearer {token}"}

# Create post
response = requests.post(
    "http://localhost:8000/api/posts",
    json={"title": "My Post", "content": "..."},
    headers=headers
)
print(response.json())

# Get posts
response = requests.get("http://localhost:8000/api/posts")
print(response.json())
```

## Production Deployment

### 1. Set Production Environment
```bash
# .env file
JWT_SECRET_KEY=very-long-random-string-from-secrets.token_urlsafe()
DATABASE_URL=mssql+pyodbc://user:password@server.database.windows.net:1433/StudentForum?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
CORS_ALLOWED_ORIGINS=https://your-frontend.vercel.app
FRONTEND_URL=https://your-frontend.vercel.app
```

### 2. Using Gunicorn + Uvicorn
```bash
pip install gunicorn

gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
```

### 3. Using Docker
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t forum-api .
docker run -p 8000:8000 forum-api
```

### 4. Database Setup (SQL Server)
```bash
# Set DATABASE_URL in .env
DATABASE_URL=mssql+pyodbc://user:password@server:1433/StudentForum?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes

# Create missing tables and run upgrade script
python -m scripts.setup_local_db --wait 90
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'app'"
**Solution**: Make sure you're running from the backend directory and have activated your virtual environment.

### Issue: "Can't open lib 'ODBC Driver 18 for SQL Server'"
**Solution**: Install ODBC Driver 18 locally or run the provided backend Docker image, which installs `msodbcsql18`.

### Issue: 401 Unauthorized errors
**Solution**: 
1. Make sure you have a valid JWT token
2. Send it in Authorization header: `Authorization: Bearer {token}`
3. Check token expiration in .env

### Issue: CORS errors in frontend
**Solution**: Check allowed origins in main.py CORS configuration

### Issue: Database migrations
**Solution**: Tables are created automatically via SQLAlchemy. To reset:
```python
# In Python shell
from app.database import Base, engine
Base.metadata.drop_all(bind=engine)  # Drop all tables
Base.metadata.create_all(bind=engine)  # Create fresh tables
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| JWT_SECRET_KEY | none | JWT signing key (MUST set in production) |
| DATABASE_URL | none | SQL Server connection string using ODBC Driver 18 |
| HOST | 0.0.0.0 | Server host |
| PORT | 8000 | Server port |
| ACCESS_TOKEN_EXPIRE_MINUTES | 30 | JWT token lifetime |

## Performance Tips

1. **Database Indexes**: Fields like `author_id`, `post_id`, `created_at` are indexed
2. **Pagination**: Always use limit/offset for large datasets
3. **Eager Loading**: Relationships are optimized to prevent N+1 queries
4. **Connection Pooling**: SQLAlchemy manages connection pool automatically

## Next Steps

1. ✅ Backend is ready for production use
2. 🔗 Connect to your frontend
3. 🔐 Implement user registration/login (use existing auth routes if available)
4. 📧 Add email notifications
5. 🔍 Add search functionality
6. ⭐ Add like/reaction system

---

For detailed API documentation, see `API_DOCUMENTATION.md`
