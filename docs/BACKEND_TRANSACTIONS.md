# Application Service, transaction và outbox

Router phân tích request, xác thực người gọi, gọi ca sử dụng (use case) và định
dạng response. `application.py` điều phối toàn bộ nghiệp vụ; `domain.py` quản lý
các quy tắc về trạng thái và quyền; `repository.py` quản lý truy vấn SQLAlchemy
và lưu dữ liệu. Các hàm trong `service.py` vẫn giữ tính tương thích tại những nơi
module khác đang sử dụng. Các thao tác đọc feed không commit transaction.

`app/db/uow.py` chịu trách nhiệm commit và rollback. Mỗi nghiệp vụ ghi dữ liệu
chạy trong `with UnitOfWork(db):`, sử dụng repository và chỉ commit một lần khi
kết thúc thành công. Nếu có lỗi, kể cả lỗi khi commit, toàn bộ thao tác sẽ được
rollback. Unit of Work sử dụng transaction hiện có của session vì bước xác thực
có thể đã mở transaction trước đó. Không cho phép lồng các Unit of Work; các thao
tác phối hợp phải dùng chung Unit of Work bên ngoài. Repository có thể gọi
`flush()` để lấy ID nhưng không được tự commit.

Nghiệp vụ chia sẻ bài viết lưu bản ghi chia sẻ, bài viết được chia sẻ, liên kết
tag và notification trong cùng một Unit of Work. Nghiệp vụ kiểm duyệt cũng gom
thay đổi trạng thái, nhật ký quản trị, tag và notification vào cùng transaction.
Notification được lưu trực tiếp trong database ứng dụng, đồng bộ và nguyên tử
với nghiệp vụ phát sinh: hoặc tất cả thay đổi được lưu, hoặc tất cả bị rollback.

Riêng luồng từ chối refresh token, session không hợp lệ được xóa và commit trong
một Unit of Work **trước khi** trả lỗi từ chối. Các lỗi khác vẫn rollback theo
quy tắc thông thường.

## Triển khai migration bổ sung schema trước

Baseline cố định vẫn là `20261119_01`. Revision `20261119_02` là migration thuộc
giai đoạn **expand**, chỉ bổ sung bảng `outbox_events` và index phục vụ xử lý sự
kiện. Chạy migration trong một bước triển khai riêng, sau đó triển khai API và
worker:

```sh
cd backend
python -m scripts.migrate upgrade head
python -m app
# Chạy trong tiến trình/container riêng, dùng chung image và database với API:
python -m scripts.outbox_worker
```

Worker phải sử dụng cùng cấu hình và database với API. Cấu hình `RESEND_API_KEY`
và `MAIL_FROM` cho địa chỉ gửi đã được xác minh trên Resend. Nếu thiếu cấu hình
nhà cung cấp, việc gửi sẽ thất bại và được thử lại; nội dung email không bị ghi
vào log hoặc âm thầm loại bỏ. API không gửi email qua mạng trong transaction.
Nghiệp vụ đặt lại mật khẩu lưu token và sự kiện outbox `email.send` cùng nhau.
Response chung của API được giữ nguyên; email thực tế được gửi bất đồng bộ.

Với Docker Compose, lệnh `docker compose --profile outbox up --build` bật worker
tùy chọn. Lệnh khởi động API mặc định vẫn là `python -m app`. Trên Render hoặc
môi trường khác, chạy tiến trình/container nền riêng bằng lệnh
`python -m scripts.outbox_worker`. Đợt refactor này chưa tạo worker trả phí hoặc
thay đổi cấu hình triển khai từ xa. Phải chạy migration trước khi khởi động cả
API và worker phiên bản mới.

## Gửi sự kiện và phục hồi khi có lỗi

Worker nhận quyền xử lý sự kiện bằng một lệnh cập nhật database có điều kiện,
rồi commit quyền xử lý trước khi gọi nhà cung cấp email. Nhiều worker chạy đồng
thời không thể cùng sở hữu một quyền xử lý còn hiệu lực. Quyền này có thời hạn
năm phút (lease), cho phép worker khác tiếp quản nếu worker trước bị dừng đột
ngột. Khi hoàn tất, hệ thống kiểm tra token của quyền xử lý để ngăn worker cũ
xác nhận nhầm sự kiện đã được tiếp quản. Request HTTP có thời gian chờ tối đa
20 giây. Khi nhận SIGTERM/SIGINT, worker ngừng lấy sự kiện mới và xử lý xong sự
kiện hiện tại trước khi thoát.

Nếu gửi thất bại, worker thử lại với khoảng chờ tăng theo cấp số nhân, tối đa
tám lần gửi. Sau đó, sự kiện chuyển sang trạng thái `failed` để người vận hành
kiểm tra. `last_error` chỉ lưu tên lớp ngoại lệ, không lưu response của nhà cung
cấp, token hoặc nội dung email. Khi xác nhận xử lý thành công, payload được xóa
vì có thể chứa liên kết đặt lại mật khẩu riêng tư. Cần giới hạn quyền truy cập
payload của các sự kiện đang chờ hoặc đã thất bại, đồng thời xóa sự kiện thất bại
không còn cần thiết theo chính sách lưu trữ của ứng dụng.

Cơ chế gửi theo nguyên tắc **at least once**: sự kiện có thể được gửi lại nếu
worker bị dừng sau khi nhà cung cấp đã chấp nhận email nhưng trước khi database
ghi nhận kết quả. UUID cố định của sự kiện được gửi qua header `Idempotency-Key`
cho Resend để hạn chế gửi trùng. Resend lưu khóa này trong 24 giờ, nên cơ chế này
không bảo đảm gửi đúng một lần trong mọi khoảng thời gian; xem
[tài liệu về idempotency của Resend](https://resend.com/docs/dashboard/emails/idempotency-keys).
Trước khi gửi lại payload email cũ, phải kiểm tra thời hạn token đặt lại mật khẩu
và lịch sử gửi. Lệnh `python -m scripts.outbox_worker --once` xử lý tối đa một
sự kiện rồi thoát.

Cần theo dõi thời gian chờ của sự kiện, các sự kiện `failed` và log của worker.
Khi worker ngừng chạy, sự kiện vẫn được lưu bền vững trong hàng đợi. HTTP response
thành công không đồng nghĩa email đã được gửi ngay. API không tự thay đổi schema
hoặc khởi động worker khi startup.

## Kiểm chứng

Chạy `python -m pytest -q`. Các bài kiểm tra transaction sử dụng database SQLite
riêng biệt và chủ động gây lỗi sau các bước flush, tạo notification, liên kết
tag, đưa sự kiện vào outbox và tại bước commit. Chúng cũng kiểm tra quyền sở hữu
dữ liệu, thời hạn quyền xử lý và cơ chế thử lại của outbox. Danh sách route công
khai được đối chiếu để bảo đảm tính tương thích API.

Lệnh `python -m scripts.verify_migrations` tạo một database SQL Server dùng riêng
cho kiểm thử, chạy và xác minh baseline, kiểm tra việc tiếp nhận schema có sẵn
và khóa migration, áp dụng migration outbox, đối chiếu metadata ORM, mô phỏng gửi
email và kiểm tra quy trình expand/backfill/contract. Sau đó, script chỉ xóa
database kiểm thử vừa tạo; không thay đổi database ứng dụng được cấu hình và
không gửi email thật.
