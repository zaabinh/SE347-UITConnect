# UITConnect V2 — REST API Contract v1

<!-- OPENAPI_CONTRACT_SHA256: 921f1c067ad554c0025c3f162d0acd6f09ffd9810c47aa6f31e41c3fe985f117 -->

> Tài liệu REST API có thẩm quyền duy nhất, viết theo router đã đăng ký, DTO và application/domain service. OpenAPI 3.1 được sinh từ ứng dụng tại `/openapi.json`; không có bản OpenAPI viết tay cạnh tranh. Giá trị ID/token trong ví dụ chỉ minh họa, không phải credential dùng được.

## 1. Tổng quan (Overview)

UITConnect V2 dùng Modular Monolith: FastAPI/Pydantic v2 → application service → domain/repository → SQLAlchemy/SQL Server, Unit of Work và Transactional Outbox. Central router chỉ ghép module; router không sở hữu commit. Unified entrypoint vẫn là `python -m app`.

Base URL local: `http://localhost:8000`; API nghiệp vụ: `{BASE_URL}/api/v1`. Frontend dùng cấu hình API origin tương ứng. Có **60 endpoint nghiệp vụ**, **62 REST operations** nếu tính `GET /` và `GET /health`. Swagger `/docs`, ReDoc `/redoc`, OpenAPI `/openapi.json` và static `/uploads/{filename}` là hạ tầng do framework phục vụ, không được tính thành operation REST trong bảng OpenAPI. Không có alias endpoint cũ hoặc route business ngoài `/api/v1`.

Request/response thường là `application/json`; upload dùng `multipart/form-data`; lỗi là `application/problem+json`; redirect OAuth là 307; 204 không có body. Bearer access JWT được gửi qua `Authorization`; refresh token trong JSON chỉ dùng cho refresh/logout. Không đổi kiến trúc JWT/session/OAuth trong đợt chuẩn hóa này.

Hai endpoint hạ tầng cũng có contract dưới đây.

### `GET /` — Thông tin ứng dụng

**Định danh:** operation_id `system_root`; module `infrastructure`. Thông tin ứng dụng.

**Xác thực và quyền:** Public: không yêu cầu Authorization. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. Không có request body.

Không có path/query parameter.

Ví dụ request: `GET /`; body không gửi.

**Response:** `200`, `application/json`, `RootResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "message": "Welcome to Student Forum API",
  "version": "1.0.0",
  "docs": "/docs",
  "openapi_schema": "/openapi.json"
}
```

**Lỗi:** 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ đọc thông tin tĩnh; không kiểm tra kết nối DB. Không query/body/auth.

### `GET /health` — Kiểm tra liveness

**Định danh:** operation_id `system_health`; module `infrastructure`. Kiểm tra liveness.

**Xác thực và quyền:** Public: không yêu cầu Authorization. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. Không có request body.

Không có path/query parameter.

Ví dụ request: `GET /health`; body không gửi.

**Response:** `200`, `application/json`, `HealthResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "status": "healthy",
  "message": "Student Forum API is running"
}
```

**Lỗi:** 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ trả liveness tĩnh healthy; không phải readiness probe của DB/Outbox/R2. Không query/body/auth.

## 2. Tiêu chuẩn thiết kế API (API Design Standards)

Paths chữ thường, plural resource, kebab-case, không trailing slash. Method/path sai không tự chuyển sang alias v1; trailing slash không thuộc hợp đồng. `operation_id` duy nhất, khai báo rõ theo `{domain}_{operation}`. GET chỉ đọc; POST tạo tài nguyên/sự kiện; PUT đặt trạng thái đích; PATCH sửa một phần; DELETE bỏ tài nguyên/membership.

Success: 200 đọc/cập nhật có representation, 201 tạo, 202 đã tiếp nhận async, 204 không body; OAuth 307. Error chuẩn: 400 quy tắc nghiệp vụ, 401 xác thực, 403 quyền, 404 thiếu, 409 xung đột, 413 upload lớn, 422 validation, 429 bị giới hạn nếu tầng triển khai áp dụng, 500 lỗi nội bộ. API hiện chưa có rate limiter ứng dụng; không hứa quota/Retry-After hoặc tự phát sinh 429. 405 cho method không được hỗ trợ.

**Quyền hiển thị V của post:** deleted/không tồn tại → 404; active → được đọc/tương tác bởi active user; pending/rejected → chỉ tác giả hoặc admin, người khác 403. Kiểm tra này cũng áp dụng views/like/bookmark/share/report/comment. Similar chỉ lấy nguồn active và trả rỗng nếu không active (mục 8). Quyền sửa post vẫn chỉ tác giả; quyền xóa tác giả/admin và giới hạn comment ở mục 6.

**PATCH:** omitted giữ nguyên; explicit null chỉ cho trường nullable về nghiệp vụ (UpdatePostRequest chỉ cover_image; UpdateProfileRequest các chuỗi tùy chọn, không full_name/interest_tags). Empty patch và field lạ bị 422. OpenAPI biểu diễn các field omittable độc lập với nullable; field không nullable có thể bỏ qua nhưng không thể gửi null. AuthRequest cũng extra=forbid. Các request khác giữ extra policy Pydantic hiện tại (ignore nếu không khai báo forbid); không hứa reject field lạ ở mọi POST.

**Pagination:** offset `(page−1)*page_size`, không cursor. Meta có page/page_size/total/total_pages; total=0 → total_pages=0. Trang vượt cuối → items=[] và meta.total giữ tổng đúng của tập/cửa sổ; invalid page/page_size → 422, không clamp request. Feed/recommendations thường page=1/page_size=10, max 50; admin page=1/page_size=20, max 100. Mảng/tree cũ tiếp tục là mảng/tree, không bọc meta. Các cap ứng viên được ghi rõ từng endpoint; dữ liệu mới/tương tác có thể làm thứ hạng đổi giữa hai request, không có snapshot pagination. Tie-break ID bảo đảm thứ tự khi điểm/cột chính bằng nhau.

**Ngày giờ:** `UtcDateTime` là datetime ISO 8601 UTC, ví dụ `2026-11-19T12:00:00Z`; SQL datetime naive được hiểu là UTC. ID user là string, các ID post/comment/tag/report/notification là integer, không ngầm hứa path integer phải >0 (hiện chỉ ràng buộc kiểu). Query là scalar, không có filter/sort tùy ý ngoài danh sách từng endpoint.

**Idempotency/concurrency:** PUT/DELETE like/bookmark/follow đặt membership đích; lặp không nhân notification. Terminal moderation trùng quyết định không lặp audit/notification; khác quyết định 409. POST tạo bài/share/comment/view/upload không có Idempotency-Key; caller không tự retry mù sau timeout. SQL Server UnitOfWork dùng transaction-owned `sp_getapplock` theo aggregate, chờ 10 giây; thất bại trả 409 CONCURRENT_MODIFICATION. Không có migration schema mới chỉ để hỗ trợ API v1. DB write, audit/notification và outbox tương ứng chia sẻ transaction; rollback khi lỗi. Outbox worker giao email sau commit, không bảo đảm email đã được nhận khi response về.

**Headers:** server tạo UUID mới cho mỗi HTTP request ở `X-Request-ID`, không tin/copy ID do client cung cấp. CORS expose X-Request-ID và Location. 401 thêm `WWW-Authenticate: Bearer`. Create/share post trả Location; không hứa Location cho các POST khác.

## 3. Tóm tắt endpoint (API Endpoint Summary)

| Method | Endpoint | Description | Authentication | Request DTO | Response DTO | Status |
|---|---|---|---|---|---|---|
| `GET` | `/` | Thông tin ứng dụng | public | `Không có` | `RootResponse` | 200 |
| `GET` | `/api/v1/admin/analytics/overview` | Đọc thống kê quản trị | admin | `Không có` | `AdminAnalyticsResponse` | 200 |
| `GET` | `/api/v1/admin/posts/pending` | Liệt kê bài chờ duyệt | admin | `Không có` | `AdminPostsListResponse` | 200 |
| `PUT` | `/api/v1/admin/posts/{post_id}/moderation` | Duyệt hoặc từ chối bài | admin | `ModeratePostRequest` | `AdminPostModerationResponse` | 200 |
| `GET` | `/api/v1/admin/reports` | Quản trị danh sách report | admin | `Không có` | `AdminReportsListResponse` | 200 |
| `PUT` | `/api/v1/admin/reports/{report_id}/moderation` | Thiết lập quyết định report | admin | `ModerateReportRequest` | `ReportResponse` | 200 |
| `GET` | `/api/v1/admin/tags` | Quản trị danh mục tag | admin | `Không có` | `TagResponse[]` | 200 |
| `POST` | `/api/v1/admin/tags` | Tạo tag | admin | `CreateTagRequest` | `TagResponse` | 201 |
| `DELETE` | `/api/v1/admin/tags/{tag_id}` | Xóa tag | admin | `Không có` | `Không body` | 204 |
| `PATCH` | `/api/v1/admin/tags/{tag_id}` | Đổi tên tag | admin | `UpdateTagRequest` | `TagResponse` | 200 |
| `GET` | `/api/v1/admin/users` | Quản trị danh sách user | admin | `Không có` | `AdminUsersListResponse` | 200 |
| `DELETE` | `/api/v1/admin/users/{user_id}/ban` | Thiết lập user active | admin | `Không có` | `AdminUserResponse` | 200 |
| `PUT` | `/api/v1/admin/users/{user_id}/ban` | Thiết lập user bị ban | admin | `BanUserRequest` | `AdminUserResponse` | 200 |
| `POST` | `/api/v1/auth/forgot-password` | Yêu cầu đặt lại password | public | `ForgotPasswordRequest` | `MessageResponse` | 202 |
| `GET` | `/api/v1/auth/google/callback` | Nhận Google OAuth callback | public | `Không có` | `Redirect + Location` | 307 |
| `GET` | `/api/v1/auth/google/login` | Bắt đầu Google OAuth | public | `Không có` | `Redirect + Location` | 307 |
| `POST` | `/api/v1/auth/login` | Đăng nhập | public | `LoginRequest` | `TokenResponse` | 200 |
| `POST` | `/api/v1/auth/logout` | Đăng xuất session | public | `LogoutRequest` | `Không body` | 204 |
| `GET` | `/api/v1/auth/me` | Đọc định danh session hiện tại | authenticated | `Không có` | `CurrentUserIdentityResponse` | 200 |
| `POST` | `/api/v1/auth/refresh` | Làm mới access token | public | `RefreshTokenRequest` | `TokenResponse` | 200 |
| `POST` | `/api/v1/auth/register` | Đăng ký tài khoản | public | `RegisterRequest` | `VerificationResponse` | 201 |
| `POST` | `/api/v1/auth/resend-verification` | Gửi lại xác minh — hiện tắt | public | `ResendVerificationRequest` | `VerificationResponse` | 200 |
| `POST` | `/api/v1/auth/reset-password` | Đặt lại password | public | `ResetPasswordRequest` | `MessageResponse` | 200 |
| `POST` | `/api/v1/auth/verify-email` | Xác minh email — hiện tắt | public | `VerifyEmailRequest` | `MessageResponse` | 200 |
| `GET` | `/api/v1/feed` | Đọc feed và tìm kiếm | active_user | `Không có` | `PostListResponse` | 200 |
| `POST` | `/api/v1/media/images` | Upload ảnh lên filesystem | active_user | `multipart:file` | `UploadImageResponse` | 201 |
| `GET` | `/api/v1/notifications` | Đọc thông báo của mình | active_user | `Không có` | `NotificationResponse[]` | 200 |
| `DELETE` | `/api/v1/notifications/{notification_id}` | Xóa thông báo đã đọc | active_user | `Không có` | `Không body` | 204 |
| `PUT` | `/api/v1/notifications/{notification_id}/read` | Đánh dấu thông báo đã đọc | active_user | `Không có` | `NotificationResponse` | 200 |
| `POST` | `/api/v1/posts` | Tạo bài viết | active_user | `CreatePostRequest` | `PostResponse` | 201 |
| `DELETE` | `/api/v1/posts/{post_id}` | Xóa mềm bài viết | active_user | `Không có` | `Không body` | 204 |
| `GET` | `/api/v1/posts/{post_id}` | Đọc chi tiết bài viết | active_user | `Không có` | `PostResponse` | 200 |
| `PATCH` | `/api/v1/posts/{post_id}` | Cập nhật một phần bài viết | active_user | `UpdatePostRequest` | `PostResponse` | 200 |
| `DELETE` | `/api/v1/posts/{post_id}/bookmarks/me` | Thiết lập chưa bookmark | active_user | `Không có` | `Không body` | 204 |
| `PUT` | `/api/v1/posts/{post_id}/bookmarks/me` | Thiết lập đã bookmark | active_user | `Không có` | `BookmarkResponse` | 200 |
| `GET` | `/api/v1/posts/{post_id}/comments` | Đọc cây bình luận | active_user | `Không có` | `CommentResponse[]` | 200 |
| `POST` | `/api/v1/posts/{post_id}/comments` | Tạo bình luận hoặc reply | active_user | `CreateCommentRequest` | `CommentResponse` | 201 |
| `POST` | `/api/v1/posts/{post_id}/comments/{comment_id}/reports` | Báo cáo bình luận | active_user | `CreateReportRequest` | `ReportResponse` | 201 |
| `DELETE` | `/api/v1/posts/{post_id}/likes/me` | Thiết lập chưa like | active_user | `Không có` | `Không body` | 204 |
| `PUT` | `/api/v1/posts/{post_id}/likes/me` | Thiết lập đã like | active_user | `Không có` | `LikeResponse` | 200 |
| `POST` | `/api/v1/posts/{post_id}/reports` | Báo cáo bài viết | active_user | `CreateReportRequest` | `ReportResponse` | 201 |
| `POST` | `/api/v1/posts/{post_id}/shares` | Tạo bài chia sẻ | active_user | `SharePostRequest` | `SharePostResponse` | 201 |
| `POST` | `/api/v1/posts/{post_id}/views` | Ghi nhận một lượt xem | active_user | `Không có` | `Không body` | 204 |
| `GET` | `/api/v1/recommendations/collaborative` | Gợi ý cộng tác | active_user | `Không có` | `CollaborativePostListResponse` | 200 |
| `GET` | `/api/v1/recommendations/posts/{post_id}/similar` | Gợi ý bài tương tự | active_user | `Không có` | `SimilarPostListResponse` | 200 |
| `GET` | `/api/v1/recommendations/profile` | Gợi ý theo hồ sơ | active_user | `Không có` | `ProfileBasedPostListResponse` | 200 |
| `GET` | `/api/v1/recommendations/profile-analysis` | Phân tích hồ sơ cho gợi ý | active_user | `Không có` | `ProfileAnalysisResponse` | 200 |
| `GET` | `/api/v1/recommendations/profile-summary` | Tóm tắt hồ sơ cho gợi ý | active_user | `Không có` | `UserProfileSummary` | 200 |
| `GET` | `/api/v1/recommendations/trending` | Gợi ý bài xu hướng | active_user | `Không có` | `TrendingPostListResponse` | 200 |
| `GET` | `/api/v1/tags` | Danh mục tag cho người dùng | active_user | `Không có` | `TagResponse[]` | 200 |
| `GET` | `/api/v1/tags/trending` | Gợi ý tag xu hướng | active_user | `Không có` | `TrendingTagListResponse` | 200 |
| `GET` | `/api/v1/users/by-username/{username}` | Đọc hồ sơ theo username | active_user | `Không có` | `PublicUserProfileResponse` | 200 |
| `GET` | `/api/v1/users/by-username/{username}/comments` | Liệt kê bình luận của user | active_user | `Không có` | `UserCommentResponse[]` | 200 |
| `GET` | `/api/v1/users/by-username/{username}/posts` | Liệt kê bài của user | active_user | `Không có` | `UserPostResponse[]` | 200 |
| `GET` | `/api/v1/users/me` | Đọc hồ sơ đầy đủ của mình | active_user | `Không có` | `CurrentUserProfileResponse` | 200 |
| `PATCH` | `/api/v1/users/me` | Cập nhật một phần hồ sơ của mình | active_user | `UpdateProfileRequest` | `CurrentUserProfileResponse` | 200 |
| `GET` | `/api/v1/users/me/bookmarks` | Liệt kê bookmark của mình | active_user | `Không có` | `UserPostResponse[]` | 200 |
| `PUT` | `/api/v1/users/me/profile-completion` | Hoàn thành profile | authenticated | `CompleteProfileRequest` | `CurrentUserIdentityResponse` | 200 |
| `GET` | `/api/v1/users/{user_id}` | Đọc user công khai theo ID | authenticated | `Không có` | `PublicUserSummary` | 200 |
| `DELETE` | `/api/v1/users/{user_id}/followers/me` | Thiết lập không follow | active_user | `Không có` | `Không body` | 204 |
| `PUT` | `/api/v1/users/{user_id}/followers/me` | Thiết lập đang follow | active_user | `Không có` | `FollowResponse` | 200 |
| `GET` | `/health` | Kiểm tra liveness | public | `Không có` | `HealthResponse` | 200 |

Nhãn auth trong bảng được định nghĩa chính xác ở mục 14; public DTO không có nghĩa endpoint không cần đăng nhập. Chi tiết mỗi operation nằm ở mục 1, 4–11.

## 4. Hợp đồng API xác thực (Authentication API Contracts)

Email verification hiện **tắt**: register tạo is_verified=true; verify/resend chỉ validate request rồi trả thông điệp tạm tắt. `require_active_verified_user` là tên helper lịch sử: hiện thực kiểm tra active + profile completed, không kiểm tra is_verified. Không quảng bá các token verification trong ví dụ thành chức năng có sẵn. Profile completion chuyển sang mục Users tại `PUT /api/v1/users/me/profile-completion`.

Google callback mặc định mới là `http://localhost:8000/api/v1/auth/google/callback` (hoặc origin công khai tương ứng). Operator phải cập nhật `GOOGLE_REDIRECT_URI` và Authorized redirect URI của Google Cloud cùng lúc deploy. Google redirect giữ query token như trước; đây là giới hạn bảo mật hiện hữu của luồng, không phải OAuth redesign. Không có state/PKCE hay cookie-session mới được cam kết ở v1.

### `POST /api/v1/auth/forgot-password` — Yêu cầu đặt lại password

**Định danh:** operation_id `auth_forgot_password`; module `auth`. Yêu cầu đặt lại password.

**Xác thực và quyền:** Public: không yêu cầu Authorization. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Content-Type: application/json` nếu có body JSON.

Không có path/query parameter.

Body bắt buộc: `ForgotPasswordRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "email": "student@example.com"
}
```

**Response:** `202`, `application/json`, `MessageResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "message": "If the email exists, a password reset email has been queued."
}
```

**Lỗi:** 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 403 FORBIDDEN: tài khoản banned theo chính sách hiện tại; thông điệp 202 chung chỉ áp dụng nhánh được chấp nhận/không tồn tại. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** 202 nghĩa là đã tiếp nhận, chưa bảo đảm email đã giao. Nếu tài khoản đủ điều kiện tồn tại, tạo reset token và email Outbox trong cùng Unit of Work; tài khoản không tồn tại/deleted vẫn trả cùng thông điệp. Không trả reset token cho client. POST lặp có thể tạo yêu cầu mới.

### `GET /api/v1/auth/google/callback` — Nhận Google OAuth callback

**Định danh:** operation_id `auth_google_callback`; module `auth`. Nhận Google OAuth callback.

**Xác thực và quyền:** Public: không yêu cầu Authorization. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. Không có request body.

Header `User-Agent` tùy chọn và IP từ request được ghi vào AuthSession; không cần client tự gửi IP trong JSON.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| query | `code` | `string` | Có | — | Authorization code do Google gửi callback, bắt buộc. |

Ví dụ request: `GET /api/v1/auth/google/callback?code=example-google-code`; body không gửi.

**Response:** `307 Temporary Redirect`, không có DTO/body JSON; `Location` chứa URL đích được mô tả trong hành vi. Browser theo redirect; không gọi axios với kỳ vọng JSON. `X-Request-ID` có trên response.

Ví dụ response (giá trị URL/token minh họa):

```http
HTTP/1.1 307 Temporary Redirect
Location: http://localhost:3000/auth/callback?access_token=example-access-jwt-value&refresh_token=example-refresh-token-value&next=%2Ffeed&email=student%40example.com&verified=true&profile_completed=true
X-Request-ID: 44444444-4444-4444-8444-444444444444
```

**Lỗi:** 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 400 BAD_REQUEST: Google không trả email; 403 FORBIDDEN: tài khoản banned; 404 NOT_FOUND: tài khoản deleted; 500 INTERNAL_ERROR: cấu hình/provider lỗi. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Đổi code với Google, lấy email, tạo user nếu chưa có và tạo session trong Unit of Work. 307 đến FRONTEND_URL/auth/callback với access_token, refresh_token, next, email, verified, profile_completed trong query như hành vi hiện tại; next là /feed hoặc /complete-profile. Code của provider không bảo đảm tái sử dụng.

### `GET /api/v1/auth/google/login` — Bắt đầu Google OAuth

**Định danh:** operation_id `auth_google_login`; module `auth`. Bắt đầu Google OAuth.

**Xác thực và quyền:** Public: không yêu cầu Authorization. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. Không có request body.

Không có path/query parameter.

Ví dụ request: `GET /api/v1/auth/google/login`; body không gửi.

**Response:** `307 Temporary Redirect`, không có DTO/body JSON; `Location` chứa URL đích được mô tả trong hành vi. Browser theo redirect; không gọi axios với kỳ vọng JSON. `X-Request-ID` có trên response.

Ví dụ response (giá trị URL/token minh họa):

```http
HTTP/1.1 307 Temporary Redirect
Location: https://accounts.google.com/o/oauth2/v2/auth?client_id=example-client&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fv1%2Fauth%2Fgoogle%2Fcallback&response_type=code&scope=openid+email+profile&access_type=offline&prompt=consent
X-Request-ID: 44444444-4444-4444-8444-444444444444
```

**Lỗi:** 500 INTERNAL_ERROR khi có lỗi không dự kiến. 500 INTERNAL_ERROR: Google OAuth chưa được cấu hình. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** 307 với Location đến Google, scope openid email profile, access_type=offline, prompt=consent. Không có JSON body. Giữ nguyên luồng OAuth hiện hành.

### `POST /api/v1/auth/login` — Đăng nhập

**Định danh:** operation_id `auth_login`; module `auth`. Đăng nhập.

**Xác thực và quyền:** Public: không yêu cầu Authorization. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Content-Type: application/json` nếu có body JSON.

Header `User-Agent` tùy chọn và IP từ request được ghi vào AuthSession; không cần client tự gửi IP trong JSON.

Không có path/query parameter.

Body bắt buộc: `LoginRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "identifier": "student@example.com",
  "password": "ExamplePass123!"
}
```

**Response:** `200`, `application/json`, `TokenResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "access_token": "example-access-jwt-value",
  "refresh_token": "example-refresh-token-value",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Lỗi:** 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 404 NOT_FOUND: không có tài khoản hoặc đã deleted; 401 UNAUTHORIZED: sai password; 403 FORBIDDEN: bị banned. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** identifier là email hoặc username, được trim/lowercase. Tạo AuthSession và cặp access/refresh token; ghi IP và User-Agent nếu có. POST lặp tạo session mới. Không bắt buộc hoàn thành profile để đăng nhập.

### `POST /api/v1/auth/logout` — Đăng xuất session

**Định danh:** operation_id `auth_logout`; module `auth`. Đăng xuất session.

**Xác thực và quyền:** Public: không yêu cầu Authorization. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Content-Type: application/json` nếu có body JSON.

Không có path/query parameter.

Body bắt buộc: `LogoutRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "refresh_token": "example-refresh-token-value"
}
```

**Response:** `204 No Content`, body rỗng, không gửi JSON `null`/`{}`; `X-Request-ID` có trên response.

**Lỗi:** 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Xóa session theo refresh_token. Session đã mất vẫn thành công 204, không body. Không thu hồi ngay access JWT đã cấp; client xóa token cục bộ.

### `GET /api/v1/auth/me` — Đọc định danh session hiện tại

**Định danh:** operation_id `auth_me`; module `auth`. Đọc định danh session hiện tại.

**Xác thực và quyền:** Bearer access JWT hợp lệ; user tồn tại, không deleted/banned. Cho phép profile chưa hoàn thành; không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

Không có path/query parameter.

Ví dụ request: `GET /api/v1/auth/me`; body không gửi.

**Response:** `200`, `application/json`, `CurrentUserIdentityResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "username": "uit_student",
  "email": "student@example.com",
  "full_name": "Nguyễn Minh An",
  "avatar_url": null,
  "bio": "Sinh viên công nghệ thông tin",
  "major": "Software Engineering",
  "academic_year": "2026",
  "career_goal": "Backend developer",
  "interest_tags": [
    "python"
  ],
  "role": "Student",
  "status": "active",
  "provider": "local",
  "is_verified": true,
  "profile_completed": true
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned. 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ đọc CurrentUserIdentityResponse: có email/provider/is_verified/profile_completed của chính user. Cho phép user chưa hoàn thành profile. Không có các bộ đếm của hồ sơ đầy đủ.

### `POST /api/v1/auth/refresh` — Làm mới access token

**Định danh:** operation_id `auth_refresh`; module `auth`. Làm mới access token.

**Xác thực và quyền:** Public: không yêu cầu Authorization. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Content-Type: application/json` nếu có body JSON.

Không có path/query parameter.

Body bắt buộc: `RefreshTokenRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "refresh_token": "example-refresh-token-value"
}
```

**Response:** `200`, `application/json`, `TokenResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "access_token": "example-access-jwt-value",
  "refresh_token": "example-refresh-token-value",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Lỗi:** 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 401 UNAUTHORIZED: session thiếu/hết hạn/token sai; 403 FORBIDDEN: user banned. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Kiểm tra refresh token và AuthSession, trả access token mới cùng refresh token cũ (không rotation). Session không hợp lệ được xóa và commit trước khi trả lỗi. Access token có thể khác giữa các lần gọi.

### `POST /api/v1/auth/register` — Đăng ký tài khoản

**Định danh:** operation_id `auth_register`; module `auth`. Đăng ký tài khoản.

**Xác thực và quyền:** Public: không yêu cầu Authorization. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Content-Type: application/json` nếu có body JSON.

Không có path/query parameter.

Body bắt buộc: `RegisterRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "username": "uit_student",
  "email": "student@example.com",
  "password": "ExamplePass123!",
  "full_name": "Nguyễn Minh An"
}
```

**Response:** `201`, `application/json`, `VerificationResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "message": "Registration successful. You can now log in.",
  "verification_token": null
}
```

**Lỗi:** 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 400 BAD_REQUEST: email/username đã tồn tại hoặc xung đột đăng ký. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chuẩn hóa email/username về chữ thường, băm password và tạo tài khoản local Student active, is_verified=true trong Unit of Work. Email verification hiện tắt; không gửi email xác minh. POST lặp không idempotent.

### `POST /api/v1/auth/resend-verification` — Gửi lại xác minh — hiện tắt

**Định danh:** operation_id `auth_resend_verification`; module `auth`. Gửi lại xác minh — hiện tắt.

**Xác thực và quyền:** Public: không yêu cầu Authorization. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Content-Type: application/json` nếu có body JSON.

Không có path/query parameter.

Body bắt buộc: `ResendVerificationRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "email": "student@example.com"
}
```

**Response:** `200`, `application/json`, `VerificationResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "message": "Email verification is temporarily disabled.",
  "verification_token": null
}
```

**Lỗi:** 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Vẫn validate email rồi trả message Email verification is temporarily disabled. verification_token=null; không enqueue email.

### `POST /api/v1/auth/reset-password` — Đặt lại password

**Định danh:** operation_id `auth_reset_password`; module `auth`. Đặt lại password.

**Xác thực và quyền:** Public: không yêu cầu Authorization. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Content-Type: application/json` nếu có body JSON.

Không có path/query parameter.

Body bắt buộc: `ResetPasswordRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "token": "example-reset-token-value",
  "password": "ExamplePass123!"
}
```

**Response:** `200`, `application/json`, `MessageResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "message": "Password has been reset successfully."
}
```

**Lỗi:** 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 400 BAD_REQUEST: reset token sai/hết hạn/đã dùng; 404 NOT_FOUND: user mất/deleted; 403 FORBIDDEN: user banned. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Kiểm tra reset token chưa dùng/chưa hết hạn, băm password mới, đánh dấu token đã dùng và xóa mọi AuthSession của user trong cùng transaction. POST lặp với token đã dùng bị từ chối.

### `POST /api/v1/auth/verify-email` — Xác minh email — hiện tắt

**Định danh:** operation_id `auth_verify_email`; module `auth`. Xác minh email — hiện tắt.

**Xác thực và quyền:** Public: không yêu cầu Authorization. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Content-Type: application/json` nếu có body JSON.

Không có path/query parameter.

Body bắt buộc: `VerifyEmailRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "token": "example-reset-token-value"
}
```

**Response:** `200`, `application/json`, `MessageResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "message": "Email verification is temporarily disabled."
}
```

**Lỗi:** 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Vẫn validate VerifyEmailRequest rồi trả message Email verification is temporarily disabled. Không đọc token, không cập nhật tài khoản, không gửi email.

## 5. Hợp đồng API user và hồ sơ (Users & Profiles API Contracts)

`GET /api/v1/auth/me` trả định danh auth (`CurrentUserIdentityResponse`); `GET /api/v1/users/me` trả hồ sơ cùng counters (`CurrentUserProfileResponse`). Hai DTO khác nhau có chủ ý. Profile public và summary không để lộ email/provider/status/is_verified/password_hash. Bookmarks chỉ đọc của mình; không có API liệt kê followers/following hoặc đổi username qua PATCH thông thường.

### `GET /api/v1/users/by-username/{username}` — Đọc hồ sơ theo username

**Định danh:** operation_id `users_get_profile`; module `users`. Đọc hồ sơ theo username.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `username` | `string` | Có | — | Username của profile đích; route by-username tránh xung đột với me/ID. |

Ví dụ request: `GET /api/v1/users/by-username/uit_student`; body không gửi.

**Response:** `200`, `application/json`, `PublicUserProfileResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "username": "uit_student",
  "full_name": "Nguyễn Minh An",
  "avatar_url": null,
  "bio": "Sinh viên công nghệ thông tin",
  "major": "Software Engineering",
  "academic_year": "2026",
  "career_goal": "Backend developer",
  "interest_tags": [
    "python"
  ],
  "followers_count": 0,
  "following_count": 0,
  "posts_count": 0,
  "is_following": false,
  "is_current_user": true
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 404 NOT_FOUND: username không tồn tại. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ đọc public profile; không có email/provider/status. posts_count chỉ tính active với người xem thường; chủ hồ sơ/admin tính cả pending/rejected, loại deleted. Không tự thêm filter trạng thái user đích ngoài lookup username hiện hành.

### `GET /api/v1/users/by-username/{username}/comments` — Liệt kê bình luận của user

**Định danh:** operation_id `users_list_comments`; module `users`. Liệt kê bình luận của user.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `username` | `string` | Có | — | Username của profile đích; route by-username tránh xung đột với me/ID. |

Ví dụ request: `GET /api/v1/users/by-username/uit_student/comments`; body không gửi.

**Response:** `200`, `application/json`, `UserCommentResponse[]`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
[]
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 404 NOT_FOUND: username không tồn tại. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Mảng không phân trang; created_at DESC, id DESC. Chỉ comment active và post chưa deleted; người xem thường chỉ thấy post active hoặc post do chính người xem sở hữu, admin thấy các trạng thái còn lại. Không có filter/query.

### `GET /api/v1/users/by-username/{username}/posts` — Liệt kê bài của user

**Định danh:** operation_id `users_list_posts`; module `users`. Liệt kê bài của user.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `username` | `string` | Có | — | Username của profile đích; route by-username tránh xung đột với me/ID. |

Ví dụ request: `GET /api/v1/users/by-username/uit_student/posts`; body không gửi.

**Response:** `200`, `application/json`, `UserPostResponse[]`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
[]
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 404 NOT_FOUND: username không tồn tại. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Mảng không phân trang; created_at DESC, id DESC. Loại deleted; chỉ chủ hồ sơ/admin thấy pending/rejected, người khác chỉ active. title có tiền tố trạng thái cho pending/rejected theo hiện trạng. Không có filter/query.

### `GET /api/v1/users/me` — Đọc hồ sơ đầy đủ của mình

**Định danh:** operation_id `users_get_current`; module `users`. Đọc hồ sơ đầy đủ của mình.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

Không có path/query parameter.

Ví dụ request: `GET /api/v1/users/me`; body không gửi.

**Response:** `200`, `application/json`, `CurrentUserProfileResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "username": "uit_student",
  "full_name": "Nguyễn Minh An",
  "avatar_url": null,
  "bio": "Sinh viên công nghệ thông tin",
  "major": "Software Engineering",
  "academic_year": "2026",
  "career_goal": "Backend developer",
  "interest_tags": [
    "python"
  ],
  "followers_count": 0,
  "following_count": 0,
  "posts_count": 0,
  "is_following": false,
  "is_current_user": true,
  "email": "student@example.com",
  "role": "Student",
  "status": "active",
  "created_at": "2026-11-19T12:00:00Z"
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ đọc hồ sơ cá nhân cùng email, role, status, created_at và số followers/following/posts. is_current_user=true, is_following=false trong tình huống thông thường.

### `PATCH /api/v1/users/me` — Cập nhật một phần hồ sơ của mình

**Định danh:** operation_id `users_update_current`; module `users`. Cập nhật một phần hồ sơ của mình.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. `Content-Type: application/json` nếu có body JSON.

Không có path/query parameter.

Body bắt buộc: `UpdateProfileRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "full_name": "Nguyễn Minh An",
  "bio": null,
  "interest_tags": [
    "python"
  ]
}
```

**Response:** `200`, `application/json`, `CurrentUserProfileResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "username": "uit_student",
  "full_name": "Nguyễn Minh An",
  "avatar_url": null,
  "bio": null,
  "major": "Software Engineering",
  "academic_year": "2026",
  "career_goal": "Backend developer",
  "interest_tags": [
    "python"
  ],
  "followers_count": 0,
  "following_count": 0,
  "posts_count": 0,
  "is_following": false,
  "is_current_user": true,
  "email": "student@example.com",
  "role": "Student",
  "status": "active",
  "created_at": "2026-11-19T12:00:00Z"
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ thay các trường thực sự xuất hiện. Trim chuỗi; chuỗi tùy chọn rỗng được lưu null; interest_tags trim/lowercase/deduplicate và [] xóa sở thích. full_name và interest_tags không nhận null. {} hoặc field lạ bị 422. Một transaction, không notification.

### `GET /api/v1/users/me/bookmarks` — Liệt kê bookmark của mình

**Định danh:** operation_id `users_list_bookmarks`; module `users`. Liệt kê bookmark của mình.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

Không có path/query parameter.

Ví dụ request: `GET /api/v1/users/me/bookmarks`; body không gửi.

**Response:** `200`, `application/json`, `UserPostResponse[]`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
[]
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ bookmark của user hiện tại, không nhận username của người khác. Mảng không phân trang; thời gian bookmark DESC, post.id DESC. Loại post deleted; post không active chỉ hiện cho chủ post hoặc admin.

### `PUT /api/v1/users/me/profile-completion` — Hoàn thành profile

**Định danh:** operation_id `users_complete_profile`; module `auth`. Hoàn thành profile.

**Xác thực và quyền:** Bearer access JWT hợp lệ; user tồn tại, không deleted/banned. Cho phép profile chưa hoàn thành; không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. `Content-Type: application/json` nếu có body JSON.

Không có path/query parameter.

Body bắt buộc: `CompleteProfileRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "username": "uit_student",
  "full_name": "Nguyễn Minh An",
  "avatar_url": null,
  "bio": "Sinh viên công nghệ thông tin",
  "major": "Software Engineering",
  "academic_year": "2026",
  "career_goal": "Backend developer",
  "interest_tags": [
    "python"
  ]
}
```

**Response:** `200`, `application/json`, `CurrentUserIdentityResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "username": "uit_student",
  "email": "student@example.com",
  "full_name": "Nguyễn Minh An",
  "avatar_url": null,
  "bio": "Sinh viên công nghệ thông tin",
  "major": "Software Engineering",
  "academic_year": "2026",
  "career_goal": "Backend developer",
  "interest_tags": [
    "python"
  ],
  "role": "Student",
  "status": "active",
  "provider": "local",
  "is_verified": true,
  "profile_completed": true
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 400 BAD_REQUEST: username bị user khác sử dụng. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Cho phép user đăng nhập chưa hoàn thành profile. Chuẩn hóa username/lowercase, cập nhật full_name; các chuỗi tùy chọn chỉ được gán khi có giá trị truthy và được trim. interest_tags được trim/lowercase/deduplicate; danh sách trống giữ giá trị cũ. Đây là hành vi completion hiện có, không dùng endpoint này để xóa trường; dùng PATCH users/me khi profile đã hoàn thành. Không có notification/session mới.

### `GET /api/v1/users/{user_id}` — Đọc user công khai theo ID

**Định danh:** operation_id `users_get_by_id`; module `auth/users`. Đọc user công khai theo ID.

**Xác thực và quyền:** Bearer access JWT hợp lệ; user tồn tại, không deleted/banned. Cho phép profile chưa hoàn thành; không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `user_id` | `string` | Có | — | ID user đích, không phải username. |

Ví dụ request: `GET /api/v1/users/11111111-1111-4111-8111-111111111111`; body không gửi.

**Response:** `200`, `application/json`, `PublicUserSummary`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "username": "uit_student",
  "full_name": "Nguyễn Minh An",
  "avatar_url": null,
  "bio": "Sinh viên công nghệ thông tin",
  "role": "Student"
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 404 NOT_FOUND: user đích thiếu hoặc không active. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ đọc PublicUserSummary với đúng sáu trường công khai. Người gọi chỉ cần authenticated; user đích phải active.

### `DELETE /api/v1/users/{user_id}/followers/me` — Thiết lập không follow

**Định danh:** operation_id `users_unfollow`; module `users`. Thiết lập không follow.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `user_id` | `string` | Có | — | ID user đích, không phải username. |

Ví dụ request: `DELETE /api/v1/users/11111111-1111-4111-8111-111111111111/followers/me`; body không gửi.

**Response:** `204 No Content`, body rỗng, không gửi JSON `null`/`{}`; `X-Request-ID` có trên response.

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** DELETE membership của chính người gọi; absent membership vẫn 204 (kể cả ID đích không tồn tại). Không body, không notification. Không cần đọc user đích. Idempotent.

### `PUT /api/v1/users/{user_id}/followers/me` — Thiết lập đang follow

**Định danh:** operation_id `users_follow`; module `users`. Thiết lập đang follow.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `user_id` | `string` | Có | — | ID user đích, không phải username. |

Ví dụ request: `PUT /api/v1/users/11111111-1111-4111-8111-111111111111/followers/me`; body không gửi.

**Response:** `200`, `application/json`, `FollowResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "message": "Followed user successfully.",
  "following": true
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 400 BAD_REQUEST: tự follow; 404 NOT_FOUND: user đích không tồn tại. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** PUT thiết lập membership của chính người gọi. Lặp trả 200 following=true; chỉ lần tạo membership mới gửi notification follow. Khóa cặp follower/target trong Unit of Work; xử lý duplicate insert do tranh chấp. User đích được tra theo ID, không áp thêm điều kiện active trong service hiện tại.

## 6. Hợp đồng API bài viết và tương tác (Posts & Interactions API Contracts)

### `POST /api/v1/posts` — Tạo bài viết

**Định danh:** operation_id `posts_create`; module `posts`. Tạo bài viết.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. `Content-Type: application/json` nếu có body JSON.

Không có path/query parameter.

Body bắt buộc: `CreatePostRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "title": "Chia sẻ kinh nghiệm học FastAPI",
  "content": "Nội dung minh họa cho cộng đồng UIT.",
  "cover_image": null,
  "tags": [
    "python"
  ]
}
```

**Response:** `201`, `application/json`, `PostResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "title": "Chia sẻ kinh nghiệm học FastAPI",
  "content": "Nội dung minh họa cho cộng đồng UIT.",
  "cover_image": null,
  "tags": [
    "python"
  ],
  "id": 42,
  "user_id": "11111111-1111-4111-8111-111111111111",
  "status": "pending",
  "original_post_id": null,
  "share_caption": null,
  "requested_new_tags": [],
  "created_at": "2026-11-19T12:00:00Z",
  "author": {
    "id": "11111111-1111-4111-8111-111111111111",
    "username": "uit_student",
    "full_name": "Nguyễn Minh An",
    "avatar_url": null,
    "bio": "Sinh viên công nghệ thông tin",
    "role": "Student"
  },
  "likes_count": 0,
  "comments_count": 0,
  "views_count": 0,
  "shares_count": 0,
  "trending_score": 0,
  "is_liked": false,
  "is_bookmarked": false
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Trim title trước validation minLength=5/maxLength=255; title chỉ có khoảng trắng hoặc quá ngắn sau trim bị 422 trước khi ghi DB. Trim content khi ghi; chuẩn hóa tags. User thường tạo pending, tag chưa biết được giữ ở requested_new_tags để admin duyệt; admin tạo active và có thể tạo tag. Notification cho admin khi pending hoặc followers khi active, cùng transaction với bài. Trả Location: /api/v1/posts/{id}. POST lặp tạo bài mới.

### `DELETE /api/v1/posts/{post_id}` — Xóa mềm bài viết

**Định danh:** operation_id `posts_delete`; module `posts`. Xóa mềm bài viết.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `post_id` | `integer` | Có | — | ID post, phải tồn tại và thỏa quyền hiển thị nếu endpoint yêu cầu. |

Ví dụ request: `DELETE /api/v1/posts/42`; body không gửi.

**Response:** `204 No Content`, body rỗng, không gửi JSON `null`/`{}`; `X-Request-ID` có trên response.

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 400 BAD_REQUEST: user thường xóa bài đã có comment active; 403 FORBIDDEN: không phải tác giả/admin; 404 NOT_FOUND: thiếu/deleted. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Tác giả hoặc admin đặt status=deleted. User thường không xóa bài đã có comment active; admin được phép và thông báo tác giả khi xóa bài người khác. Một transaction. Gọi lại khi đã deleted trả 404; không có body thành công.

### `GET /api/v1/posts/{post_id}` — Đọc chi tiết bài viết

**Định danh:** operation_id `posts_get_by_id`; module `posts`. Đọc chi tiết bài viết.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `post_id` | `integer` | Có | — | ID post, phải tồn tại và thỏa quyền hiển thị nếu endpoint yêu cầu. |

Ví dụ request: `GET /api/v1/posts/42`; body không gửi.

**Response:** `200`, `application/json`, `PostResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "title": "Chia sẻ kinh nghiệm học FastAPI",
  "content": "Nội dung minh họa cho cộng đồng UIT.",
  "cover_image": null,
  "tags": [
    "python"
  ],
  "id": 42,
  "user_id": "11111111-1111-4111-8111-111111111111",
  "status": "active",
  "original_post_id": null,
  "share_caption": null,
  "requested_new_tags": [],
  "created_at": "2026-11-19T12:00:00Z",
  "author": {
    "id": "11111111-1111-4111-8111-111111111111",
    "username": "uit_student",
    "full_name": "Nguyễn Minh An",
    "avatar_url": null,
    "bio": "Sinh viên công nghệ thông tin",
    "role": "Student"
  },
  "likes_count": 0,
  "comments_count": 0,
  "views_count": 0,
  "shares_count": 0,
  "trending_score": 0,
  "is_liked": false,
  "is_bookmarked": false
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 404 NOT_FOUND: bài thiếu/deleted; 403 FORBIDDEN: bài pending/rejected của người khác với user thường. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** GET chỉ đọc, không tăng views_count và không thêm PostView. Quyền hiển thị V ở mục 2 áp dụng.

### `PATCH /api/v1/posts/{post_id}` — Cập nhật một phần bài viết

**Định danh:** operation_id `posts_update`; module `posts`. Cập nhật một phần bài viết.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. `Content-Type: application/json` nếu có body JSON.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `post_id` | `integer` | Có | — | ID post, phải tồn tại và thỏa quyền hiển thị nếu endpoint yêu cầu. |

Body bắt buộc: `UpdatePostRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "title": "Tiêu đề bài viết đã cập nhật",
  "cover_image": null
}
```

**Response:** `200`, `application/json`, `PostResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "title": "Tiêu đề bài viết đã cập nhật",
  "content": "Nội dung minh họa cho cộng đồng UIT.",
  "cover_image": null,
  "tags": [
    "python"
  ],
  "id": 42,
  "user_id": "11111111-1111-4111-8111-111111111111",
  "status": "pending",
  "original_post_id": null,
  "share_caption": null,
  "requested_new_tags": [],
  "created_at": "2026-11-19T12:00:00Z",
  "author": {
    "id": "11111111-1111-4111-8111-111111111111",
    "username": "uit_student",
    "full_name": "Nguyễn Minh An",
    "avatar_url": null,
    "bio": "Sinh viên công nghệ thông tin",
    "role": "Student"
  },
  "likes_count": 0,
  "comments_count": 0,
  "views_count": 0,
  "shares_count": 0,
  "trending_score": 0,
  "is_liked": false,
  "is_bookmarked": false
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 403 FORBIDDEN: không phải tác giả hoặc không có quyền hiển thị; 404 NOT_FOUND: thiếu/deleted. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ tác giả được sửa, kể cả admin cũng không sửa bài người khác qua endpoint này. title được trim trước validation minLength=5/maxLength=255; title rỗng/quá ngắn sau trim bị 422 trước khi ghi DB. Omitted giữ nguyên, cover_image=null xóa ảnh; null của title/content/tags/status và {} bị 422. User thường sửa sẽ đưa bài về pending; status được gửi không trao quyền duyệt. Admin tác giả có thể đặt pending/active/rejected. Đồng bộ tags nếu có, trong cùng transaction. PUT moderation là luồng admin duyệt riêng.

### `DELETE /api/v1/posts/{post_id}/bookmarks/me` — Thiết lập chưa bookmark

**Định danh:** operation_id `posts_unbookmark`; module `posts`. Thiết lập chưa bookmark.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `post_id` | `integer` | Có | — | ID post, phải tồn tại và thỏa quyền hiển thị nếu endpoint yêu cầu. |

Ví dụ request: `DELETE /api/v1/posts/42/bookmarks/me`; body không gửi.

**Response:** `204 No Content`, body rỗng, không gửi JSON `null`/`{}`; `X-Request-ID` có trên response.

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 404 NOT_FOUND: bài thiếu/deleted; 403 FORBIDDEN: không có quyền xem. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Quyền hiển thị V. Xóa bookmark của chính user; absent membership vẫn 204. Khóa post trong Unit of Work; không body/notification, idempotent với bài còn truy cập được.

### `PUT /api/v1/posts/{post_id}/bookmarks/me` — Thiết lập đã bookmark

**Định danh:** operation_id `posts_bookmark`; module `posts`. Thiết lập đã bookmark.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `post_id` | `integer` | Có | — | ID post, phải tồn tại và thỏa quyền hiển thị nếu endpoint yêu cầu. |

Ví dụ request: `PUT /api/v1/posts/42/bookmarks/me`; body không gửi.

**Response:** `200`, `application/json`, `BookmarkResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "bookmarked": true
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 404 NOT_FOUND: bài thiếu/deleted; 403 FORBIDDEN: không có quyền xem. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Quyền hiển thị V. PUT membership riêng tư của chính user; lặp vẫn bookmarked=true, không thêm hàng; không notification. Khóa post trong Unit of Work.

### `DELETE /api/v1/posts/{post_id}/likes/me` — Thiết lập chưa like

**Định danh:** operation_id `posts_unlike`; module `posts`. Thiết lập chưa like.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `post_id` | `integer` | Có | — | ID post, phải tồn tại và thỏa quyền hiển thị nếu endpoint yêu cầu. |

Ví dụ request: `DELETE /api/v1/posts/42/likes/me`; body không gửi.

**Response:** `204 No Content`, body rỗng, không gửi JSON `null`/`{}`; `X-Request-ID` có trên response.

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 404 NOT_FOUND: bài thiếu/deleted; 403 FORBIDDEN: không có quyền xem. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Quyền hiển thị V. Xóa membership của chính user; absent membership vẫn 204, không body/notification. Khóa post trong Unit of Work, idempotent với bài còn truy cập được.

### `PUT /api/v1/posts/{post_id}/likes/me` — Thiết lập đã like

**Định danh:** operation_id `posts_like`; module `posts`. Thiết lập đã like.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `post_id` | `integer` | Có | — | ID post, phải tồn tại và thỏa quyền hiển thị nếu endpoint yêu cầu. |

Ví dụ request: `PUT /api/v1/posts/42/likes/me`; body không gửi.

**Response:** `200`, `application/json`, `LikeResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "liked": true
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 404 NOT_FOUND: bài thiếu/deleted; 403 FORBIDDEN: không có quyền xem. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Quyền hiển thị V. PUT membership của chính user; gọi lại vẫn liked=true, không thêm hàng/notification. Lần tạo mới thông báo tác giả nếu khác người gọi. Khóa post trong Unit of Work.

### `POST /api/v1/posts/{post_id}/reports` — Báo cáo bài viết

**Định danh:** operation_id `posts_create_report`; module `posts/moderation`. Báo cáo bài viết.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. `Content-Type: application/json` nếu có body JSON.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `post_id` | `integer` | Có | — | ID post, phải tồn tại và thỏa quyền hiển thị nếu endpoint yêu cầu. |

Body bắt buộc: `CreateReportRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "reason": "spam",
  "details": "Nội dung có dấu hiệu spam."
}
```

**Response:** `201`, `application/json`, `ReportResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "id": 42,
  "reporter_id": "11111111-1111-4111-8111-111111111111",
  "post_id": 42,
  "comment_id": null,
  "reason": "spam",
  "details": "Nội dung có dấu hiệu spam.",
  "status": "pending",
  "reviewed_by": null,
  "reviewed_at": null,
  "created_at": "2026-11-19T12:00:00Z"
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 409 CONFLICT: đã report bài này; 404 NOT_FOUND: thiếu/deleted; 403 FORBIDDEN: không có quyền xem. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Quyền hiển thị V. Tạo Report pending, trim details, thông báo admin và tác giả nếu khác người gọi. Report và notification cùng Unit of Work. Mỗi user chỉ một report cho cùng post theo kiểm tra hiện tại; không Idempotency-Key.

### `POST /api/v1/posts/{post_id}/shares` — Tạo bài chia sẻ

**Định danh:** operation_id `posts_share`; module `posts`. Tạo bài chia sẻ.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. `Content-Type: application/json` nếu có body JSON.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `post_id` | `integer` | Có | — | ID post, phải tồn tại và thỏa quyền hiển thị nếu endpoint yêu cầu. |

Body không bắt buộc: `SharePostRequest / null`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "caption": "Một bài viết hữu ích."
}
```

**Response:** `201`, `application/json`, `SharePostResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "post_id": 43,
  "original_post_id": 42
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 404 NOT_FOUND: nguồn thiếu/deleted; 403 FORBIDDEN: không có quyền xem. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Quyền hiển thị V. Body có thể bỏ hẳn hoặc null. Tạo PostShare và một bài mới có original_post_id, share_caption, nội dung/ảnh/tag từ nguồn; user thường pending, admin active. Notification cho tác giả nguồn và followers nếu bài mới active. Location trỏ bài chia sẻ mới. Hai POST giống nhau tạo hai bài khác nhau, không idempotent.

### `POST /api/v1/posts/{post_id}/views` — Ghi nhận một lượt xem

**Định danh:** operation_id `posts_record_view`; module `posts`. Ghi nhận một lượt xem.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `post_id` | `integer` | Có | — | ID post, phải tồn tại và thỏa quyền hiển thị nếu endpoint yêu cầu. |

Ví dụ request: `POST /api/v1/posts/42/views`; body không gửi.

**Response:** `204 No Content`, body rỗng, không gửi JSON `null`/`{}`; `X-Request-ID` có trên response.

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 404 NOT_FOUND: bài thiếu/deleted; 403 FORBIDDEN: không có quyền xem. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Sau khi kiểm tra quyền hiển thị V, thêm một PostView trong Unit of Work; 204 không body. Mỗi POST là một sự kiện mới, không deduplicate theo user và không idempotent. Client gọi riêng sau GET khi thực sự muốn ghi nhận lượt xem.

## 7. Hợp đồng API bình luận (Comments API Contracts)

Reply dùng CreateCommentRequest.parent_id trên chính endpoint tạo comment. Chưa triển khai edit/delete comment; không có route giả cho các chức năng này.

### `GET /api/v1/posts/{post_id}/comments` — Đọc cây bình luận

**Định danh:** operation_id `comments_list`; module `comments`. Đọc cây bình luận.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `post_id` | `integer` | Có | — | ID post, phải tồn tại và thỏa quyền hiển thị nếu endpoint yêu cầu. |

Ví dụ request: `GET /api/v1/posts/42/comments`; body không gửi.

**Response:** `200`, `application/json`, `CommentResponse[]`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
[]
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 404 NOT_FOUND: post thiếu/deleted; 403 FORBIDDEN: không có quyền xem post. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Quyền hiển thị V của post. Mảng gốc và replies đệ quy chỉ chứa comment active; mỗi nhóm anh em theo created_at ASC, id ASC. Không phân trang/filter; comment active có parent bị ẩn không tự được nâng thành gốc. GET không ghi dữ liệu.

### `POST /api/v1/posts/{post_id}/comments` — Tạo bình luận hoặc reply

**Định danh:** operation_id `comments_create`; module `comments`. Tạo bình luận hoặc reply.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. `Content-Type: application/json` nếu có body JSON.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `post_id` | `integer` | Có | — | ID post, phải tồn tại và thỏa quyền hiển thị nếu endpoint yêu cầu. |

Body bắt buộc: `CreateCommentRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "content": "Nội dung minh họa cho cộng đồng UIT.",
  "parent_id": null
}
```

**Response:** `201`, `application/json`, `CommentResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "content": "Nội dung minh họa cho cộng đồng UIT.",
  "id": 42,
  "post_id": 42,
  "user_id": "11111111-1111-4111-8111-111111111111",
  "parent_id": null,
  "status": "active",
  "created_at": "2026-11-19T12:00:00Z",
  "author": {
    "id": "11111111-1111-4111-8111-111111111111",
    "username": "uit_student",
    "full_name": "Nguyễn Minh An",
    "avatar_url": null,
    "bio": "Sinh viên công nghệ thông tin",
    "role": "Student"
  },
  "replies": []
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 404 NOT_FOUND: post/parent thiếu hoặc parent không active/khác post; 403 FORBIDDEN: không có quyền xem post. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Quyền hiển thị V. parent_id=null/bỏ qua tạo gốc; parent_id có giá trị phải là comment active thuộc cùng post. Trim content trước validation minLength=1; nội dung chỉ có khoảng trắng bị 422 và không ghi comment/notification. Thông báo tác giả post và tác giả parent nếu khác người gọi; hai thông báo có thể cùng một người. Một Unit of Work. POST lặp tạo comment mới. Chưa có sửa/xóa comment.

### `POST /api/v1/posts/{post_id}/comments/{comment_id}/reports` — Báo cáo bình luận

**Định danh:** operation_id `comments_create_report`; module `comments/moderation`. Báo cáo bình luận.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. `Content-Type: application/json` nếu có body JSON.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `post_id` | `integer` | Có | — | ID post, phải tồn tại và thỏa quyền hiển thị nếu endpoint yêu cầu. |
| path | `comment_id` | `integer` | Có | — | ID comment phải thuộc post_id trên path. |

Body bắt buộc: `CreateReportRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "reason": "spam",
  "details": "Nội dung có dấu hiệu spam."
}
```

**Response:** `201`, `application/json`, `ReportResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "id": 42,
  "reporter_id": "11111111-1111-4111-8111-111111111111",
  "post_id": 42,
  "comment_id": 42,
  "reason": "spam",
  "details": "Nội dung có dấu hiệu spam.",
  "status": "pending",
  "reviewed_by": null,
  "reviewed_at": null,
  "created_at": "2026-11-19T12:00:00Z"
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 409 CONFLICT: user đã report comment; 404 NOT_FOUND: post/comment thiếu, comment ẩn/khác post; 403 FORBIDDEN: không có quyền xem post. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Post phải thỏa quyền hiển thị V, comment phải active và thuộc đúng post. Tạo Report có cả post_id/comment_id; thông báo admin và tác giả comment nếu khác người gọi trong cùng transaction. Không dùng một report của post khác.

## 8. Hợp đồng API feed, tìm kiếm và gợi ý (Feed, Search & Recommendations API Contracts)

Search hiện là query `search` của feed, không có resource `/api/v1/search` độc lập. Tag thường và tag trending nằm cùng phần khám phá. Điểm không phải confidence xác suất, các mô tả range trong tên/description không thêm validation ngoài bảng DTO.

Recommendation trending giữ công thức `likes*4 + comments*3 + shares*2 + views*.5`, nhân `clamp(exp(-age_hours/24), .1, 1)` (tuổi âm dùng decay=1). Feed trending dùng công thức riêng `likes*4 + active_comments*3 + shares*5 + views` nhân `exp(-max(age_hours,0)/72)`; tag trending dùng likes*4 + comments*3 + views, không share/time decay. Không hợp nhất các thuật toán khác nhau dưới cùng một công thức. Các lý do gợi ý là thông điệp có thể thay đổi, không dùng làm code nghiệp vụ.

### `GET /api/v1/feed` — Đọc feed và tìm kiếm

**Định danh:** operation_id `feed_list`; module `feed`. Đọc feed và tìm kiếm.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| query | `page` | `integer` | Không | minimum=1; mặc định=1 | Trang offset bắt đầu từ 1. |
| query | `page_size` | `integer` | Không | minimum=1; maximum=50; mặc định=10 | Số item mỗi trang offset. |
| query | `search` | `string / null` | Không | — | Từ khóa; phạm vi tìm kiếm nêu trong hành vi endpoint. |
| query | `tag` | `string / null` | Không | — | Feed: slugify rồi khớp Tag.slug; recommendations/trending: substring tên tag ILIKE. |
| query | `mode` | `string` | Không | pattern="^(for-you\|following\|trending)$"; mặc định="for-you" | Chế độ feed; xem ưu tiên nhánh trong hành vi. |
| query | `sort` | `string` | Không | pattern="^(latest\|trending\|most-liked\|most-commented)$"; mặc định="latest" | Kiểu xếp thứ tự feed. |

Ví dụ request: `GET /api/v1/feed?page=1&page_size=10&mode=for-you&sort=latest`; body không gửi.

**Response:** `200`, `application/json`, `PostListResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "items": [
    {
      "title": "Chia sẻ kinh nghiệm học FastAPI",
      "content": "Nội dung minh họa cho cộng đồng UIT.",
      "cover_image": null,
      "tags": [
        "python"
      ],
      "id": 42,
      "user_id": "11111111-1111-4111-8111-111111111111",
      "status": "active",
      "original_post_id": null,
      "share_caption": null,
      "requested_new_tags": [],
      "created_at": "2026-11-19T12:00:00Z",
      "author": {
        "id": "11111111-1111-4111-8111-111111111111",
        "username": "uit_student",
        "full_name": "Nguyễn Minh An",
        "avatar_url": null,
        "bio": "Sinh viên công nghệ thông tin",
        "role": "Student"
      },
      "likes_count": 0,
      "comments_count": 0,
      "views_count": 0,
      "shares_count": 0,
      "trending_score": 0,
      "is_liked": false,
      "is_bookmarked": false
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 10,
    "total": 1,
    "total_pages": 1
  }
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ post active. search tìm substring title/content, không tìm username; tag được slugify rồi khớp chính xác Tag.slug. mode=following chỉ người đang follow (không tự thêm bài mình); for-you ưu tiên cá nhân hóa theo hành vi hiện tại. Offset pagination. mode=trending hoặc sort=trending ưu tiên nhánh trending bất kể mode còn lại (kể cả following). latest ở nhánh following theo created_at/id DESC; most-liked/most-commented theo số tương tác DESC rồi created_at/id DESC. Nhánh latest for-you lấy tối đa 200 ứng viên mới để xếp theo tag_overlap*4 + follow_bonus(3) + likes*2 + active_comments*2.5 + shares*1.5 + views*.2, tie-break post.id DESC. Feed trending lấy tối đa 300 ứng viên mới, score=(likes*4+active_comments*3+shares*5+views)*exp(-age_hours/72), score/id DESC. total phản ánh cửa sổ có thể phục vụ ở các nhánh 200/300, không phải toàn bộ kho bài.

### `GET /api/v1/recommendations/collaborative` — Gợi ý cộng tác

**Định danh:** operation_id `recommendations_list_collaborative`; module `feed`. Gợi ý cộng tác.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| query | `page` | `integer` | Không | minimum=1; mặc định=1 | Trang offset bắt đầu từ 1. |
| query | `page_size` | `integer` | Không | minimum=1; maximum=50; mặc định=10 | Số item mỗi trang offset. |
| query | `min_similarity` | `number` | Không | minimum=0.0; maximum=1.0; mặc định=0.2 | Ngưỡng điểm tương đồng tối thiểu. |
| query | `days_back` | `integer` | Không | minimum=1; maximum=365; mặc định=30 | Cửa sổ tuổi post tính bằng ngày. |

Ví dụ request: `GET /api/v1/recommendations/collaborative?page=1&page_size=10&min_similarity=0.2&days_back=30`; body không gửi.

**Response:** `200`, `application/json`, `CollaborativePostListResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "items": [
    {
      "post": {
        "title": "Chia sẻ kinh nghiệm học FastAPI",
        "content": "Nội dung minh họa cho cộng đồng UIT.",
        "cover_image": null,
        "tags": [
          "python"
        ],
        "id": 42,
        "user_id": "11111111-1111-4111-8111-111111111111",
        "status": "active",
        "original_post_id": null,
        "share_caption": null,
        "requested_new_tags": [],
        "created_at": "2026-11-19T12:00:00Z",
        "author": {
          "id": "11111111-1111-4111-8111-111111111111",
          "username": "uit_student",
          "full_name": "Nguyễn Minh An",
          "avatar_url": null,
          "bio": "Sinh viên công nghệ thông tin",
          "role": "Student"
        },
        "likes_count": 0,
        "comments_count": 0,
        "views_count": 0,
        "shares_count": 0,
        "trending_score": 0,
        "is_liked": false,
        "is_bookmarked": false
      },
      "cf_score": 0.6,
      "cf_reason": "Được người có sở thích tương tự quan tâm",
      "similar_user_count": 0
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 10,
    "total": 1,
    "total_pages": 1
  }
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ post active trong days_back, loại bài mình đã like. Chọn tối đa 500 user ứng viên theo user.id ASC, lấy tối đa 20 người tương tự đạt min_similarity (tie-break user.id DESC). Giữ weights interest tags 25%, liked posts 35%, following 25%, commented posts 15%. Tập bài lấy post có ít nhất một like, không chỉ like của nhóm tương tự; score = tổng like của bài * (số user tương tự đã like / số user tương tự được chọn) * (0.7 nếu người gọi đã xem, ngược lại 1). Bài có score=0 vẫn có thể nằm trong tập kết quả. Xếp score/id DESC rồi offset. total là số candidate đã chấm; similar_user_count response hiện luôn 0 (chưa cung cấp thống kê thật). Không ghi dữ liệu.

### `GET /api/v1/recommendations/posts/{post_id}/similar` — Gợi ý bài tương tự

**Định danh:** operation_id `recommendations_list_similar`; module `feed`. Gợi ý bài tương tự.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `post_id` | `integer` | Có | — | ID post, phải tồn tại và thỏa quyền hiển thị nếu endpoint yêu cầu. |
| query | `limit` | `integer` | Không | minimum=1; maximum=20; mặc định=5 | Số kết quả tối đa, không phải page_size/cursor. |
| query | `min_similarity` | `number` | Không | minimum=0.0; maximum=1.0; mặc định=0.1 | Ngưỡng điểm tương đồng tối thiểu. |

Ví dụ request: `GET /api/v1/recommendations/posts/42/similar?limit=5&min_similarity=0.1`; body không gửi.

**Response:** `200`, `application/json`, `SimilarPostListResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "items": [
    {
      "post": {
        "title": "Chia sẻ kinh nghiệm học FastAPI",
        "content": "Nội dung minh họa cho cộng đồng UIT.",
        "cover_image": null,
        "tags": [
          "python"
        ],
        "id": 42,
        "user_id": "11111111-1111-4111-8111-111111111111",
        "status": "active",
        "original_post_id": null,
        "share_caption": null,
        "requested_new_tags": [],
        "created_at": "2026-11-19T12:00:00Z",
        "author": {
          "id": "11111111-1111-4111-8111-111111111111",
          "username": "uit_student",
          "full_name": "Nguyễn Minh An",
          "avatar_url": null,
          "bio": "Sinh viên công nghệ thông tin",
          "role": "Student"
        },
        "likes_count": 0,
        "comments_count": 0,
        "views_count": 0,
        "shares_count": 0,
        "trending_score": 0,
        "is_liked": false,
        "is_bookmarked": false
      },
      "similarity_score": 0.8,
      "similarity_reason": "Nội dung và tag tương đồng"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 1,
    "total": 1,
    "total_pages": 1
  }
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ dùng nguồn active; nếu nguồn không tồn tại hoặc không active (kể cả pending của chính tác giả/admin), trả 200 items=[] thay vì 404/403. Không lộ dữ liệu nguồn ẩn. Content-based TF/cosine cho title/content và Jaccard cho tags, giữ trọng số title 20%, content 40%, tag 40%. Loại nguồn; chỉ candidate active; lọc min_similarity và xếp similarity DESC, post.id DESC, tối đa limit. meta.page=1, page_size=total=len(items), total_pages=1 nếu có kết quả, ngược lại 0. Không phải tổng trước limit; không ghi view.

### `GET /api/v1/recommendations/profile` — Gợi ý theo hồ sơ

**Định danh:** operation_id `recommendations_list_profile`; module `feed`. Gợi ý theo hồ sơ.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| query | `page` | `integer` | Không | minimum=1; mặc định=1 | Trang offset bắt đầu từ 1. |
| query | `page_size` | `integer` | Không | minimum=1; maximum=50; mặc định=10 | Số item mỗi trang offset. |
| query | `min_score` | `number` | Không | minimum=0.0; maximum=1.0; mặc định=0.1 | Ngưỡng điểm profile tối thiểu. |
| query | `days_back` | `integer` | Không | minimum=1; maximum=365; mặc định=30 | Cửa sổ tuổi post tính bằng ngày. |

Ví dụ request: `GET /api/v1/recommendations/profile?page=1&page_size=10&min_score=0.1&days_back=30`; body không gửi.

**Response:** `200`, `application/json`, `ProfileBasedPostListResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "items": [
    {
      "post": {
        "title": "Chia sẻ kinh nghiệm học FastAPI",
        "content": "Nội dung minh họa cho cộng đồng UIT.",
        "cover_image": null,
        "tags": [
          "python"
        ],
        "id": 42,
        "user_id": "11111111-1111-4111-8111-111111111111",
        "status": "active",
        "original_post_id": null,
        "share_caption": null,
        "requested_new_tags": [],
        "created_at": "2026-11-19T12:00:00Z",
        "author": {
          "id": "11111111-1111-4111-8111-111111111111",
          "username": "uit_student",
          "full_name": "Nguyễn Minh An",
          "avatar_url": null,
          "bio": "Sinh viên công nghệ thông tin",
          "role": "Student"
        },
        "likes_count": 0,
        "comments_count": 0,
        "views_count": 0,
        "shares_count": 0,
        "trending_score": 0,
        "is_liked": false,
        "is_bookmarked": false
      },
      "profile_score": 0.8,
      "recommendation_reason": "Phù hợp sở thích Python"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 10,
    "total": 1,
    "total_pages": 1
  }
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ post active trong days_back, loại bài đã like; chấm theo profile: direct interest tags 40%, keywords major/career_goal/bio 30%, behavior tags 30%. Lọc min_score, score/post.id DESC trước offset. Không có candidate cap 200/300 của feed; total là số bài đạt lọc. Không ghi dữ liệu.

### `GET /api/v1/recommendations/profile-analysis` — Phân tích hồ sơ cho gợi ý

**Định danh:** operation_id `recommendations_get_profile_analysis`; module `feed`. Phân tích hồ sơ cho gợi ý.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

Không có path/query parameter.

Ví dụ request: `GET /api/v1/recommendations/profile-analysis`; body không gửi.

**Response:** `200`, `application/json`, `ProfileAnalysisResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "user_id": "11111111-1111-4111-8111-111111111111",
  "profile_summary": {
    "interest_tags": [
      "python"
    ],
    "major": "Software Engineering",
    "academic_year": "2026",
    "career_goal": "Backend developer",
    "profile_strength": 1.0,
    "recommendations_count": 1,
    "profile_completeness": {
      "has_interest_tags": true,
      "has_major": true,
      "has_academic_year": true,
      "has_career_goal": true,
      "has_bio": true
    }
  },
  "recommendation_message": "Profile đầy đủ để nhận gợi ý."
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ user hiện tại; cùng profile_summary như endpoint summary và recommendation_message dựa trên thiếu interest_tags/major/career_goal. Nội dung thông điệp là mô tả, không phải mã trạng thái ổn định. Không ghi dữ liệu.

### `GET /api/v1/recommendations/profile-summary` — Tóm tắt hồ sơ cho gợi ý

**Định danh:** operation_id `recommendations_get_profile_summary`; module `feed`. Tóm tắt hồ sơ cho gợi ý.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

Không có path/query parameter.

Ví dụ request: `GET /api/v1/recommendations/profile-summary`; body không gửi.

**Response:** `200`, `application/json`, `UserProfileSummary`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "interest_tags": [
    "python"
  ],
  "major": "Software Engineering",
  "academic_year": "2026",
  "career_goal": "Backend developer",
  "profile_strength": 1.0,
  "recommendations_count": 1,
  "profile_completeness": {
    "has_interest_tags": true,
    "has_major": true,
    "has_academic_year": true,
    "has_career_goal": true,
    "has_bio": true
  }
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ user hiện tại. profile_strength là số trường có giá trị trong interest_tags/major/academic_year/career_goal/bio chia 5. recommendations_count đếm post active chưa like, chưa áp min_score/days_back. profile_completeness có năm cờ has_interest_tags, has_major, has_academic_year, has_career_goal, has_bio. Không ghi dữ liệu.

### `GET /api/v1/recommendations/trending` — Gợi ý bài xu hướng

**Định danh:** operation_id `recommendations_list_trending`; module `feed`. Gợi ý bài xu hướng.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| query | `page` | `integer` | Không | minimum=1; mặc định=1 | Trang offset bắt đầu từ 1. |
| query | `page_size` | `integer` | Không | minimum=1; maximum=50; mặc định=10 | Số item mỗi trang offset. |
| query | `hours` | `integer` | Không | minimum=1; maximum=168; mặc định=24 | Cửa sổ thời gian tính bằng GIỜ, không phải ngày. |
| query | `tag` | `string / null` | Không | — | Feed: slugify rồi khớp Tag.slug; recommendations/trending: substring tên tag ILIKE. |

Ví dụ request: `GET /api/v1/recommendations/trending?page=1&page_size=10&hours=24`; body không gửi.

**Response:** `200`, `application/json`, `TrendingPostListResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "items": [
    {
      "post": {
        "title": "Chia sẻ kinh nghiệm học FastAPI",
        "content": "Nội dung minh họa cho cộng đồng UIT.",
        "cover_image": null,
        "tags": [
          "python"
        ],
        "id": 42,
        "user_id": "11111111-1111-4111-8111-111111111111",
        "status": "active",
        "original_post_id": null,
        "share_caption": null,
        "requested_new_tags": [],
        "created_at": "2026-11-19T12:00:00Z",
        "author": {
          "id": "11111111-1111-4111-8111-111111111111",
          "username": "uit_student",
          "full_name": "Nguyễn Minh An",
          "avatar_url": null,
          "bio": "Sinh viên công nghệ thông tin",
          "role": "Student"
        },
        "likes_count": 0,
        "comments_count": 0,
        "views_count": 0,
        "shares_count": 0,
        "trending_score": 0,
        "is_liked": false,
        "is_bookmarked": false
      },
      "trend_rank": 1,
      "hot_score": 8.0,
      "trending_reason": "Có nhiều tương tác"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 10,
    "total": 1,
    "total_pages": 1
  }
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ post active trong hours, tag lọc substring tên tag (ILIKE). Tính điểm trên TOÀN BỘ tập đủ điều kiện rồi xếp score DESC, post.id DESC trước khi offset; total là số bài đủ điều kiện. Trọng số giữ nguyên like=4, comment=3, share=2, view=.5 và exponential time decay có sàn .1 (mục 8). trend_rank là vị trí toàn cục (page−1)*page_size+index. Không ghi view; empty/out-of-range trả items=[].

### `GET /api/v1/tags` — Danh mục tag cho người dùng

**Định danh:** operation_id `tags_list`; module `posts`. Danh mục tag cho người dùng.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

Không có path/query parameter.

Ví dụ request: `GET /api/v1/tags`; body không gửi.

**Response:** `200`, `application/json`, `TagResponse[]`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
[]
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Mảng TagResponse không phân trang, theo name ASC; không filter/query, không tự tạo tag.

### `GET /api/v1/tags/trending` — Gợi ý tag xu hướng

**Định danh:** operation_id `recommendations_list_trending_tags`; module `feed`. Gợi ý tag xu hướng.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| query | `limit` | `integer` | Không | minimum=1; maximum=50; mặc định=10 | Số kết quả tối đa, không phải page_size/cursor. |
| query | `hours` | `integer` | Không | minimum=1; maximum=168; mặc định=24 | Cửa sổ thời gian tính bằng GIỜ, không phải ngày. |

Ví dụ request: `GET /api/v1/tags/trending?limit=10&hours=24`; body không gửi.

**Response:** `200`, `application/json`, `TrendingTagListResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "items": [
    {
      "tag_name": "python",
      "post_count": 1,
      "trend_score": 8.0
    }
  ],
  "updated_at": "2026-11-19T12:00:00Z"
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ post active trong hours. Mỗi post đóng góp like*4 + comment*3 + view vào mỗi tag (không tính share); tổng score DESC, tag.id DESC; giới hạn limit. Trả items và updated_at, không meta/page. Rỗng trả items=[].

## 9. Hợp đồng API thông báo (Notifications API Contracts)

Recipient ownership được kiểm tra ở server. Notification của người khác được xem như không tồn tại (404). REST dưới đây không định nghĩa giao thức WebSocket; không có mark-all-read/unread hay phân trang giả.

### `GET /api/v1/notifications` — Đọc thông báo của mình

**Định danh:** operation_id `notifications_list`; module `notifications`. Đọc thông báo của mình.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| query | `unread_only` | `boolean` | Không | mặc định=false | true để chỉ lấy notification chưa đọc. |

Ví dụ request: `GET /api/v1/notifications?unread_only=false`; body không gửi.

**Response:** `200`, `application/json`, `NotificationResponse[]`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
[]
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ recipient user hiện tại. unread_only=true chỉ chưa đọc, false trả tất cả; created_at DESC, id DESC. Mảng không phân trang, không tự đánh dấu đã đọc. Đây là REST, không định nghĩa WebSocket event.

### `DELETE /api/v1/notifications/{notification_id}` — Xóa thông báo đã đọc

**Định danh:** operation_id `notifications_delete`; module `notifications`. Xóa thông báo đã đọc.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `notification_id` | `integer` | Có | — | ID notification thuộc recipient hiện tại. |

Ví dụ request: `DELETE /api/v1/notifications/42`; body không gửi.

**Response:** `204 No Content`, body rỗng, không gửi JSON `null`/`{}`; `X-Request-ID` có trên response.

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 400 BAD_REQUEST: thông báo chưa đọc; 404 NOT_FOUND: thiếu hoặc thuộc người khác. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ recipient và notification đã đọc. Xóa hàng trong Unit of Work; 204 không body. Gọi lại sau khi xóa trả 404.

### `PUT /api/v1/notifications/{notification_id}/read` — Đánh dấu thông báo đã đọc

**Định danh:** operation_id `notifications_mark_read`; module `notifications`. Đánh dấu thông báo đã đọc.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `notification_id` | `integer` | Có | — | ID notification thuộc recipient hiện tại. |

Ví dụ request: `PUT /api/v1/notifications/42/read`; body không gửi.

**Response:** `200`, `application/json`, `NotificationResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "id": 42,
  "user_id": "11111111-1111-4111-8111-111111111111",
  "actor_id": "22222222-2222-4222-8222-222222222222",
  "type": "post_like",
  "title": "Your post was liked",
  "message": "uit_student liked your post.",
  "is_read": true,
  "post_id": 42,
  "comment_id": null,
  "report_id": null,
  "created_at": "2026-11-19T12:00:00Z"
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 404 NOT_FOUND: notification thiếu hoặc thuộc recipient khác. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ recipient. Đặt is_read=true trong Unit of Work; PUT lặp giữ true, không thêm notification. Không có unread API.

## 10. Hợp đồng API quản trị và kiểm duyệt (Admin & Moderation API Contracts)

Toàn bộ operation ở đây yêu cầu role admin và active/completed profile. Ban/unban và moderation dùng application/domain policy, audit/notification trong cùng Unit of Work khi có thay đổi. Tags không tự phát sinh audit log nếu service chưa triển khai.

### `GET /api/v1/admin/analytics/overview` — Đọc thống kê quản trị

**Định danh:** operation_id `admin_get_analytics`; module `moderation`. Đọc thống kê quản trị.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành và role=admin (không phân biệt hoa thường). Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

Không có path/query parameter.

Ví dụ request: `GET /api/v1/admin/analytics/overview`; body không gửi.

**Response:** `200`, `application/json`, `AdminAnalyticsResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "users_today": 0,
  "users_week": 0,
  "posts_today": 0,
  "posts_week": 0,
  "comments_today": 0,
  "comments_week": 0,
  "reports_today": 0,
  "reports_week": 0,
  "pending_reports": 0,
  "pending_posts": 0
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile/không phải admin. 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Các số *_today là cửa sổ 24 giờ trượt, *_week là 7 ngày trượt tính theo UTC hiện tại (không phải ngày/tuần lịch). Users/comments/reports đếm theo created_at; posts chỉ active. pending_reports/pending_posts là tổng hiện tại. Chỉ đọc.

### `GET /api/v1/admin/posts/pending` — Liệt kê bài chờ duyệt

**Định danh:** operation_id `admin_list_pending_posts`; module `moderation`. Liệt kê bài chờ duyệt.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành và role=admin (không phân biệt hoa thường). Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| query | `page` | `integer` | Không | minimum=1; mặc định=1 | Trang offset bắt đầu từ 1. |
| query | `page_size` | `integer` | Không | minimum=1; maximum=100; mặc định=20 | Số item mỗi trang offset. |

Ví dụ request: `GET /api/v1/admin/posts/pending?page=1&page_size=20`; body không gửi.

**Response:** `200`, `application/json`, `AdminPostsListResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "items": [
    {
      "id": 42,
      "user_id": "11111111-1111-4111-8111-111111111111",
      "title": "Chia sẻ kinh nghiệm học FastAPI",
      "status": "pending",
      "requested_new_tags": [],
      "created_at": "2026-11-19T12:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 10,
    "total": 1,
    "total_pages": 1
  }
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile/không phải admin. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Chỉ status=pending; offset page/page_size; created_at DESC, id DESC. requested_new_tags là tag người viết đề nghị. Không ghi dữ liệu.

### `PUT /api/v1/admin/posts/{post_id}/moderation` — Duyệt hoặc từ chối bài

**Định danh:** operation_id `admin_moderate_post`; module `moderation`. Duyệt hoặc từ chối bài.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành và role=admin (không phân biệt hoa thường). Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. `Content-Type: application/json` nếu có body JSON.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `post_id` | `integer` | Có | — | ID post, phải tồn tại và thỏa quyền hiển thị nếu endpoint yêu cầu. |

Body bắt buộc: `ModeratePostRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "status": "active"
}
```

**Response:** `200`, `application/json`, `AdminPostModerationResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "id": 42,
  "user_id": "11111111-1111-4111-8111-111111111111",
  "title": "Chia sẻ kinh nghiệm học FastAPI",
  "status": "active",
  "requested_new_tags": [],
  "created_at": "2026-11-19T12:00:00Z"
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile/không phải admin. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 404 NOT_FOUND: thiếu/deleted; 409 POST_ALREADY_MODERATED: đã có quyết định khác. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Khóa post (và tags khi approve). Chỉ pending chuyển active/rejected; cùng trạng thái đích trả 200 không side effect; trạng thái terminal khác trả 409. active: tạo/liên kết requested_new_tags, xóa hàng đợi tag, audit approve, thông báo tác giả và followers; rejected: xóa requested_new_tags, audit reject, thông báo tác giả. Mọi thay đổi cùng Unit of Work.

### `GET /api/v1/admin/reports` — Quản trị danh sách report

**Định danh:** operation_id `admin_list_reports`; module `moderation`. Quản trị danh sách report.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành và role=admin (không phân biệt hoa thường). Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| query | `page` | `integer` | Không | minimum=1; mặc định=1 | Trang offset bắt đầu từ 1. |
| query | `page_size` | `integer` | Không | minimum=1; maximum=100; mặc định=20 | Số item mỗi trang offset. |
| query | `status_filter` | `string / null` | Không | pattern="^(pending\\|reviewed\\|dismissed\\|resolved)$" | Trạng thái cần lọc theo tập giá trị cho phép. |
| query | `reason` | `string / null` | Không | — | Lý do unban hoặc filter reason report chính xác tùy endpoint. |

Ví dụ request: `GET /api/v1/admin/reports?page=1&page_size=20`; body không gửi.

**Response:** `200`, `application/json`, `AdminReportsListResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "items": [
    {
      "id": 42,
      "reporter_id": "11111111-1111-4111-8111-111111111111",
      "post_id": 42,
      "comment_id": null,
      "reason": "spam",
      "details": "Nội dung có dấu hiệu spam.",
      "status": "pending",
      "reviewed_by": null,
      "reviewed_at": null,
      "created_at": "2026-11-19T12:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 10,
    "total": 1,
    "total_pages": 1
  }
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile/không phải admin. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Offset page/page_size; status_filter bằng status, reason so khớp chính xác. created_at DESC, id DESC. Không query sort tùy ý. Không ghi dữ liệu.

### `PUT /api/v1/admin/reports/{report_id}/moderation` — Thiết lập quyết định report

**Định danh:** operation_id `admin_moderate_report`; module `moderation`. Thiết lập quyết định report.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành và role=admin (không phân biệt hoa thường). Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. `Content-Type: application/json` nếu có body JSON.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `report_id` | `integer` | Có | — | ID report cần quản trị. |

Body bắt buộc: `ModerateReportRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "status": "resolved",
  "action": "hide_post",
  "notes": "Đã xác nhận nội dung vi phạm."
}
```

**Response:** `200`, `application/json`, `ReportResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "id": 42,
  "reporter_id": "11111111-1111-4111-8111-111111111111",
  "post_id": 42,
  "comment_id": null,
  "reason": "spam",
  "details": "Nội dung có dấu hiệu spam.",
  "status": "resolved",
  "reviewed_by": "22222222-2222-4222-8222-222222222222",
  "reviewed_at": "2026-11-19T12:00:00Z",
  "created_at": "2026-11-19T12:00:00Z"
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile/không phải admin. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 400 BAD_REQUEST: cặp status/action sai, action không đúng target, ban bản thân/admin; 404 NOT_FOUND: report/target/user thiếu; 409 REPORT_ALREADY_MODERATED: quyết định terminal khác. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Khóa report và post liên quan; action chỉ khác none khi status=resolved, resolved bắt buộc action cụ thể. Action phải đúng loại target. Có thể ẩn post (rejected), ẩn comment (hidden), ban tác giả; ghi audit và notification tác giả/reporter trong cùng transaction. Report đã rời pending: cùng status và action trả 200 không lặp side effect (notes khác không cập nhật); quyết định khác trả 409. pending→pending vẫn có thể ghi audit/notification; không quảng bá idempotency cho nhánh này.

### `GET /api/v1/admin/tags` — Quản trị danh mục tag

**Định danh:** operation_id `admin_list_tags`; module `moderation`. Quản trị danh mục tag.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành và role=admin (không phân biệt hoa thường). Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

Không có path/query parameter.

Ví dụ request: `GET /api/v1/admin/tags`; body không gửi.

**Response:** `200`, `application/json`, `TagResponse[]`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
[]
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile/không phải admin. 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Mảng không phân trang, name ASC. Không filter/query. Chỉ đọc.

### `POST /api/v1/admin/tags` — Tạo tag

**Định danh:** operation_id `admin_create_tag`; module `moderation`. Tạo tag.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành và role=admin (không phân biệt hoa thường). Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. `Content-Type: application/json` nếu có body JSON.

Không có path/query parameter.

Body bắt buộc: `CreateTagRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "name": "python"
}
```

**Response:** `201`, `application/json`, `TagResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "id": 42,
  "name": "python",
  "slug": "python",
  "created_at": "2026-11-19T12:00:00Z"
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile/không phải admin. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 400 BAD_REQUEST: tag có tên/slug đã tồn tại. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Trim/lowercase name, sinh slug từ tên; khóa tags trong Unit of Work. Tên/slug đã có bị 400 theo chính sách hiện tại. POST lặp không idempotent. Không audit/notification riêng trong service tag.

### `DELETE /api/v1/admin/tags/{tag_id}` — Xóa tag

**Định danh:** operation_id `admin_delete_tag`; module `moderation`. Xóa tag.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành và role=admin (không phân biệt hoa thường). Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `tag_id` | `integer` | Có | — | ID tag cần quản trị. |

Ví dụ request: `DELETE /api/v1/admin/tags/42`; body không gửi.

**Response:** `204 No Content`, body rỗng, không gửi JSON `null`/`{}`; `X-Request-ID` có trên response.

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile/không phải admin. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 404 NOT_FOUND: tag thiếu. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Khóa tags; xóa tag và liên kết PostTag theo cascade trong cùng Unit of Work, 204 không body. Gọi lại trả 404. Không thêm audit/notification riêng.

### `PATCH /api/v1/admin/tags/{tag_id}` — Đổi tên tag

**Định danh:** operation_id `admin_update_tag`; module `moderation`. Đổi tên tag.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành và role=admin (không phân biệt hoa thường). Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. `Content-Type: application/json` nếu có body JSON.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `tag_id` | `integer` | Có | — | ID tag cần quản trị. |

Body bắt buộc: `UpdateTagRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "name": "python"
}
```

**Response:** `200`, `application/json`, `TagResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "id": 42,
  "name": "python",
  "slug": "python",
  "created_at": "2026-11-19T12:00:00Z"
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile/không phải admin. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 404 NOT_FOUND: tag thiếu; 409 CONFLICT: tên/slug trùng tag khác. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** PATCH name bắt buộc vì đây là trường sửa duy nhất; trim/lowercase và sinh lại slug. Khóa tags trong Unit of Work. Không thêm audit/notification riêng.

### `GET /api/v1/admin/users` — Quản trị danh sách user

**Định danh:** operation_id `admin_list_users`; module `moderation`. Quản trị danh sách user.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành và role=admin (không phân biệt hoa thường). Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| query | `page` | `integer` | Không | minimum=1; mặc định=1 | Trang offset bắt đầu từ 1. |
| query | `page_size` | `integer` | Không | minimum=1; maximum=100; mặc định=20 | Số item mỗi trang offset. |
| query | `search` | `string / null` | Không | — | Từ khóa; phạm vi tìm kiếm nêu trong hành vi endpoint. |
| query | `status_filter` | `string / null` | Không | pattern="^(active\\|banned\\|deleted)$" | Trạng thái cần lọc theo tập giá trị cho phép. |
| query | `sort_by` | `string` | Không | pattern="^(created_at\|username\|email)$"; mặc định="created_at" | Cột sort quản trị user. |
| query | `sort_order` | `string` | Không | pattern="^(asc\|desc)$"; mặc định="desc" | Chiều sort quản trị user; tie-break user.id ASC. |

Ví dụ request: `GET /api/v1/admin/users?page=1&page_size=20&sort_by=created_at&sort_order=desc`; body không gửi.

**Response:** `200`, `application/json`, `AdminUsersListResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "items": [
    {
      "id": "11111111-1111-4111-8111-111111111111",
      "username": "uit_student",
      "email": "student@example.com",
      "full_name": "Nguyễn Minh An",
      "role": "Student",
      "status": "active",
      "created_at": "2026-11-19T12:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 10,
    "total": 1,
    "total_pages": 1
  }
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile/không phải admin. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Offset page/page_size. search substring username/email/full_name, status_filter lọc lowercase status. sort_by là cột được chọn, sort_order ASC/DESC, cùng giá trị phá hòa user.id ASC. Trả AdminUserResponse có email, không password_hash. Không ghi dữ liệu.

### `DELETE /api/v1/admin/users/{user_id}/ban` — Thiết lập user active

**Định danh:** operation_id `admin_unban_user`; module `moderation`. Thiết lập user active.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành và role=admin (không phân biệt hoa thường). Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. Không có request body.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `user_id` | `string` | Có | — | ID user đích, không phải username. |
| query | `reason` | `string / null` | Không | — | Lý do unban hoặc filter reason report chính xác tùy endpoint. |

Ví dụ request: `DELETE /api/v1/admin/users/11111111-1111-4111-8111-111111111111/ban`; body không gửi.

**Response:** `200`, `application/json`, `AdminUserResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "username": "uit_student",
  "email": "student@example.com",
  "full_name": "Nguyễn Minh An",
  "role": "Student",
  "status": "active",
  "created_at": "2026-11-19T12:00:00Z"
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile/không phải admin. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 404 NOT_FOUND: user thiếu/deleted. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Khóa user; deleted như không tồn tại. Lần đổi sang active ghi audit với query reason và notification account_status cùng transaction; đã active trả 200 không side effect mới. Có JSON response dù method DELETE.

### `PUT /api/v1/admin/users/{user_id}/ban` — Thiết lập user bị ban

**Định danh:** operation_id `admin_ban_user`; module `moderation`. Thiết lập user bị ban.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành và role=admin (không phân biệt hoa thường). Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. `Content-Type: application/json` nếu có body JSON.

| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| path | `user_id` | `string` | Có | — | ID user đích, không phải username. |

Body bắt buộc: `BanUserRequest`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ JSON request:

```json
{
  "reason": "spam"
}
```

**Response:** `200`, `application/json`, `AdminUserResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "username": "uit_student",
  "email": "student@example.com",
  "full_name": "Nguyễn Minh An",
  "role": "Student",
  "status": "banned",
  "created_at": "2026-11-19T12:00:00Z"
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile/không phải admin. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác. 400 BAD_REQUEST: tự ban hoặc ban admin; 404 NOT_FOUND: thiếu/deleted. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Khóa user trong Unit of Work. Không ban chính mình/admin; deleted như không tồn tại. Lần đổi sang banned ghi audit log và notification account_status cùng transaction. Đã banned trả 200 không ghi audit/notification mới; không tự xóa session.

## 11. Hợp đồng API media (Media API Contracts)

**Đã triển khai:** chỉ upload filesystem bên dưới. Static `/uploads/{filename}` hiện công khai; bearer bảo vệ bước upload, không bảo vệ URL ảnh đã trả. Không có media ownership, reservation, attach-confirm, lifecycle cleanup hoặc kiểm tra quyền truy cập từng file. File không được đính kèm post tự động; client truyền URL vào cover_image/avatar_url theo DTO. Không có bảo đảm persistence trên hosting có filesystem tạm; cần cấu hình UPLOAD_DIR/persistent storage theo triển khai thực tế.

**Planned — Not Implemented:** Cloudflare R2 là storage được chọn cho tương lai. Các khả năng create upload intent → direct upload qua presigned URL → confirm/verify → attach to post → visibility/lifecycle chưa có router, DTO hay endpoint hoạt động. Không cấp path/method giả và không đưa vào bảng endpoint triển khai. Không gọi upload v1 là R2/presigned upload.

### `POST /api/v1/media/images` — Upload ảnh lên filesystem

**Định danh:** operation_id `media_upload_image`; module `media`. Upload ảnh lên filesystem.

**Xác thực và quyền:** Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.

**Request:** `Accept: application/json` khi nhận JSON. `Authorization: Bearer <access_token>` bắt buộc. `Content-Type: multipart/form-data; boundary=...`.

Không có path/query parameter.

Body bắt buộc: `Body_media_upload_image`; toàn bộ field/type/nullability/validation ở mục 12.

Ví dụ request (binary, không phải JSON):

```http
POST /api/v1/media/images HTTP/1.1
Authorization: Bearer <access_token>
Content-Type: multipart/form-data; boundary=UITBoundary

--UITBoundary
Content-Disposition: form-data; name="file"; filename="example.png"
Content-Type: image/png

<binary PNG bytes>
--UITBoundary--
```

**Response:** `201`, `application/json`, `UploadImageResponse`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.

```json
{
  "url": "http://localhost:8000/uploads/33333333-3333-4333-8333-333333333333.png"
}
```

**Lỗi:** 401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned/inactive/chưa hoàn thành profile. 422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến. 400 BAD_REQUEST: MIME không hỗ trợ hoặc signature sai; 413 PAYLOAD_TOO_LARGE: file >5 MiB hoặc request >6 MiB; 500 INTERNAL_ERROR: không lưu được ảnh. Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.

**Hành vi, side effect và retry:** Transitional v1: nhận multipart field file bắt buộc. Content-Type của file phải image/jpeg hoặc image/png và magic bytes phải khớp (JPEG FF D8 FF; PNG 89 50 4E 47 0D 0A 1A 0A). File tối đa 5 MiB (5,242,880 byte); toàn request tối đa 6 MiB (6,291,456 byte) kể cả multipart, có chặn cả body streaming. Lưu UUID.jpg/png dưới UPLOAD_DIR, trả URL PUBLIC_API_URL hoặc request base URL + /uploads/{filename}. Xóa file ghi dở nếu upload lỗi. POST lặp tạo file mới. Không transaction DB, không ownership reservation/attach/confirm/visibility lifecycle.

## 12. DTO dùng chung và kiểu dữ liệu (Shared DTOs and Data Types)

Bảng sau được sinh từ components.schemas của OpenAPI. **Bắt buộc** nghĩa là key nằm trong required của JSON Schema, độc lập với **Nullable**. Trường response có default vẫn thường xuất hiện vì router không exclude_defaults; các ví dụ thể hiện đủ representation. `—` là không có ràng buộc bổ sung công bố ở schema, không tự suy ra max length từ cột DB. Trường response status/role là string trừ khi có enum/pattern rõ ràng.

Quy ước status: user active/banned/deleted; post pending/active/rejected/deleted (post response nullable theo DTO lịch sử); comment active/hidden; report pending/reviewed/dismissed/resolved. Các trường đếm/scores là kiểu hiện có trong schema, không tự thêm minimum/maximum nếu DTO chưa khai báo. Các field refs liên kết tới định nghĩa DTO ngay trong phần này.

`UtcDateTime` là kiểu Python dùng chung, xuất thành `string (date-time)` trong OpenAPI; nullable datetime vẫn null khi chưa có sự kiện. `PublicUserSummary` chỉ có id, username, full_name, avatar_url, bio, role.

### `AdminAnalyticsResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `users_today` | `integer` | Có | Không | — | Số user tạo trong 24 giờ gần nhất. |
| `users_week` | `integer` | Có | Không | — | Số user tạo trong 7 ngày gần nhất. |
| `posts_today` | `integer` | Có | Không | — | Số post active tạo trong 24 giờ gần nhất. |
| `posts_week` | `integer` | Có | Không | — | Số post active tạo trong 7 ngày gần nhất. |
| `comments_today` | `integer` | Có | Không | — | Số comment tạo trong 24 giờ gần nhất. |
| `comments_week` | `integer` | Có | Không | — | Số comment tạo trong 7 ngày gần nhất. |
| `reports_today` | `integer` | Có | Không | — | Số report tạo trong 24 giờ gần nhất. |
| `reports_week` | `integer` | Có | Không | — | Số report tạo trong 7 ngày gần nhất. |
| `pending_reports` | `integer` | Có | Không | — | Tổng report pending hiện tại. |
| `pending_posts` | `integer` | Có | Không | — | Tổng post pending hiện tại. |

### `AdminPostModerationResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `integer` | Có | Không | — | ID tài nguyên; user là string, post/comment/report/notification/tag là integer. |
| `user_id` | `string` | Có | Không | — | ID user sở hữu/được phân tích; trong notification là recipient. |
| `title` | `string` | Có | Không | — | Tiêu đề bài hoặc thông báo tùy DTO. |
| `status` | `string` | Có | Không | — | Trạng thái theo loại tài nguyên; xem bảng quy ước bên dưới. |
| `requested_new_tags` | `string[]` | Không | Không | mặc định=[] | Tên tag mới đang đề nghị duyệt, chưa phải tag đã công bố. |
| `created_at` | `string (date-time)` | Có | Không | format="date-time" | Thời điểm tạo theo UTC ISO 8601 có hậu tố Z. |

### `AdminPostsListResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `items` | `AdminPostModerationResponse[]` | Có | Không | — | Danh sách tài nguyên con theo thứ tự đã nêu ở endpoint. |
| `meta` | `PaginationMeta` | Có | Không | — | PaginationMeta của tập kết quả. |

### `AdminReportsListResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `items` | `ReportResponse[]` | Có | Không | — | Danh sách tài nguyên con theo thứ tự đã nêu ở endpoint. |
| `meta` | `PaginationMeta` | Có | Không | — | PaginationMeta của tập kết quả. |

### `AdminUserResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `string` | Có | Không | — | ID user; user là string, post/comment/report/notification/tag là integer. |
| `username` | `string / null` | Có | Có | — | Tên đăng nhập/định danh hồ sơ; có thể chưa được đặt với tài khoản OAuth. |
| `email` | `string` | Có | Không | — | Địa chỉ email của tài khoản; chỉ xuất hiện trong DTO riêng tư/admin. |
| `full_name` | `string` | Có | Không | — | Tên hiển thị của user. |
| `role` | `string` | Có | Không | — | Vai trò user (ví dụ Student, admin); đây là chuỗi, không phải enum đóng trong schema. |
| `status` | `string` | Có | Không | — | Trạng thái theo loại tài nguyên; xem bảng quy ước bên dưới. |
| `created_at` | `string (date-time)` | Có | Không | format="date-time" | Thời điểm tạo theo UTC ISO 8601 có hậu tố Z. |

### `AdminUsersListResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `items` | `AdminUserResponse[]` | Có | Không | — | Danh sách tài nguyên con theo thứ tự đã nêu ở endpoint. |
| `meta` | `PaginationMeta` | Có | Không | — | PaginationMeta của tập kết quả. |

### `BanUserRequest`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `reason` | `string / null` | Không | Có | maxLength=1000 | Lý do report hoặc lý do ban/unban tùy request. |

### `Body_media_upload_image`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `file` | `string (binary)` | Có | Không | format="binary" | File nhị phân multipart, JPEG/PNG. |

### `BookmarkResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `bookmarked` | `boolean` | Có | Không | — | Trạng thái mong muốn bookmark=true sau PUT. |

### `CollaborativePostListResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `items` | `CollaborativePostResponse[]` | Có | Không | — | Danh sách tài nguyên con theo thứ tự đã nêu ở endpoint. |
| `meta` | `PaginationMeta` | Có | Không | — | PaginationMeta của tập kết quả. |

### `CollaborativePostResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `post` | `PostResponse` | Có | Không | — | PostResponse đầy đủ, tác giả dùng PublicUserSummary. |
| `cf_score` | `number` | Có | Không | — | Điểm collaborative filtering. |
| `cf_reason` | `string` | Có | Không | — | Diễn giải gợi ý cộng tác. |
| `similar_user_count` | `integer` | Không | Không | mặc định=0 | Hiện implementation trả 0, chưa phải số user tương tự đo được. |

### `CommentResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `content` | `string` | Có | Không | minLength=1 | Nội dung bài/bình luận; service trim khi ghi. |
| `id` | `integer` | Có | Không | — | ID tài nguyên; user là string, post/comment/report/notification/tag là integer. |
| `post_id` | `integer` | Có | Không | — | ID post liên quan; SharePostResponse là bài chia sẻ mới. |
| `user_id` | `string` | Có | Không | — | ID user sở hữu/được phân tích; trong notification là recipient. |
| `parent_id` | `integer / null` | Có | Có | — | ID comment cha cùng post, null là comment gốc. |
| `status` | `string` | Không | Không | mặc định="active" | Trạng thái theo loại tài nguyên; xem bảng quy ước bên dưới. |
| `created_at` | `string (date-time)` | Có | Không | format="date-time" | Thời điểm tạo theo UTC ISO 8601 có hậu tố Z. |
| `author` | `PublicUserSummary` | Có | Không | — | PublicUserSummary; không chứa email/provider/status/is_verified/password_hash. |
| `replies` | `CommentResponse[]` | Không | Không | — | Danh sách CommentResponse con, đệ quy. |

### `CompleteProfileRequest`

`additionalProperties=false`: không chấp nhận field lạ.

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `username` | `string` | Có | Không | minLength=3; maxLength=50 | Tên đăng nhập/định danh hồ sơ; có thể chưa được đặt với tài khoản OAuth. |
| `full_name` | `string` | Có | Không | minLength=2; maxLength=255 | Tên hiển thị của user. |
| `avatar_url` | `string / null` | Không | Có | — | URL avatar do ứng dụng lưu; nullable để không có avatar. |
| `bio` | `string / null` | Không | Có | — | Giới thiệu cá nhân. |
| `major` | `string / null` | Không | Có | maxLength=120 | Chuyên ngành học. |
| `academic_year` | `string / null` | Không | Có | maxLength=30 | Năm học/khóa học dạng chuỗi. |
| `career_goal` | `string / null` | Không | Có | maxLength=200 | Mục tiêu nghề nghiệp. |
| `interest_tags` | `string[]` | Không | Không | maxItems=20 | Danh sách tên tag quan tâm. |

### `CreateCommentRequest`

content được strip trước minLength=1; chuỗi chỉ có khoảng trắng bị 422 trước mọi ghi DB.

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `content` | `string` | Có | Không | minLength=1 | Nội dung bài/bình luận; service trim khi ghi. |
| `parent_id` | `integer / null` | Không | Có | — | ID comment cha cùng post, null là comment gốc. |

### `CreatePostRequest`

title được strip trước minLength=5/maxLength=255; title quá ngắn sau trim bị 422 trước mọi ghi DB. content được trim khi service ghi nhưng không có minLength riêng.

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `title` | `string` | Có | Không | minLength=5; maxLength=255 | Tiêu đề bài hoặc thông báo tùy DTO. |
| `content` | `string` | Có | Không | — | Nội dung bài/bình luận; service trim khi ghi. |
| `cover_image` | `string / null` | Không | Có | — | URL ảnh cover tùy chọn; không có cơ chế reservation/ownership media. |
| `tags` | `string[]` | Không | Không | — | Danh sách tên tag gắn với bài. |

### `CreateReportRequest`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `reason` | `string` | Có | Không | enum=["spam", "harassment", "hate_speech", "violence", "misinformation", "other"] | Lý do report hoặc lý do ban/unban tùy request. |
| `details` | `string / null` | Không | Có | maxLength=2000 | Mô tả bổ sung cho report. |

### `CreateTagRequest`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `name` | `string` | Có | Không | minLength=1; maxLength=100 | Tên tag; service trim/lowercase khi ghi. |

### `CurrentUserIdentityResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `string` | Có | Không | — | ID user; user là string, post/comment/report/notification/tag là integer. |
| `username` | `string / null` | Có | Có | — | Tên đăng nhập/định danh hồ sơ; có thể chưa được đặt với tài khoản OAuth. |
| `email` | `string (email)` | Có | Không | format="email" | Địa chỉ email của tài khoản; chỉ xuất hiện trong DTO riêng tư/admin. |
| `full_name` | `string` | Có | Không | — | Tên hiển thị của user. |
| `avatar_url` | `string / null` | Không | Có | — | URL avatar do ứng dụng lưu; nullable để không có avatar. |
| `bio` | `string / null` | Không | Có | — | Giới thiệu cá nhân. |
| `major` | `string / null` | Không | Có | — | Chuyên ngành học. |
| `academic_year` | `string / null` | Không | Có | — | Năm học/khóa học dạng chuỗi. |
| `career_goal` | `string / null` | Không | Có | — | Mục tiêu nghề nghiệp. |
| `interest_tags` | `string[]` | Không | Không | — | Danh sách tên tag quan tâm. |
| `role` | `string` | Có | Không | — | Vai trò user (ví dụ Student, admin); đây là chuỗi, không phải enum đóng trong schema. |
| `status` | `string` | Có | Không | — | Trạng thái theo loại tài nguyên; xem bảng quy ước bên dưới. |
| `provider` | `string` | Có | Không | — | Nguồn đăng nhập local/google theo dữ liệu tài khoản. |
| `is_verified` | `boolean` | Có | Không | — | Cờ xác minh hiện lưu; không đồng nghĩa middleware đang bắt buộc email verification. |
| `profile_completed` | `boolean` | Có | Không | — | Kết quả policy hoàn thành profile, dùng để điều hướng client. |

### `CurrentUserProfileResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `string` | Có | Không | — | ID user; user là string, post/comment/report/notification/tag là integer. |
| `username` | `string / null` | Có | Có | — | Tên đăng nhập/định danh hồ sơ; có thể chưa được đặt với tài khoản OAuth. |
| `full_name` | `string` | Có | Không | — | Tên hiển thị của user. |
| `avatar_url` | `string / null` | Có | Có | — | URL avatar do ứng dụng lưu; nullable để không có avatar. |
| `bio` | `string / null` | Có | Có | — | Giới thiệu cá nhân. |
| `major` | `string / null` | Có | Có | — | Chuyên ngành học. |
| `academic_year` | `string / null` | Có | Có | — | Năm học/khóa học dạng chuỗi. |
| `career_goal` | `string / null` | Có | Có | — | Mục tiêu nghề nghiệp. |
| `interest_tags` | `string[]` | Có | Không | — | Danh sách tên tag quan tâm. |
| `followers_count` | `integer` | Có | Không | — | Số membership follow trỏ đến user. |
| `following_count` | `integer` | Có | Không | — | Số membership user đang follow. |
| `posts_count` | `integer` | Có | Không | — | Số post hiển thị với người gọi, loại deleted. |
| `is_following` | `boolean` | Có | Không | — | Người gọi đang follow user đích. |
| `is_current_user` | `boolean` | Có | Không | — | Hồ sơ thuộc chính người gọi. |
| `email` | `string` | Có | Không | — | Địa chỉ email của tài khoản; chỉ xuất hiện trong DTO riêng tư/admin. |
| `role` | `string` | Có | Không | — | Vai trò user (ví dụ Student, admin); đây là chuỗi, không phải enum đóng trong schema. |
| `status` | `string` | Có | Không | — | Trạng thái theo loại tài nguyên; xem bảng quy ước bên dưới. |
| `created_at` | `string (date-time)` | Có | Không | format="date-time" | Thời điểm tạo theo UTC ISO 8601 có hậu tố Z. |

### `FollowResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `message` | `string` | Có | Không | — | Thông điệp cho người dùng; client không phân tích chuỗi để quyết định logic. |
| `following` | `boolean` | Có | Không | — | Trạng thái mong muốn follow=true sau PUT. |

### `ForgotPasswordRequest`

`additionalProperties=false`: không chấp nhận field lạ.

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `email` | `string (email)` | Có | Không | maxLength=255; format="email" | Địa chỉ email của tài khoản; chỉ xuất hiện trong DTO riêng tư/admin. |

### `HealthResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `status` | `string` | Có | Không | — | Trạng thái theo loại tài nguyên; xem bảng quy ước bên dưới. |
| `message` | `string` | Có | Không | — | Thông điệp cho người dùng; client không phân tích chuỗi để quyết định logic. |

### `LikeResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `liked` | `boolean` | Có | Không | — | Trạng thái mong muốn đã like=true sau PUT. |

### `LoginRequest`

`additionalProperties=false`: không chấp nhận field lạ.

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `identifier` | `string` | Có | Không | — | Email hoặc username dùng đăng nhập. |
| `password` | `string` | Có | Không | minLength=6; maxLength=128 | Password thô chỉ trong request, được băm khi lưu; không có trong response. |

### `LogoutRequest`

`additionalProperties=false`: không chấp nhận field lạ.

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `refresh_token` | `string` | Có | Không | minLength=10 | JWT refresh gắn AuthSession; chỉ gửi tới luồng auth thích hợp. |

### `MessageResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `message` | `string` | Có | Không | — | Thông điệp cho người dùng; client không phân tích chuỗi để quyết định logic. |

### `ModeratePostRequest`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `status` | `string` | Có | Không | enum=["active", "rejected"] | Trạng thái theo loại tài nguyên; xem bảng quy ước bên dưới. |

### `ModerateReportRequest`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `status` | `string` | Có | Không | pattern="^(pending\|reviewed\|dismissed\|resolved)$" | Trạng thái theo loại tài nguyên; xem bảng quy ước bên dưới. |
| `action` | `string` | Không | Không | enum=["none", "hide_post", "hide_comment", "ban_author", "hide_post_and_ban_author", "hide_comment_and_ban_author"]; mặc định="none" | Hành động moderation; chỉ áp dụng khi resolved. |
| `notes` | `string / null` | Không | Có | maxLength=1000 | Ghi chú admin được lưu trong audit log; không xuất hiện trong ReportResponse. |

### `NotificationResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `integer` | Có | Không | — | ID tài nguyên; user là string, post/comment/report/notification/tag là integer. |
| `user_id` | `string` | Có | Không | — | ID user sở hữu/được phân tích; trong notification là recipient. |
| `actor_id` | `string / null` | Có | Có | — | ID user gây ra notification; null với sự kiện hệ thống/ẩn danh. |
| `type` | `string` | Có | Không | — | Loại notification dạng chuỗi; trong ProblemDetails là URI định danh loại lỗi. |
| `title` | `string` | Có | Không | — | Tiêu đề bài hoặc thông báo tùy DTO. |
| `message` | `string / null` | Có | Có | — | Thông điệp cho người dùng; client không phân tích chuỗi để quyết định logic. |
| `is_read` | `boolean` | Có | Không | — | Notification đã được recipient đọc. |
| `post_id` | `integer / null` | Có | Có | — | ID post liên quan; SharePostResponse là bài chia sẻ mới. |
| `comment_id` | `integer / null` | Có | Có | — | ID comment đích/liên quan. |
| `report_id` | `integer / null` | Có | Có | — | ID report liên quan. |
| `created_at` | `string (date-time)` | Có | Không | format="date-time" | Thời điểm tạo theo UTC ISO 8601 có hậu tố Z. |

### `PaginationMeta`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `page` | `integer` | Có | Không | minimum=1.0 | Trang offset bắt đầu từ 1. |
| `page_size` | `integer` | Có | Không | minimum=0.0 | Kích thước trang; similar dùng số item thực trả, có thể 0. |
| `total` | `integer` | Có | Không | minimum=0.0 | Tổng trong tập/cửa sổ có thể phục vụ theo endpoint. |
| `total_pages` | `integer` | Có | Không | minimum=0.0 | ceil(total/page_size) với collection thường; total=0 luôn là 0. |

### `PostListResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `items` | `PostResponse[]` | Có | Không | — | Danh sách tài nguyên con theo thứ tự đã nêu ở endpoint. |
| `meta` | `PaginationMeta` | Có | Không | — | PaginationMeta của tập kết quả. |

### `PostResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `title` | `string` | Có | Không | minLength=5; maxLength=255 | Tiêu đề bài hoặc thông báo tùy DTO. |
| `content` | `string` | Có | Không | — | Nội dung bài/bình luận; service trim khi ghi. |
| `cover_image` | `string / null` | Không | Có | — | URL ảnh cover tùy chọn; không có cơ chế reservation/ownership media. |
| `tags` | `string[]` | Không | Không | — | Danh sách tên tag gắn với bài. |
| `id` | `integer` | Có | Không | — | ID tài nguyên; user là string, post/comment/report/notification/tag là integer. |
| `user_id` | `string` | Có | Không | — | ID user sở hữu/được phân tích; trong notification là recipient. |
| `status` | `string / null` | Có | Có | — | Trạng thái theo loại tài nguyên; xem bảng quy ước bên dưới. |
| `original_post_id` | `integer / null` | Không | Có | — | ID post nguồn của bài chia sẻ; null với post thường. |
| `share_caption` | `string / null` | Không | Có | — | Lời dẫn của bài chia sẻ. |
| `requested_new_tags` | `string[]` | Không | Không | — | Tên tag mới đang đề nghị duyệt, chưa phải tag đã công bố. |
| `created_at` | `string (date-time)` | Có | Không | format="date-time" | Thời điểm tạo theo UTC ISO 8601 có hậu tố Z. |
| `author` | `PublicUserSummary` | Có | Không | — | PublicUserSummary; không chứa email/provider/status/is_verified/password_hash. |
| `likes_count` | `integer` | Không | Không | mặc định=0 | Số lượt like hiện tại. |
| `comments_count` | `integer` | Không | Không | mặc định=0 | Số bình luận được thống kê theo thuật toán hiện tại; không bảo đảm đồng nhất với độ dài cây comment active. |
| `views_count` | `integer` | Không | Không | mặc định=0 | Số sự kiện PostView; chỉ POST views tạo sự kiện. |
| `shares_count` | `integer` | Không | Không | mặc định=0 | Số sự kiện PostShare. |
| `trending_score` | `integer` | Không | Không | mặc định=0 | Điểm số nguyên hiển thị theo nhánh thống kê; không phải hot_score float của mọi thuật toán. |
| `is_liked` | `boolean` | Không | Không | mặc định=false | Membership like của người gọi. |
| `is_bookmarked` | `boolean` | Không | Không | mặc định=false | Membership bookmark của người gọi. |

### `ProblemDetails`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `type` | `string` | Có | Không | — | URI loại problem, hiện about:blank. |
| `title` | `string` | Có | Không | — | Tên HTTP status ngắn do server sinh; không phải tiêu đề post. |
| `status` | `integer` | Có | Không | — | HTTP status số, trùng response status. |
| `detail` | `string` | Có | Không | — | Mô tả lỗi an toàn cho client. |
| `instance` | `string` | Có | Không | — | Path request tạo lỗi, không kèm query. |
| `code` | `string` | Có | Không | — | Mã ứng dụng ổn định dùng cho logic client. |
| `request_id` | `string` | Có | Không | — | UUID do server tạo, cũng trả ở X-Request-ID. |
| `errors` | `ValidationIssue[] / null` | Không | Có | — | Danh sách ValidationIssue khi 422; không chứa input/context nhạy cảm. |

### `ProfileAnalysisResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `user_id` | `string` | Có | Không | — | ID user sở hữu/được phân tích; trong notification là recipient. |
| `profile_summary` | `UserProfileSummary` | Có | Không | — | UserProfileSummary của chính người gọi. |
| `recommendation_message` | `string` | Không | Không | mặc định="Gợi ý dựa trên thông tin profile của bạn" | Gợi ý hoàn thiện profile dạng thông điệp. |

### `ProfileBasedPostListResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `items` | `ProfileBasedPostResponse[]` | Có | Không | — | Danh sách tài nguyên con theo thứ tự đã nêu ở endpoint. |
| `meta` | `PaginationMeta` | Có | Không | — | PaginationMeta của tập kết quả. |

### `ProfileBasedPostResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `post` | `PostResponse` | Có | Không | — | PostResponse đầy đủ, tác giả dùng PublicUserSummary. |
| `profile_score` | `number` | Có | Không | — | Điểm phù hợp với profile. |
| `recommendation_reason` | `string` | Có | Không | — | Diễn giải gợi ý theo profile. |

### `PublicUserProfileResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `string` | Có | Không | — | ID user; user là string, post/comment/report/notification/tag là integer. |
| `username` | `string / null` | Có | Có | — | Tên đăng nhập/định danh hồ sơ; có thể chưa được đặt với tài khoản OAuth. |
| `full_name` | `string` | Có | Không | — | Tên hiển thị của user. |
| `avatar_url` | `string / null` | Có | Có | — | URL avatar do ứng dụng lưu; nullable để không có avatar. |
| `bio` | `string / null` | Có | Có | — | Giới thiệu cá nhân. |
| `major` | `string / null` | Có | Có | — | Chuyên ngành học. |
| `academic_year` | `string / null` | Có | Có | — | Năm học/khóa học dạng chuỗi. |
| `career_goal` | `string / null` | Có | Có | — | Mục tiêu nghề nghiệp. |
| `interest_tags` | `string[]` | Có | Không | — | Danh sách tên tag quan tâm. |
| `followers_count` | `integer` | Có | Không | — | Số membership follow trỏ đến user. |
| `following_count` | `integer` | Có | Không | — | Số membership user đang follow. |
| `posts_count` | `integer` | Có | Không | — | Số post hiển thị với người gọi, loại deleted. |
| `is_following` | `boolean` | Có | Không | — | Người gọi đang follow user đích. |
| `is_current_user` | `boolean` | Có | Không | — | Hồ sơ thuộc chính người gọi. |

### `PublicUserSummary`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `string` | Có | Không | — | ID user; user là string, post/comment/report/notification/tag là integer. |
| `username` | `string / null` | Có | Có | — | Tên đăng nhập/định danh hồ sơ; có thể chưa được đặt với tài khoản OAuth. |
| `full_name` | `string` | Có | Không | — | Tên hiển thị của user. |
| `avatar_url` | `string / null` | Không | Có | — | URL avatar do ứng dụng lưu; nullable để không có avatar. |
| `bio` | `string / null` | Không | Có | — | Giới thiệu cá nhân. |
| `role` | `string` | Có | Không | — | Vai trò user (ví dụ Student, admin); đây là chuỗi, không phải enum đóng trong schema. |

### `RefreshTokenRequest`

`additionalProperties=false`: không chấp nhận field lạ.

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `refresh_token` | `string` | Có | Không | minLength=10 | JWT refresh gắn AuthSession; chỉ gửi tới luồng auth thích hợp. |

### `RegisterRequest`

`additionalProperties=false`: không chấp nhận field lạ.

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `username` | `string` | Có | Không | minLength=3; maxLength=50 | Tên đăng nhập/định danh hồ sơ; có thể chưa được đặt với tài khoản OAuth. |
| `email` | `string (email)` | Có | Không | maxLength=255; format="email" | Địa chỉ email của tài khoản; chỉ xuất hiện trong DTO riêng tư/admin. |
| `password` | `string` | Có | Không | minLength=6; maxLength=128 | Password thô chỉ trong request, được băm khi lưu; không có trong response. |
| `full_name` | `string` | Có | Không | minLength=2; maxLength=255 | Tên hiển thị của user. |

### `ReportResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `integer` | Có | Không | — | ID tài nguyên; user là string, post/comment/report/notification/tag là integer. |
| `reporter_id` | `string / null` | Có | Có | — | ID user tạo report. |
| `post_id` | `integer / null` | Có | Có | — | ID post liên quan; SharePostResponse là bài chia sẻ mới. |
| `comment_id` | `integer / null` | Có | Có | — | ID comment đích/liên quan. |
| `reason` | `string` | Có | Không | — | Lý do report hoặc lý do ban/unban tùy request. |
| `details` | `string / null` | Có | Có | — | Mô tả bổ sung cho report. |
| `status` | `string` | Có | Không | — | Trạng thái theo loại tài nguyên; xem bảng quy ước bên dưới. |
| `reviewed_by` | `string / null` | Có | Có | — | ID admin xử lý report; null trước khi xử lý. |
| `reviewed_at` | `string (date-time) / null` | Có | Có | format="date-time" | Thời điểm xử lý report UTC, null trước khi xử lý. |
| `created_at` | `string (date-time)` | Có | Không | format="date-time" | Thời điểm tạo theo UTC ISO 8601 có hậu tố Z. |

### `ResendVerificationRequest`

`additionalProperties=false`: không chấp nhận field lạ.

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `email` | `string (email)` | Có | Không | maxLength=255; format="email" | Địa chỉ email của tài khoản; chỉ xuất hiện trong DTO riêng tư/admin. |

### `ResetPasswordRequest`

`additionalProperties=false`: không chấp nhận field lạ.

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `token` | `string` | Có | Không | minLength=12 | Token email verification/reset password theo endpoint. |
| `password` | `string` | Có | Không | minLength=6; maxLength=128 | Password thô chỉ trong request, được băm khi lưu; không có trong response. |

### `RootResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `message` | `string` | Có | Không | — | Thông điệp cho người dùng; client không phân tích chuỗi để quyết định logic. |
| `version` | `string` | Có | Không | — | Phiên bản thông tin ứng dụng. |
| `docs` | `string` | Có | Không | — | Đường dẫn Swagger UI. |
| `openapi_schema` | `string` | Có | Không | — | Đường dẫn OpenAPI máy đọc. |

### `SharePostRequest`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `caption` | `string / null` | Không | Có | maxLength=2000 | Lời dẫn khi tạo bài chia sẻ; tối đa 2000 ký tự. |

### `SharePostResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `post_id` | `integer` | Có | Không | — | ID post liên quan; SharePostResponse là bài chia sẻ mới. |
| `original_post_id` | `integer` | Có | Không | — | ID post nguồn của bài chia sẻ; null với post thường. |

### `SimilarPostListResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `items` | `SimilarPostResponse[]` | Có | Không | — | Danh sách tài nguyên con theo thứ tự đã nêu ở endpoint. |
| `meta` | `PaginationMeta` | Có | Không | — | PaginationMeta của tập kết quả. |

### `SimilarPostResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `post` | `PostResponse` | Có | Không | — | PostResponse đầy đủ, tác giả dùng PublicUserSummary. |
| `similarity_score` | `number` | Có | Không | — | Điểm tương đồng nội dung. |
| `similarity_reason` | `string` | Có | Không | — | Diễn giải tương đồng nội dung. |

### `TagResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `integer` | Có | Không | — | ID tài nguyên; user là string, post/comment/report/notification/tag là integer. |
| `name` | `string` | Có | Không | — | Tên tag; service trim/lowercase khi ghi. |
| `slug` | `string` | Có | Không | — | Slug ASCII sinh từ tên tag. |
| `created_at` | `string (date-time)` | Có | Không | format="date-time" | Thời điểm tạo theo UTC ISO 8601 có hậu tố Z. |

### `TokenResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `access_token` | `string` | Có | Không | — | JWT access dùng Authorization: Bearer. |
| `refresh_token` | `string` | Có | Không | — | JWT refresh gắn AuthSession; chỉ gửi tới luồng auth thích hợp. |
| `token_type` | `string` | Không | Không | mặc định="bearer" | Kiểu token, mặc định bearer. |
| `expires_in` | `integer` | Có | Không | — | Thời gian sống access token tính bằng giây, lấy từ cấu hình runtime. |

### `TrendingPostListResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `items` | `TrendingPostResponse[]` | Có | Không | — | Danh sách tài nguyên con theo thứ tự đã nêu ở endpoint. |
| `meta` | `PaginationMeta` | Có | Không | — | PaginationMeta của tập kết quả. |

### `TrendingPostResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `post` | `PostResponse` | Có | Không | — | PostResponse đầy đủ, tác giả dùng PublicUserSummary. |
| `trend_rank` | `integer` | Có | Không | — | Xếp hạng toàn cục trong tập trending, bắt đầu 1. |
| `hot_score` | `number` | Có | Không | — | Điểm xu hướng float có time decay. |
| `trending_reason` | `string` | Có | Không | — | Diễn giải vì sao bài đang trending. |

### `TrendingTagListResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `items` | `TrendingTagResponse[]` | Có | Không | — | Danh sách tài nguyên con theo thứ tự đã nêu ở endpoint. |
| `updated_at` | `string (date-time)` | Có | Không | format="date-time" | Thời điểm tạo kết quả tính toán theo UTC. |

### `TrendingTagResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `tag_name` | `string` | Có | Không | — | Tên tag được xếp hạng. |
| `post_count` | `integer` | Có | Không | — | Số post active đủ điều kiện chứa tag. |
| `trend_score` | `number` | Có | Không | — | Tổng điểm xu hướng của tag. |

### `UpdatePostRequest`

Ràng buộc ngoài JSON Schema: ít nhất một key. Chỉ cover_image nullable; title/content/tags/status omittable nhưng không nhận explicit null. Extra field bị từ chối. title được strip trước minLength=5/maxLength=255.

`additionalProperties=false`: không chấp nhận field lạ.

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `title` | `string` | Không | Không | minLength=5; maxLength=255; explicit null → 422 | Tiêu đề bài hoặc thông báo tùy DTO. |
| `content` | `string` | Không | Không | —; explicit null → 422 | Nội dung bài/bình luận; service trim khi ghi. |
| `cover_image` | `string / null` | Không | Có | — | URL ảnh cover tùy chọn; không có cơ chế reservation/ownership media. |
| `tags` | `string[]` | Không | Không | —; explicit null → 422 | Danh sách tên tag gắn với bài. |
| `status` | `string` | Không | Không | pattern="^(pending\|active\|rejected)$"; explicit null → 422 | Trạng thái theo loại tài nguyên; xem bảng quy ước bên dưới. |

### `UpdateProfileRequest`

Ràng buộc ngoài JSON Schema: ít nhất một key; full_name/interest_tags không nullable; extra field bị từ chối.

`additionalProperties=false`: không chấp nhận field lạ.

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `full_name` | `string` | Không | Không | minLength=2; maxLength=255 | Tên hiển thị của user. |
| `bio` | `string / null` | Không | Có | — | Giới thiệu cá nhân. |
| `avatar_url` | `string / null` | Không | Có | — | URL avatar do ứng dụng lưu; nullable để không có avatar. |
| `major` | `string / null` | Không | Có | maxLength=120 | Chuyên ngành học. |
| `academic_year` | `string / null` | Không | Có | maxLength=30 | Năm học/khóa học dạng chuỗi. |
| `career_goal` | `string / null` | Không | Có | maxLength=200 | Mục tiêu nghề nghiệp. |
| `interest_tags` | `string[]` | Không | Không | maxItems=20 | Danh sách tên tag quan tâm. |

### `UpdateTagRequest`

`additionalProperties=false`: không chấp nhận field lạ.

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `name` | `string` | Có | Không | minLength=1; maxLength=100 | Tên tag; service trim/lowercase khi ghi. |

### `UploadImageResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `url` | `string` | Có | Không | — | URL công khai của file đã lưu dưới /uploads. |

### `UserCommentResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `integer` | Có | Không | — | ID tài nguyên; user là string, post/comment/report/notification/tag là integer. |
| `post_id` | `integer` | Có | Không | — | ID post liên quan; SharePostResponse là bài chia sẻ mới. |
| `post_title` | `string / null` | Có | Có | — | Tiêu đề post liên quan đến bình luận. |
| `content` | `string` | Có | Không | — | Nội dung bài/bình luận; service trim khi ghi. |
| `created_at` | `string (date-time)` | Có | Không | format="date-time" | Thời điểm tạo theo UTC ISO 8601 có hậu tố Z. |

### `UserPostResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `id` | `integer` | Có | Không | — | ID tài nguyên; user là string, post/comment/report/notification/tag là integer. |
| `title` | `string` | Có | Không | — | Tiêu đề bài hoặc thông báo tùy DTO. |
| `content` | `string` | Có | Không | — | Nội dung bài/bình luận; service trim khi ghi. |
| `cover_image` | `string / null` | Có | Có | — | URL ảnh cover tùy chọn; không có cơ chế reservation/ownership media. |
| `status` | `string / null` | Có | Có | — | Trạng thái theo loại tài nguyên; xem bảng quy ước bên dưới. |
| `created_at` | `string (date-time)` | Có | Không | format="date-time" | Thời điểm tạo theo UTC ISO 8601 có hậu tố Z. |

### `UserProfileSummary`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `interest_tags` | `string[]` | Không | Không | — | Danh sách tên tag quan tâm. |
| `major` | `string` | Không | Không | mặc định="" | Chuyên ngành học. |
| `academic_year` | `string` | Không | Không | mặc định="" | Năm học/khóa học dạng chuỗi. |
| `career_goal` | `string` | Không | Không | mặc định="" | Mục tiêu nghề nghiệp. |
| `profile_strength` | `number` | Có | Không | — | Mức đầy đủ profile, từ 0 đến 1 theo năm tiêu chí. |
| `recommendations_count` | `integer` | Không | Không | mặc định=0 | Số bài active chưa được user like, trước khi lọc riêng của recommendation. |
| `profile_completeness` | `object` | Không | Không | — | Object mở; hiện gồm has_interest_tags, has_major, has_academic_year, has_career_goal, has_bio (boolean). |

### `ValidationIssue`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `loc` | `(string / integer)[]` | Có | Không | — | Vị trí trường sai gồm body/query/path và tên trường/chỉ số. |
| `msg` | `string` | Có | Không | — | Thông điệp đã khử input: Field required. hoặc Invalid value. |
| `type` | `string` | Có | Không | — | Loại lỗi validation máy đọc, ví dụ missing/string_too_short. |

### `VerificationResponse`

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `message` | `string` | Có | Không | — | Thông điệp cho người dùng; client không phân tích chuỗi để quyết định logic. |
| `verification_token` | `string / null` | Không | Có | — | Trường tùy chọn còn trong DTO; hiện null vì verification tắt. |

### `VerifyEmailRequest`

`additionalProperties=false`: không chấp nhận field lạ.

| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |
|---|---|---|---|---|---|
| `token` | `string` | Có | Không | minLength=12 | Token email verification/reset password theo endpoint. |

## 13. Mã lỗi (Error Codes)

Tất cả lỗi HTTP được handler chuẩn hóa về RFC 9457 `application/problem+json`. type/title/status luôn có; implementation hiện luôn thêm detail/instance/code/request_id; errors chỉ có khi validation. Lỗi >=500 chỉ trả `Internal server error.`; stack trace/SQL/credential chỉ ở log server, không trong payload. Validation bỏ input/context và chỉ trả vị trí, loại, thông điệp khử nhạy cảm.

| Code | HTTP | Điều kiện |
|---|---|---|
| `BAD_REQUEST` | 400 | Quy tắc nghiệp vụ không hợp lệ: duplicate register/tag create, reset token sai, tự follow/ban, xóa bài có comment, xóa notification chưa đọc, cặp status/action moderation sai, MIME/signature ảnh sai. |
| `UNAUTHORIZED` | 401 | Thiếu/sai/hết hạn JWT, sai password, refresh session/token sai; kèm WWW-Authenticate: Bearer. |
| `FORBIDDEN` | 403 | Banned/inactive, chưa hoàn thành profile, thiếu role/ownership/visibility. |
| `NOT_FOUND` | 404 | Resource thiếu/deleted, notification không thuộc recipient, parent/comment sai post; login với tài khoản thiếu hiện cũng dùng 404. |
| `CONFLICT` | 409 | Report trùng, update tag trùng hoặc xung đột nghiệp vụ không có code riêng. |
| `CONCURRENT_MODIFICATION` | 409 | Không lấy được SQL Server aggregate lock trong thời gian chờ; cân nhắc retry theo tính idempotent. |
| `POST_ALREADY_MODERATED` | 409 | Post đã có trạng thái terminal khác quyết định yêu cầu. |
| `REPORT_ALREADY_MODERATED` | 409 | Report đã rời pending và status/action khác quyết định cũ. |
| `PAYLOAD_TOO_LARGE` | 413 | File ảnh >5 MiB hoặc request multipart >6 MiB. |
| `VALIDATION_ERROR` | 422 | Sai kiểu, thiếu field, giới hạn/pattern/enum sai, empty PATCH, null/extra bị cấm. |
| `RATE_LIMITED` | 429 | Dự phòng hợp đồng; chưa có limiter ứng dụng hoặc quota cụ thể. |
| `METHOD_NOT_ALLOWED` | 405 | Dùng method chưa đăng ký. |
| `INTERNAL_ERROR` | 500 | Lỗi không dự kiến, DB/storage/provider/config; detail đã che thông tin nội bộ. |

Schema OpenAPI dự phòng nhiều status lỗi cho mỗi business operation; bảng lỗi cụ thể trong mục 4–11 nêu các nhánh thực sự có ý nghĩa. Không suy ra một endpoint tự có rate limiting chỉ vì OpenAPI khai báo 429. Framework có thể dùng HTTP_n cho status không có ánh xạ nêu trên.

Ví dụ lỗi validation, không echo password/nội dung request:

```json
{
  "type": "about:blank",
  "title": "Unprocessable Entity",
  "status": 422,
  "detail": "Request validation failed.",
  "instance": "/api/v1/posts",
  "code": "VALIDATION_ERROR",
  "request_id": "44444444-4444-4444-8444-444444444444",
  "errors": [
    {
      "loc": [
        "body",
        "title"
      ],
      "msg": "Invalid value.",
      "type": "string_too_short"
    }
  ]
}
```

Ví dụ conflict moderation:

```json
{
  "type": "about:blank",
  "title": "Conflict",
  "status": 409,
  "detail": "Post has already been moderated.",
  "instance": "/api/v1/admin/posts/42/moderation",
  "code": "POST_ALREADY_MODERATED",
  "request_id": "44444444-4444-4444-8444-444444444444"
}
```

Ví dụ thiếu Bearer token:

```json
{
  "type": "about:blank",
  "title": "Unauthorized",
  "status": 401,
  "detail": "Authentication credentials were not provided.",
  "instance": "/api/v1/users/me",
  "code": "UNAUTHORIZED",
  "request_id": "44444444-4444-4444-8444-444444444444"
}
```

## 14. Ma trận xác thực và phân quyền (Authentication and Authorization Matrix)

| Nhãn | Endpoint/operation | Quyền bắt buộc |
|---|---|---|
| public | `auth_forgot_password`, `auth_google_callback`, `auth_google_login`, `auth_login`, `auth_logout`, `auth_refresh`, `auth_register`, `auth_resend_verification`, `auth_reset_password`, `auth_verify_email`, `system_root`, `system_health` | Public: không yêu cầu Authorization. |
| authenticated | `auth_me`, `users_complete_profile`, `users_get_by_id` | Bearer access JWT hợp lệ; user tồn tại, không deleted/banned. Cho phép profile chưa hoàn thành; không yêu cầu role cụ thể. |
| active_user | `feed_list`, `media_upload_image`, `notifications_list`, `notifications_delete`, `notifications_mark_read`, `posts_create`, `posts_delete`, `posts_get_by_id`, `posts_update`, `posts_unbookmark`, `posts_bookmark`, `comments_list`, `comments_create`, `comments_create_report`, `posts_unlike`, `posts_like`, `posts_create_report`, `posts_share`, `posts_record_view`, `recommendations_list_collaborative`, `recommendations_list_similar`, `recommendations_list_profile`, `recommendations_get_profile_analysis`, `recommendations_get_profile_summary`, `recommendations_list_trending`, `tags_list`, `recommendations_list_trending_tags`, `users_get_profile`, `users_list_comments`, `users_list_posts`, `users_get_current`, `users_update_current`, `users_list_bookmarks`, `users_unfollow`, `users_follow` | Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể. |
| admin | `admin_get_analytics`, `admin_list_pending_posts`, `admin_moderate_post`, `admin_list_reports`, `admin_moderate_report`, `admin_list_tags`, `admin_create_tag`, `admin_delete_tag`, `admin_update_tag`, `admin_list_users`, `admin_unban_user`, `admin_ban_user` | Bearer access JWT; user active, profile đã hoàn thành và role=admin (không phân biệt hoa thường). |

Ownership bổ sung: users/me và bookmarks chỉ chính mình; notification chỉ recipient; post update chỉ tác giả; post delete tác giả/admin; membership me chỉ người gọi; post visibility V áp dụng interaction/comment; similar chỉ dùng nguồn active và trả rỗng nếu không đủ điều kiện. Profile công khai/author DTO không có email; auth/me/current profile chỉ chính mình; AdminUserResponse có email dành riêng admin. Role kiểm tra server-side, client ẩn nút không thay quyền.

get_current_user không yêu cầu status=active cho mọi trường hợp ngoài banned/deleted; active_user mới bắt buộc active và completed profile. Không dùng is_verified làm gate hiện tại. Profile completion phải có Bearer nhưng không bắt user đã hoàn thành profile để gọi chính nó.

## 15. Chính sách tương thích và phiên bản API (API Compatibility and Versioning Policy)

URL-based major version `/api/v1`. Thay field đang có, type/nullable/required, method/path, semantics/quyền, success status hoặc loại bỏ operation là breaking change cần cập nhật backend, frontend, frozen map/tests và tài liệu cùng release; khi cần phục vụ external consumers lâu dài phải lên kế hoạch major version thực sự. Thêm field response optional hoặc capability độc lập có thể tương thích nếu consumer bỏ qua field lạ; không tự tạo v2 chỉ vì đổi tên mỹ thuật. Không có compatibility alias được giữ lại trong migration này và không có external consumer nào trong repository cần alias.

Đợt migration này là breaking change có phối hợp: namespace /api/v1; PUT update cũ → PATCH; toggle like/bookmark → PUT/DELETE state; follow POST → PUT; notification read POST → PUT; approve/reject gộp PUT moderation; private bookmarks thành users/me; feed có page/page_size/items/meta; public author loại bỏ dữ liệu riêng tư; lỗi ProblemDetails thay detail-only; create=201, queued reset=202, delete/logout=204; GET post không còn tự ghi view, client gọi POST views riêng. Chi tiết đầy đủ ở mapping mục 17. Không đổi JWT rotation/session model hoặc thuật toán recommendation.

**OAuth deployment:** cập nhật Google provider và GOOGLE_REDIRECT_URI trước khi chuyển traffic tới callback v1; callback cũ không còn được đăng ký. Frontend/auth API origin và mọi consumer phải deploy tương thích cùng đợt. Không có DB migration schema mới cho việc đổi contract. Alembic vẫn chạy thành bước riêng; startup không chạy DDL/create_all. Docker Compose, Render và GitHub Actions giữ entrypoint `python -m app`, quy trình migrations không được nhập vào app startup.

Code helper/DTO alias nội bộ không phải HTTP compatibility route. File tag_router cũ không từng được central factory đăng ký nên không phải endpoint public bị loại; danh mục tag hoạt động vẫn được bảo toàn qua tags_list và admin CRUD. Không có independent search/edit-delete-comment/R2 giả.

## 16. Kiểm chứng hợp đồng API (API Contract Verification)

Nguồn sự thật: `app.factory.create_app().openapi()` và route đăng ký thực tế; `/openapi.json` dùng cùng schema. Không mở DB để export OpenAPI. Frozen migration inventory: `backend/tests/api_v1_contract.json` (58 legacy business → 60 v1 business); hạ tầng thêm 2, tổng 62. FastAPI/Pydantic dùng dependencies đã pin của backend; tránh export bằng môi trường Python khác version.

Từ thư mục backend, dùng interpreter `.venv/Scripts/python.exe` trên Windows (hoặc `.venv/bin/python` trên POSIX) tương ứng cài requirements:

```powershell
python -m scripts.check_api_contract --export .tmp/openapi-v1.json
python -m scripts.render_api_contract
python -m scripts.check_api_contract --check-docs
python -m pytest -q
```

Từ frontend:

```powershell
npm run test:contract
npx tsc --noEmit
npm run lint
npm run build
```

check_api_contract kiểm tra OpenAPI 3.1, ref DTO, không trùng route/operation_id, namespace/mapping, success status, request/response DTO, auth, problem content type và field public. --check-docs kiểm tra coverage tất cả operation_id/method-path/schema/field cùng SHA-256 trên contract projection (parameters, body, response, security, components). Marker ở đầu tài liệu phải khớp; không sửa marker thủ công để bỏ qua drift. Renderer dùng schema trực tiếp cho bảng/constraints và behavior đã review trong cùng script, tự kiểm tra inventory/field coverage và ví dụ bằng Pydantic trước khi ghi tài liệu. Khi thay business rule cần review phần ghi chú behavior nữa; fingerprint không chứng minh tính đúng của câu văn. Tài liệu này là output duy nhất, không tạo thêm API reference thủ công.

Kiểm tra tích hợp cần SQL Server/migration/provider/email thật phải chạy trong môi trường có hạ tầng đó; unit/contract tests không tự chứng minh provider redirect registration, email delivery, live R2 (chưa triển khai) hoặc production persistence. Lệnh và kết quả thực tế của release phải được báo cáo từ lần chạy thật, không suy ra chỉ từ tài liệu.

**Kết quả kiểm chứng đợt chuẩn hóa (19/11/2026):** bộ backend kết hợp chạy bằng môi trường pin đạt **354 passed, 39 warnings** (195.95 giây), gồm kiểm tra contract/nghiệp vụ và bộ HTTP security độc lập. Frontend đạt **13 contract tests**, TypeScript `tsc --noEmit`, lint (4 cảnh báo có từ trước) và Next production build **18 pages**. SQL Server thật đã kiểm tra baseline/adoption, expand-backfill-contract, Outbox, HTTP/private DTO, GET chỉ đọc, share atomic, concurrent likes/reports và migration/app locks; database thử nghiệm được xóa sau kiểm tra. Docker production image đã build và chạy entrypoint mặc định `python -m app`, HTTP health/OpenAPI 62 operations đạt; `docker compose config --quiet` đạt. Schema Linux container và môi trường pin local có cùng fingerprint. Đây là kết quả của đợt chạy cụ thể, không phải bảo đảm mọi môi trường. Browser E2E, cloud deployment, Google provider registration thực tế và email delivery thực tế chưa được kiểm tra; R2 vẫn chưa triển khai.

## 17. Ánh xạ endpoint legacy sang v1 (Legacy-to-v1 Endpoint Mapping)

Đủ **58 method/path legacy duy nhất** từ inventory router đã đăng ký. Cột v1 có thể chứa hai method khi tách toggle; hai legacy approve/reject cùng trỏ một operation. Không có route alias cũ được giữ lại.

| Legacy method/path | v1 method/path | Migration/semantics |
|---|---|---|
| `DELETE /api/admin/tags/{tag_id}` | `DELETE /api/v1/admin/tags/{tag_id}` | Success không body 204 (trừ unban có representation). |
| `DELETE /api/posts/{post_id}` | `DELETE /api/v1/posts/{post_id}` | Success không body 204 (trừ unban có representation). |
| `DELETE /follow/{user_id}` | `DELETE /api/v1/users/{user_id}/followers/me` | Success không body 204 (trừ unban có representation). |
| `DELETE /users/me/notifications/{notification_id}` | `DELETE /api/v1/notifications/{notification_id}` | Success không body 204 (trừ unban có representation). |
| `GET /api/admin/analytics/overview` | `GET /api/v1/admin/analytics/overview` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /api/admin/posts/pending` | `GET /api/v1/admin/posts/pending` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /api/admin/reports` | `GET /api/v1/admin/reports` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /api/admin/tags` | `GET /api/v1/admin/tags` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /api/admin/users` | `GET /api/v1/admin/users` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /api/posts/feed` | `GET /api/v1/feed` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /api/posts/profile/analysis` | `GET /api/v1/recommendations/profile-analysis` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /api/posts/profile/summary` | `GET /api/v1/recommendations/profile-summary` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /api/posts/recommendations/collaborative` | `GET /api/v1/recommendations/collaborative` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /api/posts/recommendations/profile` | `GET /api/v1/recommendations/profile` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /api/posts/tags` | `GET /api/v1/tags` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /api/posts/trending/suggestions` | `GET /api/v1/recommendations/trending` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /api/posts/trending/tags` | `GET /api/v1/tags/trending` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /api/posts/{post_id}` | `GET /api/v1/posts/{post_id}` | GET read-only; ghi view qua POST /api/v1/posts/{post_id}/views. |
| `GET /api/posts/{post_id}/comments/` | `GET /api/v1/posts/{post_id}/comments` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /api/posts/{post_id}/similar` | `GET /api/v1/recommendations/posts/{post_id}/similar` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /auth/google/callback` | `GET /api/v1/auth/google/callback` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /auth/google/login` | `GET /api/v1/auth/google/login` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /auth/me` | `GET /api/v1/auth/me` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /auth/users/{user_id}` | `GET /api/v1/users/{user_id}` | PublicUserSummary không còn email/provider/status/is_verified. |
| `GET /users/me` | `GET /api/v1/users/me` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /users/me/notifications` | `GET /api/v1/notifications` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /users/{username}` | `GET /api/v1/users/by-username/{username}` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /users/{username}/bookmarks` | `GET /api/v1/users/me/bookmarks` | Chỉ dữ liệu chính mình, không nhận username của người khác. |
| `GET /users/{username}/comments` | `GET /api/v1/users/by-username/{username}/comments` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `GET /users/{username}/posts` | `GET /api/v1/users/by-username/{username}/posts` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /api/admin/posts/{post_id}/approve` | `PUT /api/v1/admin/posts/{post_id}/moderation` | Gộp moderation, body {"status":"active"}; terminal trùng 200/khác 409. |
| `POST /api/admin/posts/{post_id}/reject` | `PUT /api/v1/admin/posts/{post_id}/moderation` | Gộp moderation, body {"status":"rejected"}; terminal trùng 200/khác 409. |
| `POST /api/admin/reports/{report_id}/moderate` | `PUT /api/v1/admin/reports/{report_id}/moderation` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /api/admin/tags` | `POST /api/v1/admin/tags` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /api/admin/users/{user_id}/ban` | `PUT /api/v1/admin/users/{user_id}/ban` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /api/admin/users/{user_id}/unban` | `DELETE /api/v1/admin/users/{user_id}/ban` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /api/posts/` | `POST /api/v1/posts` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /api/posts/{post_id}/bookmark` | `DELETE /api/v1/posts/{post_id}/bookmarks/me`<br>`PUT /api/v1/posts/{post_id}/bookmarks/me` | Bỏ toggle; PUT đặt có, DELETE đặt không; retry idempotent. |
| `POST /api/posts/{post_id}/comments/` | `POST /api/v1/posts/{post_id}/comments` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /api/posts/{post_id}/comments/{comment_id}/report` | `POST /api/v1/posts/{post_id}/comments/{comment_id}/reports` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /api/posts/{post_id}/like` | `DELETE /api/v1/posts/{post_id}/likes/me`<br>`PUT /api/v1/posts/{post_id}/likes/me` | Bỏ toggle; PUT đặt có, DELETE đặt không; retry idempotent. |
| `POST /api/posts/{post_id}/report` | `POST /api/v1/posts/{post_id}/reports` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /api/posts/{post_id}/share` | `POST /api/v1/posts/{post_id}/shares` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /auth/complete-profile` | `PUT /api/v1/users/me/profile-completion` | Chuyển module/path và POST→PUT; authenticated, cho profile chưa hoàn thành. |
| `POST /auth/forgot-password` | `POST /api/v1/auth/forgot-password` | 202 queued Outbox, không trả token. |
| `POST /auth/login` | `POST /api/v1/auth/login` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /auth/logout` | `POST /api/v1/auth/logout` | Success không body 204 (trừ unban có representation). |
| `POST /auth/refresh` | `POST /api/v1/auth/refresh` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /auth/register` | `POST /api/v1/auth/register` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /auth/resend-verification` | `POST /api/v1/auth/resend-verification` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /auth/reset-password` | `POST /api/v1/auth/reset-password` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /auth/verify-email` | `POST /api/v1/auth/verify-email` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /follow/{user_id}` | `PUT /api/v1/users/{user_id}/followers/me` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `POST /upload/image` | `POST /api/v1/media/images` | Upload phải active/completed user; MIME+magic+5 MiB/6 MiB; 201; filesystem transitional. |
| `POST /users/me/notifications/{notification_id}/read` | `PUT /api/v1/notifications/{notification_id}/read` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `PUT /api/admin/tags/{tag_id}` | `PATCH /api/v1/admin/tags/{tag_id}` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `PUT /api/posts/{post_id}` | `PATCH /api/v1/posts/{post_id}` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |
| `PUT /users/me` | `PATCH /api/v1/users/me` | Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết. |

Operation mới `POST /api/v1/posts/{post_id}/views` thay side effect cũ của GET, không làm mất capability. Phép đếm: 58 + 2 do tách hai toggle + 1 do tách view − 1 do gộp approve/reject = **60 business**. Tính cả `GET /` và `GET /health` giữ nguyên: **60 tổng legacy → 62 tổng v1**; chỉ tính nghiệp vụ: **58 → 60**. Các capability legacy còn lại được giữ; thay đổi ownership/schema bảo vệ dữ liệu riêng tư là thay đổi có chủ ý, không alias.
