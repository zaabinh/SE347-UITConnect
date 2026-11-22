# SE347 UITConnect V2 — Hướng dẫn chạy local và kiểm thử phần của Na

> **Đọc README.md gốc trước khi chạy.** Tất cả file có sẵn trong ZIP của nhóm được giữ nguyên. Bản của Na bổ sung file mới để tích hợp Post Editor với tag suggestions và không cần sửa file gốc.

## 1. Chuẩn bị môi trường (Windows PowerShell)

- Node.js 20.9+ cho Next.js 15; **Node.js 22.16+ nếu muốn chạy file unit test TypeScript trực tiếp**.
- Python 3.11+, pip, SQL Server và **ODBC Driver 18 for SQL Server** (backend bắt buộc có database để startup).
- Có thể dùng Docker Desktop thay cho SQL Server chạy trực tiếp theo `docker-compose.yml` gốc.
- Cổng thường dùng: frontend 3000, FastAPI 8000, SQL Server 1433.

Tất cả lệnh dưới đây được chạy tại thư mục đã giải nén `SE347-UITConnect-develop`.

## 2. Cấu hình backend (đúng theo README gốc)

Mở PowerShell số 1:

```powershell
cd backend
Copy-Item .env.example .env
```

Chỉnh `backend/.env` theo SQL Server thật của bạn; các giá trị mẫu bên dưới cần được thay thế phù hợp:

```dotenv
DATABASE_URL=mssql+pyodbc://USER:PASSWORD@localhost:1433/StudentForum?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes
APP_ENV=development
JWT_SECRET_KEY=replace-with-a-long-random-secret
FRONTEND_URL=http://127.0.0.1:3000
CORS_ALLOWED_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
PUBLIC_API_URL=http://127.0.0.1:8000
```

**Lưu ý:** Password chứa `@`, `#`, `!`... phải URL-encode. Đừng commit `.env` thật hoặc JWT secret. Để dùng database local, cần bật SQL Server và chắc chắn database/schema có thể được setup.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m scripts.setup_local_db --wait 90
python -m app
```

- Backend: <http://127.0.0.1:8000>
- Swagger: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/health>
- Backend phiên bản mới khởi động từ `app.main:app` / `python -m app`, **không chạy** `backend/main.py` cũ hoặc dùng route `/auth/login` khi API hiện tại định nghĩa khác.

Nếu cần reload khi phát triển:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 3. Chạy frontend

Mở PowerShell số 2 tại thư mục gốc dự án:

```powershell
cd frontend
Copy-Item .env.example .env.local
```

Trong `frontend/.env.local`, cấu hình:

```dotenv
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

**Tùy chọn khi Duy/nhóm Backend cung cấp API gợi ý mới:** Chỉ thêm biến sau **sau khi endpoint thật tồn tại và đã thống nhất contract**:

```dotenv
# Ví dụ minh họa, KHÔNG bật khi backend chưa có route tương ứng:
# TAG_SUGGESTIONS_UPSTREAM_PATH=/api/posts/tags/suggest
```

Backend mới được kỳ vọng nhận `POST` body `{ "title": "...", "content": "...", "limit": 8 }` và trả về `{ "tags": ["python", "docker"] }` hoặc `{ "suggestions": [{ "name": "python" }] }`. Path này chỉ là ví dụ cấu hình, **không phải endpoint đã có trong ZIP gốc**.

Chạy frontend:

```powershell
npm ci
npm run dev
```

- Trang chủ: <http://127.0.0.1:3000>
- **Create Post (Smart Editor):** <http://127.0.0.1:3000/create>
- Alias Create Post: <http://127.0.0.1:3000/post/create>
- **Edit Post:** `http://127.0.0.1:3000/edit/<post_id>` (dùng ID một bài do bạn tạo)

**Bắt buộc đăng nhập tài khoản đủ quyền** để dùng Create/Edit Post. Trang sửa bài chỉ dành cho chủ bài viết theo chính sách hiện tại.

### Có cần chỉnh file gốc để bật tính năng không?

**Không.** File mới `frontend/middleware.ts` rewrite các URL `/create`, `/post/create` và `/edit/:id` sang các trang Smart Editor mới trong `frontend/app/na-post-editor/`. URL trên thanh địa chỉ vẫn như cũ. File `PostEditor.tsx`, route Create/Edit cũ, `forumApi.ts`, `axios.ts`, `package.json`, `package-lock.json` và toàn bộ backend gốc không bị chỉnh sửa.

Khi FE-01 thay đổi kiến trúc frontend hoặc tạo middleware dùng chung, cần **gộp quy tắc rewrite** từ `frontend/middleware.ts` này vào middleware trung tâm để tránh xung đột; trước đó tránh di chuyển hoặc rename các file mới tùy tiện. Đây là cơ chế **add-only** để tuân thủ ràng buộc không sửa file cũ.

## 4. Cơ chế gợi ý tag

1. Chỉ gọi API khi tiêu đề đạt **5 ký tự** và nội dung đạt **20 ký tự** (sau trim).
2. Debounce **700 ms** kể từ lần thay đổi title/content cuối, hủy request cũ, không hiển thị response cũ dù upstream không hỗ trợ abort.
3. Mỗi request bị giới hạn **5 giây** tại client. API gợi ý mới của frontend: **`POST /api/fe/tag-suggestions`**, sử dụng access token đã lưu.
4. BFF Next.js mặc định đọc danh sách **tag đã được duyệt** từ backend gốc `GET /api/posts/tags`, xếp hạng theo mức trùng nội dung với tiêu đề/bài viết (lexical baseline), trả tối đa **8 gợi ý**. Đây **không phải mô hình AI**; khi nhóm đã có endpoint semantic/AI, bật `TAG_SUGGESTIONS_UPSTREAM_PATH` để dùng nguồn mới.
5. Nếu API gợi ý lỗi, client lấy `getTags()` đã tải để tự xếp hạng và hiển thị fallback; nếu không có data, hiển thị error + nút Retry. Người dùng **luôn có thể chọn tag thủ công**.
6. `Suggested for this post` và `Search existing tags` là **hai khu vực riêng biệt**. Gợi ý **không tự được thêm**, tag đã chọn bị ẩn khỏi hai danh sách gợi ý nhưng luôn nằm trong `Selected tags` và có thể gỡ.
7. Khi người dùng tự gõ một tag mới rồi chọn **Add tag** hoặc Enter, tag vẫn được gửi trong `tags` như logic gốc. Với tài khoản thường, backend tách thành `requested_new_tags` chờ duyệt. Trang Edit mới tải cả `tags` và `requested_new_tags` để tránh xóa nhầm yêu cầu chờ duyệt khi lưu.

## 5. Kiểm thử có thể chạy bằng dòng lệnh

Trong PowerShell ở thư mục `frontend`:

```powershell
# Unit tests cho ranking, dedup, debounce, abort và stale responses
node --experimental-strip-types --test tests/smart-tags.test.mjs

# Kiểm tra build gốc + file mới khi đã có dependencies
npm run build

# Kiểm tra các đường dẫn khi dev server đang chạy
node tests/smart-editor.http-smoke.mjs
```

**Tình trạng kiểm thử tại thời điểm đóng gói:** 9 unit tests đã chạy và PASS bằng Node.js 22.16.0. Cú pháp TypeScript/TSX của file mới đã được phân tích bằng TypeScript 5.8.3 và không có lỗi cú pháp. Không thể xác thực full `npm run build`, HTTP smoke test hoặc thao tác Create/Edit thực tế trong môi trường đóng gói vì `npm ci` chưa cài xong dependencies và không có SQL Server đang chạy. Cần tự chạy các bước ở trên trên máy local.

## 6. Checklist smoke test có đăng nhập (Create/Edit)

- [ ] Đăng nhập, vào `/create`: sidebar/topbar và preview còn hoạt động.
- [ ] Title dưới 5 ký tự hoặc content dưới 20 ký tự: chưa gửi yêu cầu suggest; Create vẫn theo quy tắc validate cũ (title tối thiểu 5, content không rỗng).
- [ ] Nhập đủ title và content, ngừng gõ khoảng 700 ms, xem Network: đúng **một** `POST /api/fe/tag-suggestions` sau lần nhập cuối.
- [ ] Gõ liên tục/chuyển nội dung nhanh: response cũ không đè response mới; nếu hủy thì không báo lỗi giả.
- [ ] Click gợi ý: tag được chọn **một lần**, biến mất ở Suggested/Search nhưng hiện tại Selected tags và preview; click gỡ thì có thể gợi ý lại.
- [ ] Search existing tags, chọn tag, kiểm tra không trùng; tự nhập một tag mới và Enter, tag vẫn được lưu dưới dạng yêu cầu chờ duyệt theo backend.
- [ ] Ngắt backend hoặc giả lập request lỗi/timeout bằng DevTools: fallback hoặc error/empty và Retry hiển thị; Add tag thủ công vẫn dùng được.
- [ ] Tạo bài, kiểm tra thông báo trạng thái, ID, điều hướng `/post/{id}` và danh sách tag.
- [ ] Vào `/edit/{id}` của chính bài vừa tạo: dữ liệu title, content, ảnh, tag đã duyệt **và tag chờ duyệt** còn đủ.
- [ ] Sửa title/content, thêm/bớt tag, Save changes: dữ liệu lưu đúng, trang chi tiết được mở. Thử Delete post để đảm bảo modal/API không bị thay đổi.
- [ ] Mở `/edit/{id}` của người khác: chuyển về `/feed` như logic gốc.
- [ ] Dùng màn hình điện thoại/tablet và bàn phím: sidebar/topbar, tag picker, preview không vỡ; vùng gợi ý có trạng thái accessible (aria-live).

## 7. Debug nhanh

| Vấn đề | Kiểm tra |
|---|---|
| Backend không khởi động | `DATABASE_URL`, ODBC Driver 18, SQL Server cổng 1433, `.env`, log lifespan DB |
| Frontend 404 `/create` | Đứng trong thư mục `frontend`, kiểm tra `frontend/middleware.ts` và `frontend/app/na-post-editor/create/page.tsx`, khởi động lại dev server |
| Không gợi ý nào | Tài khoản đã đăng nhập, `GET /api/posts/tags` có dữ liệu, title >= 5, content >= 20 và nội dung có từ khóa khớp tag |
| HTTP 401 gợi ý | Kiểm tra JWT/access token, đăng xuất/đăng nhập lại; backend `GET /api/posts/tags` yêu cầu tài khoản hợp lệ |
| CORS lỗi khi login | `CORS_ALLOWED_ORIGINS` ở backend và `NEXT_PUBLIC_API_URL` ở frontend phải khớp chính xác origin đang dùng (127.0.0.1 khác localhost) |
| Backend suggestion chưa có | Để trống `TAG_SUGGESTIONS_UPSTREAM_PATH`, BFF mặc định vẫn gợi ý lexical từ tag đã duyệt |
| Không chạy được `node --experimental-strip-types` | Dùng Node.js 22.16+ cho test, hoặc chạy frontend bình thường trên Node 20.9+ |

## 8. Các file chỉ được bổ sung

- `frontend/middleware.ts` (add-only routing integration)
- `frontend/app/na-post-editor/create/page.tsx`, `frontend/app/na-post-editor/edit/[id]/page.tsx`
- `frontend/app/api/fe/tag-suggestions/route.ts`
- `frontend/features/smart-tags/` (Post Editor mới, tag picker, API client, debounce/controller, ranking, flow helpers)
- `frontend/tests/smart-tags.test.mjs`, `frontend/tests/smart-editor.http-smoke.mjs`
- `HUONG_DAN_CHAY_LOCAL_NA.md` (tài liệu này)

Để chạy toàn hệ thống, hãy tiếp tục tham khảo README.md và các hướng dẫn migrations/deployment gốc của nhóm.
