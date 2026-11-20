# Đồ án SE347 - UITConnect

## Sinh Viên Thực Hiện

| Họ và tên | MSSV | Phân công |
| --- | --- | --- |

UITConnect là ứng dụng diễn đàn sinh viên dành cho cộng đồng UIT. Dự án gồm xác thực, bài viết, bình luận lồng nhau, report, kiểm duyệt, notification, gợi ý bài viết, hồ sơ người dùng và cấu hình deploy lên Vercel + Render.

## Công nghệ

- Frontend: Next.js 15.5.19, React 19.0.4, TypeScript, Tailwind CSS
- Backend: FastAPI, SQLAlchemy 2.0, Uvicorn
- Database: Microsoft SQL Server qua `pyodbc`
- SQL driver: ODBC Driver 18 for SQL Server
- Xác thực: JWT access/refresh token, Google OAuth tùy chọn
- Deploy: Vercel cho frontend, Render Docker backend, Azure SQL hoặc SQL Server bên ngoài

## Cấu trúc Repository

```text
backend/
  app/
    main.py
    core/
    db/
    modules/  # auth, users, posts, comments, feed, moderation, notifications
  alembic/
  scripts/
  tests/
  pyproject.toml
  Dockerfile

frontend/
  app/
  components/
  lib/
  public/
  package.json
  next.config.ts
  vercel.json

docs/
docker-compose.yml
render.yaml
PROJECT_SUMMARY.md
PROJECT_SUMMARY_vi.md
```

## Trạng thái tính năng

Đã có:

- Đăng ký và đăng nhập local
- JWT refresh/logout
- Google OAuth callback tùy chọn
- Luồng hoàn thiện hồ sơ
- Feed, tìm kiếm, tag, sắp xếp và phân trang
- Tạo, sửa, xóa, like, bookmark, share và report bài viết
- Bình luận lồng nhau và report bình luận
- Hồ sơ người dùng hiện tại/công khai
- Follow/unfollow
- Notification cho kiểm duyệt, like, comment, reply, report, follow và trạng thái tài khoản
- Admin quản lý user, xử lý report, duyệt/từ chối bài, tag và analytics
- Gợi ý bài viết theo trending, tương tự, collaborative và profile

Giới hạn hiện tại:

- Xác minh email đang tạm tắt.
- Gửi email thật chưa hoàn thiện; backend đang in email ra log.
- Notification chưa realtime.
- `/settings` vẫn là giao diện placeholder.

## Biến môi trường

### Backend

Tạo `backend/.env` từ `backend/.env.example`.

Cấu hình được đọc bằng `pydantic-settings` và kiểm tra trước khi khởi động API
hoặc chạy setup database. Các biến `DATABASE_URL` và `CORS_ALLOWED_ORIGINS` là bắt buộc;
`FRONTEND_URL` mặc định là `http://localhost:3000`. Biến môi trường ghi đè giá trị trong `.env`.
`CORS_ALLOWED_ORIGINS` nhận các HTTP origin phân cách bằng dấu phẩy.

Khi deploy, đặt `APP_ENV=production` (Render Blueprint đã cấu hình sẵn).
Production từ chối JWT secret mặc định, giá trị mẫu và secret dưới 32 ký tự.
Tạo secret riêng bằng `python -c "import secrets; print(secrets.token_urlsafe(48))"`
và lưu vào `JWT_SECRET_KEY`. Không ghi secret vào repository.

```env
DATABASE_URL=mssql+pyodbc://USER:PASSWORD@SERVER:1433/StudentForum?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes
APP_ENV=development
JWT_SECRET_KEY=replace-with-a-long-random-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
FRONTEND_URL=http://127.0.0.1:3000
CORS_ALLOWED_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
PUBLIC_API_URL=http://127.0.0.1:8000
```

Ví dụ Azure SQL / Render:

```env
DATABASE_URL=mssql+pyodbc://USER:PASSWORD@SERVER.database.windows.net:1433/StudentForum?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
```

Nếu password DB có ký tự đặc biệt thì cần URL-encode, ví dụ `!` -> `%21`, `@` -> `%40`, `#` -> `%23`.

### Frontend

Tạo `frontend/.env.local` từ `frontend/.env.example`.

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

## Chạy local không dùng Docker

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -m scripts.setup_local_db --wait 90
python -m app
```

Entrypoint chung là `python -m app`, dùng `app.main:app` và factory
`app.factory.create_app()`. Launcher đọc `APP_HOST` (mặc định `0.0.0.0`) và `PORT`
(mặc định `8000`) từ settings, không bật reload. `APP_PORT` không được launcher dùng.
Khi cần reload cho phát triển local, dùng
`uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`.

Dockerfile chạy `python -m app`; Compose và Render kế thừa CMD đó, không ghi đè
lệnh chạy. Compose dùng cổng `8000`, Render dùng `PORT=10000`. GitHub Actions
build cùng Dockerfile và chạy CMD mặc định để kiểm tra `/health` bằng SQLite
trong bộ nhớ; bước này kiểm tra entrypoint, không thay thế test tích hợp SQL Server.
Nếu service Render trước đây có Docker Command tùy chỉnh trong Dashboard,
xóa giá trị đó để service dùng CMD của image.

Lifespan tạo thư mục uploads, kiểm tra kết nối DB bằng `SELECT 1` trước khi nhận
request và đóng connection pool khi shutdown, kể cả khi startup thất bại.
API không tự tạo bảng hoặc chạy migration. `/health` là liveness endpoint;
nó không kiểm tra lại DB trong từng request.

Tài liệu API:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Health check: `http://127.0.0.1:8000/health`

### Frontend

```powershell
cd frontend
npm ci
npm run dev
```

Frontend URL: `http://127.0.0.1:3000`

## Chạy bằng Docker Compose

Tại root repo:

```powershell
docker compose up -d --build
```

Các service:

- SQL Server: `localhost:1433`
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`

## Deploy

### Frontend trên Vercel

Cấu hình Vercel Project Settings:

- Root Directory: `frontend`
- Framework Preset: Next.js
- Install Command: `npm ci`
- Build Command: `npm run build`
- Output Directory: để trống

Biến môi trường:

```env
NEXT_PUBLIC_API_URL=https://your-backend.onrender.com
```

### Backend trên Render

Dùng Blueprint `render.yaml` ở root repo, hoặc tạo Docker Web Service thủ công:

- Dockerfile Path: `backend/Dockerfile`
- Docker Context: `backend`
- Health Check Path: `/health`

Biến môi trường trên Render:

```env
DATABASE_URL=mssql+pyodbc://USER:PASSWORD@SERVER.database.windows.net:1433/StudentForum?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
FRONTEND_URL=https://your-frontend.vercel.app
CORS_ALLOWED_ORIGINS=https://your-frontend.vercel.app
PUBLIC_API_URL=https://your-backend.onrender.com
JWT_SECRET_KEY=generate-a-long-random-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
RUN_DB_SETUP_ON_START=false
```

Chuẩn bị schema bằng `python -m scripts.setup_local_db --wait 90` và chạy các
migration đã được review trong bước deploy riêng, trước khi khởi động worker.
Baseline `20261119_01` đã được kiểm chứng trên SQL Server thật. Database trống dùng
`python -m scripts.migrate upgrade`; database có schema tương đương dùng
`python -m scripts.migrate verify` rồi `python -m scripts.migrate adopt` để stamp,
không chạy lại CREATE TABLE. Quy trình expand–backfill–contract và workflow migration
riêng được mô tả tại [backend/alembic/README.md](backend/alembic/README.md).
Entrypoint không chạy setup DB, kể cả khi biến cũ `RUN_DB_SETUP_ON_START` được bật.
Khởi động thất bại nếu không kết nối được DB. Dùng duy nhất `python -m app`
để khởi động backend; alias launcher cũ đã được loại bỏ.

## Route chính

Frontend:

- `/`
- `/login`
- `/register`
- `/feed`
- `/create`
- `/edit/[id]`
- `/post/[id]`
- `/profile/[id]`
- `/profile/edit`
- `/dashboard`
- `/settings`

Backend:

REST API dùng prefix `/api/v1`. Xem [API contract](docs/API_CONTRACT.md) để có
danh sách endpoint, DTO, phân quyền, lỗi và hướng dẫn chuyển đổi từ API cũ.
Đây là tài liệu REST API có thẩm quyền duy nhất; OpenAPI máy đọc được sinh tại
`/openapi.json`, Swagger UI tại `/docs` và ReDoc tại `/redoc`.

## Kiểm tra

Backend:

```powershell
cd backend
python -m pytest -q
```

Frontend:

```powershell
cd frontend
npm audit
npm run build
```

Docker Compose:

```powershell
docker compose -f docker-compose.yml config
```


## Backend transaction architecture

Write use cases use Application Service + Repository + Unit of Work; password
reset email is delivered through a durable outbox. Deploy migration
`20261119_02` before the new API and run its separate worker. See
[transaction and outbox runbook](docs/BACKEND_TRANSACTIONS.md).

