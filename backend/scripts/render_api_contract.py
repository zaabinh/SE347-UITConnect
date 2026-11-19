"""Render the single Vietnamese API reference from live OpenAPI and reviewed behavior.

Run from backend: python -m scripts.render_api_contract
This is a synchronized documentation renderer, not a second OpenAPI specification.
"""

import json
import re
from pathlib import Path

from scripts.check_api_contract import contract_digest, frozen_contract, validate_documentation, validate_implementation

ROOT = Path(__file__).resolve().parents[2]
MODELS = {}

# Explicit behavioral notes were reviewed against routers, application services and policies.
# name, module, behavior, operation-specific failures (shared auth/validation errors are added below).
OPERATIONS = {
    'auth_register': ('Đăng ký tài khoản', 'auth', 'Chuẩn hóa email/username về chữ thường, băm password và tạo tài khoản local Student active, is_verified=true trong Unit of Work. Email verification hiện tắt; không gửi email xác minh. POST lặp không idempotent.', '400 BAD_REQUEST: email/username đã tồn tại hoặc xung đột đăng ký.'),
    'auth_login': ('Đăng nhập', 'auth', 'identifier là email hoặc username, được trim/lowercase. Tạo AuthSession và cặp access/refresh token; ghi IP và User-Agent nếu có. POST lặp tạo session mới. Không bắt buộc hoàn thành profile để đăng nhập.', '404 NOT_FOUND: không có tài khoản hoặc đã deleted; 401 UNAUTHORIZED: sai password; 403 FORBIDDEN: bị banned.'),
    'auth_google_login': ('Bắt đầu Google OAuth', 'auth', '307 với Location đến Google, scope openid email profile, access_type=offline, prompt=consent. Không có JSON body. Giữ nguyên luồng OAuth hiện hành.', '500 INTERNAL_ERROR: Google OAuth chưa được cấu hình.'),
    'auth_google_callback': ('Nhận Google OAuth callback', 'auth', 'Đổi code với Google, lấy email, tạo user nếu chưa có và tạo session trong Unit of Work. 307 đến FRONTEND_URL/auth/callback với access_token, refresh_token, next, email, verified, profile_completed trong query như hành vi hiện tại; next là /feed hoặc /complete-profile. Code của provider không bảo đảm tái sử dụng.', '400 BAD_REQUEST: Google không trả email; 403 FORBIDDEN: tài khoản banned; 404 NOT_FOUND: tài khoản deleted; 500 INTERNAL_ERROR: cấu hình/provider lỗi.'),
    'auth_refresh': ('Làm mới access token', 'auth', 'Kiểm tra refresh token và AuthSession, trả access token mới cùng refresh token cũ (không rotation). Session không hợp lệ được xóa và commit trước khi trả lỗi. Access token có thể khác giữa các lần gọi.', '401 UNAUTHORIZED: session thiếu/hết hạn/token sai; 403 FORBIDDEN: user banned.'),
    'auth_logout': ('Đăng xuất session', 'auth', 'Xóa session theo refresh_token. Session đã mất vẫn thành công 204, không body. Không thu hồi ngay access JWT đã cấp; client xóa token cục bộ.', ''),
    'auth_verify_email': ('Xác minh email — hiện tắt', 'auth', 'Vẫn validate VerifyEmailRequest rồi trả message Email verification is temporarily disabled. Không đọc token, không cập nhật tài khoản, không gửi email.', ''),
    'auth_resend_verification': ('Gửi lại xác minh — hiện tắt', 'auth', 'Vẫn validate email rồi trả message Email verification is temporarily disabled. verification_token=null; không enqueue email.', ''),
    'auth_forgot_password': ('Yêu cầu đặt lại password', 'auth', '202 nghĩa là đã tiếp nhận, chưa bảo đảm email đã giao. Nếu tài khoản đủ điều kiện tồn tại, tạo reset token và email Outbox trong cùng Unit of Work; tài khoản không tồn tại/deleted vẫn trả cùng thông điệp. Không trả reset token cho client. POST lặp có thể tạo yêu cầu mới.', '403 FORBIDDEN: tài khoản banned theo chính sách hiện tại; thông điệp 202 chung chỉ áp dụng nhánh được chấp nhận/không tồn tại.'),
    'auth_reset_password': ('Đặt lại password', 'auth', 'Kiểm tra reset token chưa dùng/chưa hết hạn, băm password mới, đánh dấu token đã dùng và xóa mọi AuthSession của user trong cùng transaction. POST lặp với token đã dùng bị từ chối.', '400 BAD_REQUEST: reset token sai/hết hạn/đã dùng; 404 NOT_FOUND: user mất/deleted; 403 FORBIDDEN: user banned.'),
    'auth_me': ('Đọc định danh session hiện tại', 'auth', 'Chỉ đọc CurrentUserIdentityResponse: có email/provider/is_verified/profile_completed của chính user. Cho phép user chưa hoàn thành profile. Không có các bộ đếm của hồ sơ đầy đủ.', ''),
    'users_complete_profile': ('Hoàn thành profile', 'auth', 'Cho phép user đăng nhập chưa hoàn thành profile. Chuẩn hóa username/lowercase, cập nhật full_name; các chuỗi tùy chọn chỉ được gán khi có giá trị truthy và được trim. interest_tags được trim/lowercase/deduplicate; danh sách trống giữ giá trị cũ. Đây là hành vi completion hiện có, không dùng endpoint này để xóa trường; dùng PATCH users/me khi profile đã hoàn thành. Không có notification/session mới.', '400 BAD_REQUEST: username bị user khác sử dụng.'),
    'users_get_by_id': ('Đọc user công khai theo ID', 'auth/users', 'Chỉ đọc PublicUserSummary với đúng sáu trường công khai. Người gọi chỉ cần authenticated; user đích phải active.', '404 NOT_FOUND: user đích thiếu hoặc không active.'),
    'users_get_current': ('Đọc hồ sơ đầy đủ của mình', 'users', 'Chỉ đọc hồ sơ cá nhân cùng email, role, status, created_at và số followers/following/posts. is_current_user=true, is_following=false trong tình huống thông thường.', ''),
    'users_update_current': ('Cập nhật một phần hồ sơ của mình', 'users', 'Chỉ thay các trường thực sự xuất hiện. Trim chuỗi; chuỗi tùy chọn rỗng được lưu null; interest_tags trim/lowercase/deduplicate và [] xóa sở thích. full_name và interest_tags không nhận null. {} hoặc field lạ bị 422. Một transaction, không notification.', ''),
    'users_get_profile': ('Đọc hồ sơ theo username', 'users', 'Chỉ đọc public profile; không có email/provider/status. posts_count chỉ tính active với người xem thường; chủ hồ sơ/admin tính cả pending/rejected, loại deleted. Không tự thêm filter trạng thái user đích ngoài lookup username hiện hành.', '404 NOT_FOUND: username không tồn tại.'),
    'users_list_posts': ('Liệt kê bài của user', 'users', 'Mảng không phân trang; created_at DESC, id DESC. Loại deleted; chỉ chủ hồ sơ/admin thấy pending/rejected, người khác chỉ active. title có tiền tố trạng thái cho pending/rejected theo hiện trạng. Không có filter/query.', '404 NOT_FOUND: username không tồn tại.'),
    'users_list_comments': ('Liệt kê bình luận của user', 'users', 'Mảng không phân trang; created_at DESC, id DESC. Chỉ comment active và post chưa deleted; người xem thường chỉ thấy post active hoặc post do chính người xem sở hữu, admin thấy các trạng thái còn lại. Không có filter/query.', '404 NOT_FOUND: username không tồn tại.'),
    'users_list_bookmarks': ('Liệt kê bookmark của mình', 'users', 'Chỉ bookmark của user hiện tại, không nhận username của người khác. Mảng không phân trang; thời gian bookmark DESC, post.id DESC. Loại post deleted; post không active chỉ hiện cho chủ post hoặc admin.', ''),
    'users_follow': ('Thiết lập đang follow', 'users', 'PUT thiết lập membership của chính người gọi. Lặp trả 200 following=true; chỉ lần tạo membership mới gửi notification follow. Khóa cặp follower/target trong Unit of Work; xử lý duplicate insert do tranh chấp. User đích được tra theo ID, không áp thêm điều kiện active trong service hiện tại.', '400 BAD_REQUEST: tự follow; 404 NOT_FOUND: user đích không tồn tại.'),
    'users_unfollow': ('Thiết lập không follow', 'users', 'DELETE membership của chính người gọi; absent membership vẫn 204 (kể cả ID đích không tồn tại). Không body, không notification. Không cần đọc user đích. Idempotent.', ''),
    'posts_create': ('Tạo bài viết', 'posts', 'Trim title/content; chuẩn hóa tags. User thường tạo pending, tag chưa biết được giữ ở requested_new_tags để admin duyệt; admin tạo active và có thể tạo tag. Notification cho admin khi pending hoặc followers khi active, cùng transaction với bài. Trả Location: /api/v1/posts/{id}. POST lặp tạo bài mới.', ''),
    'posts_get_by_id': ('Đọc chi tiết bài viết', 'posts', 'GET chỉ đọc, không tăng views_count và không thêm PostView. Quyền hiển thị V ở mục 2 áp dụng.', '404 NOT_FOUND: bài thiếu/deleted; 403 FORBIDDEN: bài pending/rejected của người khác với user thường.'),
    'posts_record_view': ('Ghi nhận một lượt xem', 'posts', 'Sau khi kiểm tra quyền hiển thị V, thêm một PostView trong Unit of Work; 204 không body. Mỗi POST là một sự kiện mới, không deduplicate theo user và không idempotent. Client gọi riêng sau GET khi thực sự muốn ghi nhận lượt xem.', '404 NOT_FOUND: bài thiếu/deleted; 403 FORBIDDEN: không có quyền xem.'),
    'posts_update': ('Cập nhật một phần bài viết', 'posts', 'Chỉ tác giả được sửa, kể cả admin cũng không sửa bài người khác qua endpoint này. Omitted giữ nguyên, cover_image=null xóa ảnh; null của title/content/tags/status và {} bị 422. User thường sửa sẽ đưa bài về pending; status được gửi không trao quyền duyệt. Admin tác giả có thể đặt pending/active/rejected. Đồng bộ tags nếu có, trong cùng transaction. PUT moderation là luồng admin duyệt riêng.', '403 FORBIDDEN: không phải tác giả hoặc không có quyền hiển thị; 404 NOT_FOUND: thiếu/deleted.'),
    'posts_delete': ('Xóa mềm bài viết', 'posts', 'Tác giả hoặc admin đặt status=deleted. User thường không xóa bài đã có comment active; admin được phép và thông báo tác giả khi xóa bài người khác. Một transaction. Gọi lại khi đã deleted trả 404; không có body thành công.', '400 BAD_REQUEST: user thường xóa bài đã có comment active; 403 FORBIDDEN: không phải tác giả/admin; 404 NOT_FOUND: thiếu/deleted.'),
    'posts_like': ('Thiết lập đã like', 'posts', 'Quyền hiển thị V. PUT membership của chính user; gọi lại vẫn liked=true, không thêm hàng/notification. Lần tạo mới thông báo tác giả nếu khác người gọi. Khóa post trong Unit of Work.', '404 NOT_FOUND: bài thiếu/deleted; 403 FORBIDDEN: không có quyền xem.'),
    'posts_unlike': ('Thiết lập chưa like', 'posts', 'Quyền hiển thị V. Xóa membership của chính user; absent membership vẫn 204, không body/notification. Khóa post trong Unit of Work, idempotent với bài còn truy cập được.', '404 NOT_FOUND: bài thiếu/deleted; 403 FORBIDDEN: không có quyền xem.'),
    'posts_bookmark': ('Thiết lập đã bookmark', 'posts', 'Quyền hiển thị V. PUT membership riêng tư của chính user; lặp vẫn bookmarked=true, không thêm hàng; không notification. Khóa post trong Unit of Work.', '404 NOT_FOUND: bài thiếu/deleted; 403 FORBIDDEN: không có quyền xem.'),
    'posts_unbookmark': ('Thiết lập chưa bookmark', 'posts', 'Quyền hiển thị V. Xóa bookmark của chính user; absent membership vẫn 204. Khóa post trong Unit of Work; không body/notification, idempotent với bài còn truy cập được.', '404 NOT_FOUND: bài thiếu/deleted; 403 FORBIDDEN: không có quyền xem.'),
    'posts_share': ('Tạo bài chia sẻ', 'posts', 'Quyền hiển thị V. Body có thể bỏ hẳn hoặc null. Tạo PostShare và một bài mới có original_post_id, share_caption, nội dung/ảnh/tag từ nguồn; user thường pending, admin active. Notification cho tác giả nguồn và followers nếu bài mới active. Location trỏ bài chia sẻ mới. Hai POST giống nhau tạo hai bài khác nhau, không idempotent.', '404 NOT_FOUND: nguồn thiếu/deleted; 403 FORBIDDEN: không có quyền xem.'),
    'posts_create_report': ('Báo cáo bài viết', 'posts/moderation', 'Quyền hiển thị V. Tạo Report pending, trim details, thông báo admin và tác giả nếu khác người gọi. Report và notification cùng Unit of Work. Mỗi user chỉ một report cho cùng post theo kiểm tra hiện tại; không Idempotency-Key.', '409 CONFLICT: đã report bài này; 404 NOT_FOUND: thiếu/deleted; 403 FORBIDDEN: không có quyền xem.'),
    'comments_list': ('Đọc cây bình luận', 'comments', 'Quyền hiển thị V của post. Mảng gốc và replies đệ quy chỉ chứa comment active; mỗi nhóm anh em theo created_at ASC, id ASC. Không phân trang/filter; comment active có parent bị ẩn không tự được nâng thành gốc. GET không ghi dữ liệu.', '404 NOT_FOUND: post thiếu/deleted; 403 FORBIDDEN: không có quyền xem post.'),
    'comments_create': ('Tạo bình luận hoặc reply', 'comments', 'Quyền hiển thị V. parent_id=null/bỏ qua tạo gốc; parent_id có giá trị phải là comment active thuộc cùng post. Trim content sau validation minLength=1 (không có ràng buộc minLength sau trim). Thông báo tác giả post và tác giả parent nếu khác người gọi; hai thông báo có thể cùng một người. Một Unit of Work. POST lặp tạo comment mới. Chưa có sửa/xóa comment.', '404 NOT_FOUND: post/parent thiếu hoặc parent không active/khác post; 403 FORBIDDEN: không có quyền xem post.'),
    'comments_create_report': ('Báo cáo bình luận', 'comments/moderation', 'Post phải thỏa quyền hiển thị V, comment phải active và thuộc đúng post. Tạo Report có cả post_id/comment_id; thông báo admin và tác giả comment nếu khác người gọi trong cùng transaction. Không dùng một report của post khác.', '409 CONFLICT: user đã report comment; 404 NOT_FOUND: post/comment thiếu, comment ẩn/khác post; 403 FORBIDDEN: không có quyền xem post.'),
    'feed_list': ('Đọc feed và tìm kiếm', 'feed', 'Chỉ post active. search tìm substring title/content, không tìm username; tag được slugify rồi khớp chính xác Tag.slug. mode=following chỉ người đang follow (không tự thêm bài mình); for-you ưu tiên cá nhân hóa theo hành vi hiện tại. Offset pagination. mode=trending hoặc sort=trending ưu tiên nhánh trending bất kể mode còn lại (kể cả following). latest ở nhánh following theo created_at/id DESC; most-liked/most-commented theo số tương tác DESC rồi created_at/id DESC. Nhánh latest for-you lấy tối đa 200 ứng viên mới để xếp theo tag_overlap*4 + follow_bonus(3) + likes*2 + active_comments*2.5 + shares*1.5 + views*.2, tie-break post.id DESC. Feed trending lấy tối đa 300 ứng viên mới, score=(likes*4+active_comments*3+shares*5+views)*exp(-age_hours/72), score/id DESC. total phản ánh cửa sổ có thể phục vụ ở các nhánh 200/300, không phải toàn bộ kho bài.', ''),
    'recommendations_list_trending': ('Gợi ý bài xu hướng', 'feed', 'Chỉ post active trong hours, tag lọc substring tên tag (ILIKE). Tính điểm trên TOÀN BỘ tập đủ điều kiện rồi xếp score DESC, post.id DESC trước khi offset; total là số bài đủ điều kiện. Trọng số giữ nguyên like=4, comment=3, share=2, view=.5 và exponential time decay có sàn .1 (mục 8). trend_rank là vị trí toàn cục (page−1)*page_size+index. Không ghi view; empty/out-of-range trả items=[].', ''),
    'recommendations_list_trending_tags': ('Gợi ý tag xu hướng', 'feed', 'Chỉ post active trong hours. Mỗi post đóng góp like*4 + comment*3 + view vào mỗi tag (không tính share); tổng score DESC, tag.id DESC; giới hạn limit. Trả items và updated_at, không meta/page. Rỗng trả items=[].', ''),
    'recommendations_list_similar': ('Gợi ý bài tương tự', 'feed', 'Chỉ dùng nguồn active; nếu nguồn không tồn tại hoặc không active (kể cả pending của chính tác giả/admin), trả 200 items=[] thay vì 404/403. Không lộ dữ liệu nguồn ẩn. Content-based TF/cosine cho title/content và Jaccard cho tags, giữ trọng số title 20%, content 40%, tag 40%. Loại nguồn; chỉ candidate active; lọc min_similarity và xếp similarity DESC, post.id DESC, tối đa limit. meta.page=1, page_size=total=len(items), total_pages=1 nếu có kết quả, ngược lại 0. Không phải tổng trước limit; không ghi view.', ''),
    'recommendations_list_collaborative': ('Gợi ý cộng tác', 'feed', 'Chỉ post active trong days_back, loại bài mình đã like. Chọn tối đa 500 user ứng viên theo user.id ASC, lấy tối đa 20 người tương tự đạt min_similarity (tie-break user.id DESC). Giữ weights interest tags 25%, liked posts 35%, following 25%, commented posts 15%. Tập bài lấy post có ít nhất một like, không chỉ like của nhóm tương tự; score = tổng like của bài * (số user tương tự đã like / số user tương tự được chọn) * (0.7 nếu người gọi đã xem, ngược lại 1). Bài có score=0 vẫn có thể nằm trong tập kết quả. Xếp score/id DESC rồi offset. total là số candidate đã chấm; similar_user_count response hiện luôn 0 (chưa cung cấp thống kê thật). Không ghi dữ liệu.', ''),
    'recommendations_list_profile': ('Gợi ý theo hồ sơ', 'feed', 'Chỉ post active trong days_back, loại bài đã like; chấm theo profile: direct interest tags 40%, keywords major/career_goal/bio 30%, behavior tags 30%. Lọc min_score, score/post.id DESC trước offset. Không có candidate cap 200/300 của feed; total là số bài đạt lọc. Không ghi dữ liệu.', ''),
    'recommendations_get_profile_summary': ('Tóm tắt hồ sơ cho gợi ý', 'feed', 'Chỉ user hiện tại. profile_strength là số trường có giá trị trong interest_tags/major/academic_year/career_goal/bio chia 5. recommendations_count đếm post active chưa like, chưa áp min_score/days_back. profile_completeness có năm cờ has_interest_tags, has_major, has_academic_year, has_career_goal, has_bio. Không ghi dữ liệu.', ''),
    'recommendations_get_profile_analysis': ('Phân tích hồ sơ cho gợi ý', 'feed', 'Chỉ user hiện tại; cùng profile_summary như endpoint summary và recommendation_message dựa trên thiếu interest_tags/major/career_goal. Nội dung thông điệp là mô tả, không phải mã trạng thái ổn định. Không ghi dữ liệu.', ''),
    'tags_list': ('Danh mục tag cho người dùng', 'posts', 'Mảng TagResponse không phân trang, theo name ASC; không filter/query, không tự tạo tag.', ''),
    'notifications_list': ('Đọc thông báo của mình', 'notifications', 'Chỉ recipient user hiện tại. unread_only=true chỉ chưa đọc, false trả tất cả; created_at DESC, id DESC. Mảng không phân trang, không tự đánh dấu đã đọc. Đây là REST, không định nghĩa WebSocket event.', ''),
    'notifications_mark_read': ('Đánh dấu thông báo đã đọc', 'notifications', 'Chỉ recipient. Đặt is_read=true trong Unit of Work; PUT lặp giữ true, không thêm notification. Không có unread API.', '404 NOT_FOUND: notification thiếu hoặc thuộc recipient khác.'),
    'notifications_delete': ('Xóa thông báo đã đọc', 'notifications', 'Chỉ recipient và notification đã đọc. Xóa hàng trong Unit of Work; 204 không body. Gọi lại sau khi xóa trả 404.', '400 BAD_REQUEST: thông báo chưa đọc; 404 NOT_FOUND: thiếu hoặc thuộc người khác.'),
    'admin_list_users': ('Quản trị danh sách user', 'moderation', 'Offset page/page_size. search substring username/email/full_name, status_filter lọc lowercase status. sort_by là cột được chọn, sort_order ASC/DESC, cùng giá trị phá hòa user.id ASC. Trả AdminUserResponse có email, không password_hash. Không ghi dữ liệu.', ''),
    'admin_ban_user': ('Thiết lập user bị ban', 'moderation', 'Khóa user trong Unit of Work. Không ban chính mình/admin; deleted như không tồn tại. Lần đổi sang banned ghi audit log và notification account_status cùng transaction. Đã banned trả 200 không ghi audit/notification mới; không tự xóa session.', '400 BAD_REQUEST: tự ban hoặc ban admin; 404 NOT_FOUND: thiếu/deleted.'),
    'admin_unban_user': ('Thiết lập user active', 'moderation', 'Khóa user; deleted như không tồn tại. Lần đổi sang active ghi audit với query reason và notification account_status cùng transaction; đã active trả 200 không side effect mới. Có JSON response dù method DELETE.', '404 NOT_FOUND: user thiếu/deleted.'),
    'admin_list_reports': ('Quản trị danh sách report', 'moderation', 'Offset page/page_size; status_filter bằng status, reason so khớp chính xác. created_at DESC, id DESC. Không query sort tùy ý. Không ghi dữ liệu.', ''),
    'admin_moderate_report': ('Thiết lập quyết định report', 'moderation', 'Khóa report và post liên quan; action chỉ khác none khi status=resolved, resolved bắt buộc action cụ thể. Action phải đúng loại target. Có thể ẩn post (rejected), ẩn comment (hidden), ban tác giả; ghi audit và notification tác giả/reporter trong cùng transaction. Report đã rời pending: cùng status và action trả 200 không lặp side effect (notes khác không cập nhật); quyết định khác trả 409. pending→pending vẫn có thể ghi audit/notification; không quảng bá idempotency cho nhánh này.', '400 BAD_REQUEST: cặp status/action sai, action không đúng target, ban bản thân/admin; 404 NOT_FOUND: report/target/user thiếu; 409 REPORT_ALREADY_MODERATED: quyết định terminal khác.'),
    'admin_list_pending_posts': ('Liệt kê bài chờ duyệt', 'moderation', 'Chỉ status=pending; offset page/page_size; created_at DESC, id DESC. requested_new_tags là tag người viết đề nghị. Không ghi dữ liệu.', ''),
    'admin_moderate_post': ('Duyệt hoặc từ chối bài', 'moderation', 'Khóa post (và tags khi approve). Chỉ pending chuyển active/rejected; cùng trạng thái đích trả 200 không side effect; trạng thái terminal khác trả 409. active: tạo/liên kết requested_new_tags, xóa hàng đợi tag, audit approve, thông báo tác giả và followers; rejected: xóa requested_new_tags, audit reject, thông báo tác giả. Mọi thay đổi cùng Unit of Work.', '404 NOT_FOUND: thiếu/deleted; 409 POST_ALREADY_MODERATED: đã có quyết định khác.'),
    'admin_get_analytics': ('Đọc thống kê quản trị', 'moderation', 'Các số *_today là cửa sổ 24 giờ trượt, *_week là 7 ngày trượt tính theo UTC hiện tại (không phải ngày/tuần lịch). Users/comments/reports đếm theo created_at; posts chỉ active. pending_reports/pending_posts là tổng hiện tại. Chỉ đọc.', ''),
    'admin_list_tags': ('Quản trị danh mục tag', 'moderation', 'Mảng không phân trang, name ASC. Không filter/query. Chỉ đọc.', ''),
    'admin_create_tag': ('Tạo tag', 'moderation', 'Trim/lowercase name, sinh slug từ tên; khóa tags trong Unit of Work. Tên/slug đã có bị 400 theo chính sách hiện tại. POST lặp không idempotent. Không audit/notification riêng trong service tag.', '400 BAD_REQUEST: tag có tên/slug đã tồn tại.'),
    'admin_update_tag': ('Đổi tên tag', 'moderation', 'PATCH name bắt buộc vì đây là trường sửa duy nhất; trim/lowercase và sinh lại slug. Khóa tags trong Unit of Work. Không thêm audit/notification riêng.', '404 NOT_FOUND: tag thiếu; 409 CONFLICT: tên/slug trùng tag khác.'),
    'admin_delete_tag': ('Xóa tag', 'moderation', 'Khóa tags; xóa tag và liên kết PostTag theo cascade trong cùng Unit of Work, 204 không body. Gọi lại trả 404. Không thêm audit/notification riêng.', '404 NOT_FOUND: tag thiếu.'),
    'media_upload_image': ('Upload ảnh lên filesystem', 'media', 'Transitional v1: nhận multipart field file bắt buộc. Content-Type của file phải image/jpeg hoặc image/png và magic bytes phải khớp (JPEG FF D8 FF; PNG 89 50 4E 47 0D 0A 1A 0A). File tối đa 5 MiB (5,242,880 byte); toàn request tối đa 6 MiB (6,291,456 byte) kể cả multipart, có chặn cả body streaming. Lưu UUID.jpg/png dưới UPLOAD_DIR, trả URL PUBLIC_API_URL hoặc request base URL + /uploads/{filename}. Xóa file ghi dở nếu upload lỗi. POST lặp tạo file mới. Không transaction DB, không ownership reservation/attach/confirm/visibility lifecycle.', '400 BAD_REQUEST: MIME không hỗ trợ hoặc signature sai; 413 PAYLOAD_TOO_LARGE: file >5 MiB hoặc request >6 MiB; 500 INTERNAL_ERROR: không lưu được ảnh.'),
    'system_root': ('Thông tin ứng dụng', 'infrastructure', 'Chỉ đọc thông tin tĩnh; không kiểm tra kết nối DB. Không query/body/auth.', ''),
    'system_health': ('Kiểm tra liveness', 'infrastructure', 'Chỉ trả liveness tĩnh healthy; không phải readiness probe của DB/Outbox/R2. Không query/body/auth.', ''),
}

AUTH = {
    'public': 'Public: không yêu cầu Authorization.',
    'authenticated': 'Bearer access JWT hợp lệ; user tồn tại, không deleted/banned. Cho phép profile chưa hoàn thành; không yêu cầu role cụ thể.',
    'active_user': 'Bearer access JWT; user active, profile đã hoàn thành (policy hiện tại: username không rỗng sau trim). Không yêu cầu role cụ thể.',
    'admin': 'Bearer access JWT; user active, profile đã hoàn thành và role=admin (không phân biệt hoa thường).',
}

MEANING = {
    'id': 'Định danh của tài nguyên trong DTO này.', 'user_id': 'ID user sở hữu/được phân tích; trong notification là recipient.',
    'username': 'Tên đăng nhập/định danh hồ sơ; có thể chưa được đặt với tài khoản OAuth.',
    'email': 'Địa chỉ email của tài khoản; chỉ xuất hiện trong DTO riêng tư/admin.',
    'full_name': 'Tên hiển thị của user.', 'avatar_url': 'URL avatar do ứng dụng lưu; nullable để không có avatar.',
    'bio': 'Giới thiệu cá nhân.', 'major': 'Chuyên ngành học.', 'academic_year': 'Năm học/khóa học dạng chuỗi.',
    'career_goal': 'Mục tiêu nghề nghiệp.', 'interest_tags': 'Danh sách tên tag quan tâm.',
    'role': 'Vai trò user (ví dụ Student, admin); đây là chuỗi, không phải enum đóng trong schema.',
    'status': 'Trạng thái theo loại tài nguyên; xem bảng quy ước bên dưới.',
    'provider': 'Nguồn đăng nhập local/google theo dữ liệu tài khoản.', 'is_verified': 'Cờ xác minh hiện lưu; không đồng nghĩa middleware đang bắt buộc email verification.',
    'profile_completed': 'Kết quả policy hoàn thành profile, dùng để điều hướng client.',
    'followers_count': 'Số membership follow trỏ đến user.', 'following_count': 'Số membership user đang follow.',
    'posts_count': 'Số post hiển thị với người gọi, loại deleted.', 'is_following': 'Người gọi đang follow user đích.',
    'is_current_user': 'Hồ sơ thuộc chính người gọi.', 'created_at': 'Thời điểm tạo theo UTC ISO 8601 có hậu tố Z.',
    'updated_at': 'Thời điểm tạo kết quả tính toán theo UTC.', 'title': 'Tiêu đề bài hoặc thông báo tùy DTO.',
    'content': 'Nội dung bài/bình luận; service trim khi ghi.', 'cover_image': 'URL ảnh cover tùy chọn; không có cơ chế reservation/ownership media.',
    'tags': 'Danh sách tên tag gắn với bài.', 'requested_new_tags': 'Tên tag mới đang đề nghị duyệt, chưa phải tag đã công bố.',
    'original_post_id': 'ID post nguồn của bài chia sẻ; null với post thường.', 'share_caption': 'Lời dẫn của bài chia sẻ.',
    'caption': 'Lời dẫn khi tạo bài chia sẻ; tối đa 2000 ký tự.', 'author': 'PublicUserSummary; không chứa email/provider/status/is_verified/password_hash.',
    'likes_count': 'Số lượt like hiện tại.', 'comments_count': 'Số bình luận được thống kê theo thuật toán hiện tại; không bảo đảm đồng nhất với độ dài cây comment active.',
    'views_count': 'Số sự kiện PostView; chỉ POST views tạo sự kiện.', 'shares_count': 'Số sự kiện PostShare.',
    'trending_score': 'Điểm số nguyên hiển thị theo nhánh thống kê; không phải hot_score float của mọi thuật toán.',
    'is_liked': 'Membership like của người gọi.', 'is_bookmarked': 'Membership bookmark của người gọi.',
    'liked': 'Trạng thái mong muốn đã like=true sau PUT.', 'bookmarked': 'Trạng thái mong muốn bookmark=true sau PUT.',
    'following': 'Trạng thái mong muốn follow=true sau PUT.', 'post_id': 'ID post liên quan; SharePostResponse là bài chia sẻ mới.',
    'parent_id': 'ID comment cha cùng post, null là comment gốc.', 'replies': 'Danh sách CommentResponse con, đệ quy.',
    'post_title': 'Tiêu đề post liên quan đến bình luận.', 'comment_id': 'ID comment đích/liên quan.',
    'report_id': 'ID report liên quan.', 'reporter_id': 'ID user tạo report.', 'reason': 'Lý do report hoặc lý do ban/unban tùy request.',
    'details': 'Mô tả bổ sung cho report.', 'reviewed_by': 'ID admin xử lý report; null trước khi xử lý.',
    'reviewed_at': 'Thời điểm xử lý report UTC, null trước khi xử lý.', 'action': 'Hành động moderation; chỉ áp dụng khi resolved.',
    'notes': 'Ghi chú admin được lưu trong audit log; không xuất hiện trong ReportResponse.',
    'actor_id': 'ID user gây ra notification; null với sự kiện hệ thống/ẩn danh.',
    'type': 'Loại notification dạng chuỗi; trong ProblemDetails là URI định danh loại lỗi.',
    'message': 'Thông điệp cho người dùng; client không phân tích chuỗi để quyết định logic.', 'is_read': 'Notification đã được recipient đọc.',
    'items': 'Danh sách tài nguyên con theo thứ tự đã nêu ở endpoint.', 'meta': 'PaginationMeta của tập kết quả.',
    'page': 'Trang offset bắt đầu từ 1.', 'page_size': 'Kích thước trang; similar dùng số item thực trả, có thể 0.',
    'total': 'Tổng trong tập/cửa sổ có thể phục vụ theo endpoint.', 'total_pages': 'ceil(total/page_size) với collection thường; total=0 luôn là 0.',
    'post': 'PostResponse đầy đủ, tác giả dùng PublicUserSummary.', 'trend_rank': 'Xếp hạng toàn cục trong tập trending, bắt đầu 1.',
    'hot_score': 'Điểm xu hướng float có time decay.', 'trending_reason': 'Diễn giải vì sao bài đang trending.',
    'tag_name': 'Tên tag được xếp hạng.', 'post_count': 'Số post active đủ điều kiện chứa tag.', 'trend_score': 'Tổng điểm xu hướng của tag.',
    'similarity_score': 'Điểm tương đồng nội dung.', 'similarity_reason': 'Diễn giải tương đồng nội dung.',
    'cf_score': 'Điểm collaborative filtering.', 'cf_reason': 'Diễn giải gợi ý cộng tác.',
    'similar_user_count': 'Hiện implementation trả 0, chưa phải số user tương tự đo được.',
    'profile_score': 'Điểm phù hợp với profile.', 'recommendation_reason': 'Diễn giải gợi ý theo profile.',
    'profile_summary': 'UserProfileSummary của chính người gọi.', 'recommendation_message': 'Gợi ý hoàn thiện profile dạng thông điệp.',
    'profile_strength': 'Mức đầy đủ profile, từ 0 đến 1 theo năm tiêu chí.',
    'recommendations_count': 'Số bài active chưa được user like, trước khi lọc riêng của recommendation.',
    'profile_completeness': 'Object mở; hiện gồm has_interest_tags, has_major, has_academic_year, has_career_goal, has_bio (boolean).',
    'name': 'Tên tag; service trim/lowercase khi ghi.', 'slug': 'Slug ASCII sinh từ tên tag.',
    'password': 'Password thô chỉ trong request, được băm khi lưu; không có trong response.',
    'identifier': 'Email hoặc username dùng đăng nhập.', 'token': 'Token email verification/reset password theo endpoint.',
    'refresh_token': 'JWT refresh gắn AuthSession; chỉ gửi tới luồng auth thích hợp.',
    'access_token': 'JWT access dùng Authorization: Bearer.', 'token_type': 'Kiểu token, mặc định bearer.',
    'expires_in': 'Thời gian sống access token tính bằng giây, lấy từ cấu hình runtime.',
    'verification_token': 'Trường tùy chọn còn trong DTO; hiện null vì verification tắt.',
    'url': 'URL công khai của file đã lưu dưới /uploads.', 'file': 'File nhị phân multipart, JPEG/PNG.',
    'detail': 'Mô tả lỗi an toàn cho client.', 'instance': 'Path request tạo lỗi, không kèm query.',
    'code': 'Mã ứng dụng ổn định dùng cho logic client.', 'request_id': 'UUID do server tạo, cũng trả ở X-Request-ID.',
    'errors': 'Danh sách ValidationIssue khi 422; không chứa input/context nhạy cảm.',
    'loc': 'Vị trí trường sai gồm body/query/path và tên trường/chỉ số.', 'msg': 'Thông điệp đã khử input: Field required. hoặc Invalid value.',
    'version': 'Phiên bản thông tin ứng dụng.', 'docs': 'Đường dẫn Swagger UI.', 'openapi_schema': 'Đường dẫn OpenAPI máy đọc.',
    'users_today': 'Số user tạo trong 24 giờ gần nhất.', 'users_week': 'Số user tạo trong 7 ngày gần nhất.',
    'posts_today': 'Số post active tạo trong 24 giờ gần nhất.', 'posts_week': 'Số post active tạo trong 7 ngày gần nhất.',
    'comments_today': 'Số comment tạo trong 24 giờ gần nhất.', 'comments_week': 'Số comment tạo trong 7 ngày gần nhất.',
    'reports_today': 'Số report tạo trong 24 giờ gần nhất.', 'reports_week': 'Số report tạo trong 7 ngày gần nhất.',
    'pending_reports': 'Tổng report pending hiện tại.', 'pending_posts': 'Tổng post pending hiện tại.',
}

PARAM_MEANING = {
    'post_id': 'ID post, phải tồn tại và thỏa quyền hiển thị nếu endpoint yêu cầu.',
    'comment_id': 'ID comment phải thuộc post_id trên path.', 'user_id': 'ID user đích, không phải username.',
    'username': 'Username của profile đích; route by-username tránh xung đột với me/ID.',
    'notification_id': 'ID notification thuộc recipient hiện tại.', 'report_id': 'ID report cần quản trị.',
    'tag_id': 'ID tag cần quản trị.', 'code': 'Authorization code do Google gửi callback, bắt buộc.',
    'page': MEANING['page'], 'page_size': 'Số item mỗi trang offset.', 'search': 'Từ khóa; phạm vi tìm kiếm nêu trong hành vi endpoint.',
    'tag': 'Feed: slugify rồi khớp Tag.slug; recommendations/trending: substring tên tag ILIKE.', 'mode': 'Chế độ feed; xem ưu tiên nhánh trong hành vi.',
    'sort': 'Kiểu xếp thứ tự feed.', 'hours': 'Cửa sổ thời gian tính bằng GIỜ, không phải ngày.',
    'limit': 'Số kết quả tối đa, không phải page_size/cursor.', 'min_similarity': 'Ngưỡng điểm tương đồng tối thiểu.',
    'min_score': 'Ngưỡng điểm profile tối thiểu.', 'days_back': 'Cửa sổ tuổi post tính bằng ngày.',
    'unread_only': 'true để chỉ lấy notification chưa đọc.', 'reason': 'Lý do unban hoặc filter reason report chính xác tùy endpoint.',
    'status_filter': 'Trạng thái cần lọc theo tập giá trị cho phép.', 'sort_by': 'Cột sort quản trị user.',
    'sort_order': 'Chiều sort quản trị user; tie-break user.id ASC.',
}

SAMPLE_VALUES = {
    'username': 'uit_student', 'email': 'student@example.com', 'full_name': 'Nguyễn Minh An',
    'user_id': '11111111-1111-4111-8111-111111111111', 'actor_id': '22222222-2222-4222-8222-222222222222',
    'reporter_id': '11111111-1111-4111-8111-111111111111', 'reviewed_by': None,
    'avatar_url': None, 'bio': 'Sinh viên công nghệ thông tin', 'major': 'Software Engineering',
    'academic_year': '2026', 'career_goal': 'Backend developer', 'role': 'Student', 'provider': 'local',
    'title': 'Chia sẻ kinh nghiệm học FastAPI', 'content': 'Nội dung minh họa cho cộng đồng UIT.',
    'cover_image': None, 'tags': ['python'], 'interest_tags': ['python'], 'requested_new_tags': [],
    'password': 'ExamplePass123!', 'identifier': 'student@example.com', 'refresh_token': 'example-refresh-token-value',
    'access_token': 'example-access-jwt-value', 'token': 'example-reset-token-value', 'token_type': 'bearer',
    'expires_in': 1800, 'caption': 'Một bài viết hữu ích.', 'share_caption': None, 'original_post_id': None,
    'parent_id': None, 'replies': [], 'post_id': 42, 'comment_id': None, 'report_id': None,
    'created_at': '2026-11-19T12:00:00Z', 'updated_at': '2026-11-19T12:00:00Z', 'reviewed_at': None,
    'post_title': 'Chia sẻ kinh nghiệm học FastAPI', 'reason': 'spam', 'details': 'Nội dung có dấu hiệu spam.',
    'action': 'none', 'notes': None, 'name': 'python', 'slug': 'python', 'url': 'http://localhost:8000/uploads/33333333-3333-4333-8333-333333333333.png',
    'message': 'Thao tác thành công.', 'following': True, 'liked': True, 'bookmarked': True,
    'is_verified': True, 'profile_completed': True, 'is_current_user': True, 'is_following': False,
    'is_read': False, 'is_liked': False, 'is_bookmarked': False, 'page': 1, 'page_size': 10,
    'total': 1, 'total_pages': 1, 'trend_rank': 1, 'hot_score': 8.0, 'trending_reason': 'Có nhiều tương tác',
    'tag_name': 'python', 'post_count': 1, 'trend_score': 8.0, 'similarity_score': 0.8,
    'similarity_reason': 'Nội dung và tag tương đồng', 'cf_score': 0.6, 'cf_reason': 'Được người có sở thích tương tự quan tâm',
    'similar_user_count': 0, 'profile_score': 0.8, 'recommendation_reason': 'Phù hợp sở thích Python',
    'profile_strength': 1.0, 'recommendations_count': 1,
    'profile_completeness': {'has_interest_tags': True, 'has_major': True, 'has_academic_year': True, 'has_career_goal': True, 'has_bio': True},
    'recommendation_message': 'Profile đầy đủ để nhận gợi ý.', 'verification_token': None,
    'version': '1.0.0', 'docs': '/docs', 'openapi_schema': '/openapi.json', 'file': '<binary PNG bytes>',
    'loc': ['body', 'title'], 'msg': 'Invalid value.',
}


def type_name(value):
    if '$ref' in value:
        return value['$ref'].rsplit('/', 1)[-1]
    if 'anyOf' in value:
        return ' / '.join(type_name(part) for part in value['anyOf'])
    if value.get('type') == 'array':
        return type_name(value['items']) + '[]'
    return value.get('type', 'object') + (f" ({value['format']})" if 'format' in value else '')


def nullable(value):
    return value.get('type') == 'null' or any(nullable(part) for part in value.get('anyOf', []))


def constraints(value):
    rules = []
    for key in ('minLength', 'maxLength', 'minimum', 'maximum', 'minItems', 'maxItems', 'pattern', 'format', 'enum'):
        if key in value:
            rules.append(f'{key}={json.dumps(value[key], ensure_ascii=False)}')
    if 'default' in value:
        rules.append('mặc định=' + json.dumps(value['default'], ensure_ascii=False))
    for part in value.get('anyOf', []):
        nested = constraints(part)
        if nested != '—':
            rules.append(nested)
    return '; '.join(rules).replace('|', '\\|') or '—'


def example(value, schemas, field='', owner='', stack=()):
    if '$ref' in value:
        name = value['$ref'].rsplit('/', 1)[-1]
        return example(schemas[name], schemas, owner=name, stack=stack + (name,))
    if 'anyOf' in value:
        if field in SAMPLE_VALUES and SAMPLE_VALUES[field] is None and nullable(value):
            return None
        part = next(part for part in value['anyOf'] if part.get('type') != 'null')
        return example(part, schemas, field, owner, stack)
    if 'properties' in value:
        result = {key: example(definition, schemas, key, owner, stack) for key, definition in value['properties'].items()}
        if owner == 'ProblemDetails':
            return problem_example()
        if owner == 'ValidationIssue':
            result['type'] = 'string_too_short'
        if owner in {'PostResponse', 'CreatePostRequest', 'UpdatePostRequest'}:
            if owner == 'PostResponse':
                result['status'] = 'active'
        if owner == 'UpdatePostRequest':
            return {'title': 'Tiêu đề bài viết đã cập nhật', 'cover_image': None}
        if owner == 'UpdateProfileRequest':
            return {'full_name': 'Nguyễn Minh An', 'bio': None, 'interest_tags': ['python']}
        if owner == 'ModeratePostRequest':
            result['status'] = 'active'
        if owner in {'ModerateReportRequest', 'ReportResponse'}:
            result['status'] = 'pending'
        if owner == 'AdminPostModerationResponse':
            result['status'] = 'pending'
        if owner == 'SharePostResponse':
            result.update(post_id=43, original_post_id=42)
        if owner == 'NotificationResponse':
            result.update(type='post_like', title='Your post was liked', message='uit_student liked your post.')
        if owner == 'HealthResponse':
            result.update(status='healthy', message='Student Forum API is running')
        if owner == 'RootResponse':
            result['message'] = 'Welcome to Student Forum API'
        if owner == 'PaginationMeta':
            result.update(page=1, page_size=10, total=1, total_pages=1)
        if owner == 'SimilarPostListResponse':
            result['meta'].update(page_size=1)
        return result
    if field in SAMPLE_VALUES:
        return SAMPLE_VALUES[field]
    if value.get('enum'):
        return value['enum'][0]
    kind = value.get('type')
    if kind == 'array':
        if field == 'items':
            return [example(value['items'], schemas, stack=stack)]
        return []
    if kind == 'boolean':
        return False
    if kind in ('integer', 'number'):
        return 42 if field == 'id' else value.get('minimum', 0)
    if kind == 'object':
        return {}
    if kind == 'null':
        return None
    if field == 'id':
        return '11111111-1111-4111-8111-111111111111'
    if field == 'status':
        return 'active'
    return 'Giá trị minh họa'


def problem_example(status=422, code='VALIDATION_ERROR', path='/api/v1/posts', detail='Request validation failed.'):
    result = {'type': 'about:blank', 'title': {422: 'Unprocessable Entity', 409: 'Conflict', 401: 'Unauthorized', 404: 'Not Found'}.get(status, 'Bad Request'), 'status': status,
              'detail': detail, 'instance': path, 'code': code, 'request_id': '44444444-4444-4444-8444-444444444444'}
    if status == 422:
        result['errors'] = [{'loc': ['body', 'title'], 'msg': 'Invalid value.', 'type': 'string_too_short'}]
    return result


def block(value):
    return '```json\n' + json.dumps(value, ensure_ascii=False, indent=2) + '\n```\n'


def validate_example(value_schema, value):
    from pydantic import TypeAdapter
    if '$ref' in value_schema:
        TypeAdapter(MODELS[value_schema['$ref'].rsplit('/', 1)[-1]]).validate_python(value)
    elif 'anyOf' in value_schema:
        if value is not None:
            validate_example(next(part for part in value_schema['anyOf'] if part.get('type') != 'null'), value)
    elif value_schema.get('type') == 'array':
        for item in value:
            validate_example(value_schema['items'], item)


def meaning(name, field):
    if name == 'ProblemDetails' and field == 'title':
        return 'Tên HTTP status ngắn do server sinh; không phải tiêu đề post.'
    if name == 'ProblemDetails' and field == 'status':
        return 'HTTP status số, trùng response status.'
    if name == 'ProblemDetails' and field == 'type':
        return 'URI loại problem, hiện about:blank.'
    if name == 'ValidationIssue' and field == 'type':
        return 'Loại lỗi validation máy đọc, ví dụ missing/string_too_short.'
    if field == 'id':
        entity = 'user' if 'User' in name and 'Post' not in name and 'Comment' not in name else 'tài nguyên'
        return f'ID {entity}; user là string, post/comment/report/notification/tag là integer.'
    return MEANING[field]


def section_of(identifier):
    if identifier.startswith('system_'):
        return 1
    if identifier.startswith('auth_'):
        return 4
    if identifier.startswith('users_'):
        return 5
    if identifier.startswith('comments_'):
        return 7
    if identifier == 'tags_list' or identifier.startswith(('feed_', 'recommendations_')):
        return 8
    if identifier.startswith('posts_'):
        return 6
    if identifier.startswith('notifications_'):
        return 9
    if identifier.startswith('admin_'):
        return 10
    return 11


def render_endpoint(item, operation, schema):
    identifier = item['operation_id']
    name, module, behavior, failures = OPERATIONS[identifier]
    method, path, success = item['method'], item['path'], item['status']
    parts = [f'### `{method} {path}` — {name}\n',
             f'**Định danh:** operation_id `{identifier}`; module `{module}`. {name}.\n',
             f'**Xác thực và quyền:** {AUTH[item["security"]]} Quyền sở hữu/đối tượng cụ thể được nêu trong hành vi dưới đây.\n',
             '**Request:** `Accept: application/json` khi nhận JSON. ' + ('`Authorization: Bearer <access_token>` bắt buộc. ' if item['security'] != 'public' else '') +
             ('`Content-Type: multipart/form-data; boundary=...`.' if item['request'] == 'multipart:file' else '`Content-Type: application/json` nếu có body JSON.' if item['request'] else 'Không có request body.') + '\n']
    if identifier in {'auth_login', 'auth_google_callback'}:
        parts.append('Header `User-Agent` tùy chọn và IP từ request được ghi vào AuthSession; không cần client tự gửi IP trong JSON.\n')
    params = operation.get('parameters', [])
    if params:
        parts += ['| Vị trí | Trường | Kiểu | Bắt buộc | Ràng buộc / mặc định | Ý nghĩa |\n|---|---|---|---|---|---|\n']
        for param in params:
            parts.append(f'| {param["in"]} | `{param["name"]}` | `{type_name(param["schema"])}` | {"Có" if param.get("required") else "Không"} | {constraints(param["schema"])} | {PARAM_MEANING[param["name"]]} |\n')
        parts.append('\n')
    else:
        parts.append('Không có path/query parameter.\n')
    request = operation.get('requestBody')
    if request:
        content_type, content = next(iter(request['content'].items()))
        body_schema = content['schema']
        parts.append(f'Body {"bắt buộc" if request.get("required") else "không bắt buộc"}: `{type_name(body_schema)}`; toàn bộ field/type/nullability/validation ở mục 12.\n')
        if content_type == 'multipart/form-data':
            parts.append('Ví dụ request (binary, không phải JSON):\n\n```http\nPOST /api/v1/media/images HTTP/1.1\nAuthorization: Bearer <access_token>\nContent-Type: multipart/form-data; boundary=UITBoundary\n\n--UITBoundary\nContent-Disposition: form-data; name="file"; filename="example.png"\nContent-Type: image/png\n\n<binary PNG bytes>\n--UITBoundary--\n```\n')
        else:
            request_sample = example(body_schema, schema['components']['schemas'])
            if identifier == 'admin_moderate_report':
                request_sample = {'status': 'resolved', 'action': 'hide_post', 'notes': 'Đã xác nhận nội dung vi phạm.'}
            validate_example(body_schema, request_sample)
            parts.append('Ví dụ JSON request:\n\n' + block(request_sample))
    else:
        concrete = path
        for param in params:
            if param['in'] == 'path':
                concrete = concrete.replace('{' + param['name'] + '}', {'username': 'uit_student', 'user_id': '11111111-1111-4111-8111-111111111111'}.get(param['name'], '42'))
        query = '&'.join(param['name'] + '=' + str(param['schema'].get('default', 'example-google-code')).lower() for param in params if param['in'] == 'query' and (param.get('required') or param['schema'].get('default') is not None))
        parts.append(f'Ví dụ request: `{method} {concrete}{"?" + query if query else ""}`; body không gửi.\n')
    response = operation['responses'][str(success)]
    if item['response']:
        response_schema = response['content']['application/json']['schema']
        sample = example(response_schema, schema['components']['schemas'])
        if identifier == 'posts_create':
            sample['status'] = 'pending'
        if identifier == 'auth_register':
            sample['message'] = 'Registration successful. You can now log in.'
        if identifier in {'auth_verify_email', 'auth_resend_verification'}:
            sample['message'] = 'Email verification is temporarily disabled.'
        if identifier == 'auth_forgot_password':
            sample['message'] = 'If the email exists, a password reset email has been queued.'
        if identifier == 'auth_reset_password':
            sample['message'] = 'Password has been reset successfully.'
        if identifier == 'admin_ban_user':
            sample['status'] = 'banned'
        if identifier == 'admin_moderate_post':
            sample['status'] = 'active'
        if identifier == 'admin_moderate_report':
            sample.update(status='resolved', reviewed_by='22222222-2222-4222-8222-222222222222', reviewed_at='2026-11-19T12:00:00Z')
        if identifier == 'comments_create_report':
            sample['comment_id'] = 42
        if identifier == 'notifications_mark_read':
            sample['is_read'] = True
        if identifier == 'users_follow':
            sample['message'] = 'Followed user successfully.'
        if identifier == 'posts_update':
            sample.update(title='Tiêu đề bài viết đã cập nhật', status='pending')
        if identifier == 'users_update_current':
            sample['bio'] = None
        validate_example(response_schema, sample)
        parts.append(f'**Response:** `{success}`, `application/json`, `{item["response"]}`; mỗi field được định nghĩa ở mục 12. Mọi response có `X-Request-ID` do server tạo.\n\n' + block(sample))
    elif success == 307:
        parts.append('**Response:** `307 Temporary Redirect`, không có DTO/body JSON; `Location` chứa URL đích được mô tả trong hành vi. Browser theo redirect; không gọi axios với kỳ vọng JSON. `X-Request-ID` có trên response.\n')
        destination = ('https://accounts.google.com/o/oauth2/v2/auth?client_id=example-client&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fv1%2Fauth%2Fgoogle%2Fcallback&response_type=code&scope=openid+email+profile&access_type=offline&prompt=consent'
                       if identifier == 'auth_google_login' else 'http://localhost:3000/auth/callback?access_token=example-access-jwt-value&refresh_token=example-refresh-token-value&next=%2Ffeed&email=student%40example.com&verified=true&profile_completed=true')
        parts.append('Ví dụ response (giá trị URL/token minh họa):\n\n```http\nHTTP/1.1 307 Temporary Redirect\nLocation: ' + destination + '\nX-Request-ID: 44444444-4444-4444-8444-444444444444\n```\n')
    else:
        parts.append(f'**Response:** `{success} No Content`, body rỗng, không gửi JSON `null`/`{{}}`; `X-Request-ID` có trên response.\n')
    shared_errors = '422 VALIDATION_ERROR khi path/query/body không hợp lệ; 500 INTERNAL_ERROR khi có lỗi không dự kiến.' if params or request else '500 INTERNAL_ERROR khi có lỗi không dự kiến.'
    if item['security'] != 'public':
        shared_errors = '401 UNAUTHORIZED khi thiếu/sai/hết hạn access token; 404 NOT_FOUND khi user của session đã deleted; 403 FORBIDDEN khi user banned' + ('/inactive/chưa hoàn thành profile' if item['security'] in ('active_user', 'admin') else '') + ('/không phải admin' if item['security'] == 'admin' else '') + '. ' + shared_errors
    if item['security'] == 'admin' or method in ('POST', 'PUT', 'PATCH', 'DELETE') and module != 'media':
        shared_errors += ' 409 CONCURRENT_MODIFICATION nếu không lấy được khóa aggregate sau 10 giây; retry theo ngữ nghĩa thao tác.' if identifier not in ('auth_verify_email', 'auth_resend_verification', 'auth_logout', 'auth_login', 'auth_register', 'auth_forgot_password', 'auth_refresh', 'auth_reset_password', 'users_update_current', 'users_complete_profile', 'notifications_mark_read', 'notifications_delete') and not identifier.startswith('admin_list') and identifier != 'admin_get_analytics' else ''
    parts.append('**Lỗi:** ' + shared_errors + (' ' + failures if failures else '') + ' Dùng `ProblemDetails` và mẫu mục 13; mã/điều kiện ở đây bổ sung cho lỗi validation/xác thực chung. Các status dự phòng khai báo OpenAPI không có nghĩa mọi nhánh đều phát sinh chúng.\n')
    parts.append('**Hành vi, side effect và retry:** ' + behavior + '\n')
    return '\n'.join(parts)


def render(schema):
    frozen = frozen_contract()
    endpoints = frozen['endpoints'] + [
        {'method': 'GET', 'path': '/', 'operation_id': 'system_root', 'request': None, 'response': 'RootResponse', 'status': 200, 'security': 'public'},
        {'method': 'GET', 'path': '/health', 'operation_id': 'system_health', 'request': None, 'response': 'HealthResponse', 'status': 200, 'security': 'public'},
    ]
    assert set(OPERATIONS) == {item['operation_id'] for item in endpoints}
    schemas = schema['components']['schemas']
    for name, definition in schemas.items():
        for field in definition.get('properties', {}):
            assert field in MEANING, (name, field)
    headings = {
        1: 'Tổng quan (Overview)', 2: 'Tiêu chuẩn thiết kế API (API Design Standards)', 3: 'Tóm tắt endpoint (API Endpoint Summary)',
        4: 'Hợp đồng API xác thực (Authentication API Contracts)', 5: 'Hợp đồng API user và hồ sơ (Users & Profiles API Contracts)',
        6: 'Hợp đồng API bài viết và tương tác (Posts & Interactions API Contracts)', 7: 'Hợp đồng API bình luận (Comments API Contracts)',
        8: 'Hợp đồng API feed, tìm kiếm và gợi ý (Feed, Search & Recommendations API Contracts)', 9: 'Hợp đồng API thông báo (Notifications API Contracts)',
        10: 'Hợp đồng API quản trị và kiểm duyệt (Admin & Moderation API Contracts)', 11: 'Hợp đồng API media (Media API Contracts)', 12: 'DTO dùng chung và kiểu dữ liệu (Shared DTOs and Data Types)',
        13: 'Mã lỗi (Error Codes)', 14: 'Ma trận xác thực và phân quyền (Authentication and Authorization Matrix)',
        15: 'Chính sách tương thích và phiên bản API (API Compatibility and Versioning Policy)', 16: 'Kiểm chứng hợp đồng API (API Contract Verification)', 17: 'Ánh xạ endpoint legacy sang v1 (Legacy-to-v1 Endpoint Mapping)',
    }
    out = ['# UITConnect V2 — REST API Contract v1\n', f'<!-- OPENAPI_CONTRACT_SHA256: {contract_digest(schema)} -->\n',
           '> Tài liệu REST API có thẩm quyền duy nhất, viết theo router đã đăng ký, DTO và application/domain service. OpenAPI 3.1 được sinh từ ứng dụng tại `/openapi.json`; không có bản OpenAPI viết tay cạnh tranh. Giá trị ID/token trong ví dụ chỉ minh họa, không phải credential dùng được.\n']
    for number, title in headings.items():
        out.append(f'## {number}. {title}\n')
        if number == 1:
            out.append('UITConnect V2 dùng Modular Monolith: FastAPI/Pydantic v2 → application service → domain/repository → SQLAlchemy/SQL Server, Unit of Work và Transactional Outbox. Central router chỉ ghép module; router không sở hữu commit. Unified entrypoint vẫn là `python -m app`.\n\nBase URL local: `http://localhost:8000`; API nghiệp vụ: `{BASE_URL}/api/v1`. Frontend dùng cấu hình API origin tương ứng. Có **60 endpoint nghiệp vụ**, **62 REST operations** nếu tính `GET /` và `GET /health`. Swagger `/docs`, ReDoc `/redoc`, OpenAPI `/openapi.json` và static `/uploads/{filename}` là hạ tầng do framework phục vụ, không được tính thành operation REST trong bảng OpenAPI. Không có alias endpoint cũ hoặc route business ngoài `/api/v1`.\n\nRequest/response thường là `application/json`; upload dùng `multipart/form-data`; lỗi là `application/problem+json`; redirect OAuth là 307; 204 không có body. Bearer access JWT được gửi qua `Authorization`; refresh token trong JSON chỉ dùng cho refresh/logout. Không đổi kiến trúc JWT/session/OAuth trong đợt chuẩn hóa này.\n\nHai endpoint hạ tầng cũng có contract dưới đây.\n')
        if number == 2:
            out.append('Paths chữ thường, plural resource, kebab-case, không trailing slash. Method/path sai không tự chuyển sang alias v1; trailing slash không thuộc hợp đồng. `operation_id` duy nhất, khai báo rõ theo `{domain}_{operation}`. GET chỉ đọc; POST tạo tài nguyên/sự kiện; PUT đặt trạng thái đích; PATCH sửa một phần; DELETE bỏ tài nguyên/membership.\n\nSuccess: 200 đọc/cập nhật có representation, 201 tạo, 202 đã tiếp nhận async, 204 không body; OAuth 307. Error chuẩn: 400 quy tắc nghiệp vụ, 401 xác thực, 403 quyền, 404 thiếu, 409 xung đột, 413 upload lớn, 422 validation, 429 bị giới hạn nếu tầng triển khai áp dụng, 500 lỗi nội bộ. API hiện chưa có rate limiter ứng dụng; không hứa quota/Retry-After hoặc tự phát sinh 429. 405 cho method không được hỗ trợ.\n\n**Quyền hiển thị V của post:** deleted/không tồn tại → 404; active → được đọc/tương tác bởi active user; pending/rejected → chỉ tác giả hoặc admin, người khác 403. Kiểm tra này cũng áp dụng views/like/bookmark/share/report/comment. Similar chỉ lấy nguồn active và trả rỗng nếu không active (mục 8). Quyền sửa post vẫn chỉ tác giả; quyền xóa tác giả/admin và giới hạn comment ở mục 6.\n\n**PATCH:** omitted giữ nguyên; explicit null chỉ cho trường nullable về nghiệp vụ (UpdatePostRequest chỉ cover_image; UpdateProfileRequest các chuỗi tùy chọn, không full_name/interest_tags). Empty patch và field lạ bị 422. OpenAPI biểu diễn các field omittable độc lập với nullable; field không nullable có thể bỏ qua nhưng không thể gửi null. AuthRequest cũng extra=forbid. Các request khác giữ extra policy Pydantic hiện tại (ignore nếu không khai báo forbid); không hứa reject field lạ ở mọi POST.\n\n**Pagination:** offset `(page−1)*page_size`, không cursor. Meta có page/page_size/total/total_pages; total=0 → total_pages=0. Trang vượt cuối → items=[] và meta.total giữ tổng đúng của tập/cửa sổ; invalid page/page_size → 422, không clamp request. Feed/recommendations thường page=1/page_size=10, max 50; admin page=1/page_size=20, max 100. Mảng/tree cũ tiếp tục là mảng/tree, không bọc meta. Các cap ứng viên được ghi rõ từng endpoint; dữ liệu mới/tương tác có thể làm thứ hạng đổi giữa hai request, không có snapshot pagination. Tie-break ID bảo đảm thứ tự khi điểm/cột chính bằng nhau.\n\n**Ngày giờ:** `UtcDateTime` là datetime ISO 8601 UTC, ví dụ `2026-11-19T12:00:00Z`; SQL datetime naive được hiểu là UTC. ID user là string, các ID post/comment/tag/report/notification là integer, không ngầm hứa path integer phải >0 (hiện chỉ ràng buộc kiểu). Query là scalar, không có filter/sort tùy ý ngoài danh sách từng endpoint.\n\n**Idempotency/concurrency:** PUT/DELETE like/bookmark/follow đặt membership đích; lặp không nhân notification. Terminal moderation trùng quyết định không lặp audit/notification; khác quyết định 409. POST tạo bài/share/comment/view/upload không có Idempotency-Key; caller không tự retry mù sau timeout. SQL Server UnitOfWork dùng transaction-owned `sp_getapplock` theo aggregate, chờ 10 giây; thất bại trả 409 CONCURRENT_MODIFICATION. Không có migration schema mới chỉ để hỗ trợ API v1. DB write, audit/notification và outbox tương ứng chia sẻ transaction; rollback khi lỗi. Outbox worker giao email sau commit, không bảo đảm email đã được nhận khi response về.\n\n**Headers:** server tạo UUID mới cho mỗi HTTP request ở `X-Request-ID`, không tin/copy ID do client cung cấp. CORS expose X-Request-ID và Location. 401 thêm `WWW-Authenticate: Bearer`. Create/share post trả Location; không hứa Location cho các POST khác.\n')
        if number == 3:
            out.append('| Method | Endpoint | Description | Authentication | Request DTO | Response DTO | Status |\n|---|---|---|---|---|---|---|\n')
            for item in sorted(endpoints, key=lambda item: (item['path'], item['method'])):
                request = item['request'] or 'Không có'
                response = item['response'] or ('Redirect + Location' if item['status'] == 307 else 'Không body')
                out.append(f'| `{item["method"]}` | `{item["path"]}` | {OPERATIONS[item["operation_id"]][0]} | {item["security"]} | `{request}` | `{response}` | {item["status"]} |\n')
            out.append('\nNhãn auth trong bảng được định nghĩa chính xác ở mục 14; public DTO không có nghĩa endpoint không cần đăng nhập. Chi tiết mỗi operation nằm ở mục 1, 4–11.\n')
        if number == 4:
            out.append('Email verification hiện **tắt**: register tạo is_verified=true; verify/resend chỉ validate request rồi trả thông điệp tạm tắt. `require_active_verified_user` là tên helper lịch sử: hiện thực kiểm tra active + profile completed, không kiểm tra is_verified. Không quảng bá các token verification trong ví dụ thành chức năng có sẵn. Profile completion chuyển sang mục Users tại `PUT /api/v1/users/me/profile-completion`.\n\nGoogle callback mặc định mới là `http://localhost:8000/api/v1/auth/google/callback` (hoặc origin công khai tương ứng). Operator phải cập nhật `GOOGLE_REDIRECT_URI` và Authorized redirect URI của Google Cloud cùng lúc deploy. Google redirect giữ query token như trước; đây là giới hạn bảo mật hiện hữu của luồng, không phải OAuth redesign. Không có state/PKCE hay cookie-session mới được cam kết ở v1.\n')
        if number == 5:
            out.append('`GET /api/v1/auth/me` trả định danh auth (`CurrentUserIdentityResponse`); `GET /api/v1/users/me` trả hồ sơ cùng counters (`CurrentUserProfileResponse`). Hai DTO khác nhau có chủ ý. Profile public và summary không để lộ email/provider/status/is_verified/password_hash. Bookmarks chỉ đọc của mình; không có API liệt kê followers/following hoặc đổi username qua PATCH thông thường.\n')
        if number == 7:
            out.append('Reply dùng CreateCommentRequest.parent_id trên chính endpoint tạo comment. Chưa triển khai edit/delete comment; không có route giả cho các chức năng này.\n')
        if number == 8:
            out.append('Search hiện là query `search` của feed, không có resource `/api/v1/search` độc lập. Tag thường và tag trending nằm cùng phần khám phá. Điểm không phải confidence xác suất, các mô tả range trong tên/description không thêm validation ngoài bảng DTO.\n\nRecommendation trending giữ công thức `likes*4 + comments*3 + shares*2 + views*.5`, nhân `clamp(exp(-age_hours/24), .1, 1)` (tuổi âm dùng decay=1). Feed trending dùng công thức riêng `likes*4 + active_comments*3 + shares*5 + views` nhân `exp(-max(age_hours,0)/72)`; tag trending dùng likes*4 + comments*3 + views, không share/time decay. Không hợp nhất các thuật toán khác nhau dưới cùng một công thức. Các lý do gợi ý là thông điệp có thể thay đổi, không dùng làm code nghiệp vụ.\n')
        if number == 9:
            out.append('Recipient ownership được kiểm tra ở server. Notification của người khác được xem như không tồn tại (404). REST dưới đây không định nghĩa giao thức WebSocket; không có mark-all-read/unread hay phân trang giả.\n')
        if number == 10:
            out.append('Toàn bộ operation ở đây yêu cầu role admin và active/completed profile. Ban/unban và moderation dùng application/domain policy, audit/notification trong cùng Unit of Work khi có thay đổi. Tags không tự phát sinh audit log nếu service chưa triển khai.\n')
        if number == 11:
            out.append('**Đã triển khai:** chỉ upload filesystem bên dưới. Static `/uploads/{filename}` hiện công khai; bearer bảo vệ bước upload, không bảo vệ URL ảnh đã trả. Không có media ownership, reservation, attach-confirm, lifecycle cleanup hoặc kiểm tra quyền truy cập từng file. File không được đính kèm post tự động; client truyền URL vào cover_image/avatar_url theo DTO. Không có bảo đảm persistence trên hosting có filesystem tạm; cần cấu hình UPLOAD_DIR/persistent storage theo triển khai thực tế.\n\n**Planned — Not Implemented:** Cloudflare R2 là storage được chọn cho tương lai. Các khả năng create upload intent → direct upload qua presigned URL → confirm/verify → attach to post → visibility/lifecycle chưa có router, DTO hay endpoint hoạt động. Không cấp path/method giả và không đưa vào bảng endpoint triển khai. Không gọi upload v1 là R2/presigned upload.\n')
        if number in (1, 4, 5, 6, 7, 8, 9, 10, 11):
            for item in endpoints:
                if section_of(item['operation_id']) == number:
                    out.append(render_endpoint(item, schema['paths'][item['path']][item['method'].lower()], schema))
        if number == 12:
            out.append('Bảng sau được sinh từ components.schemas của OpenAPI. **Bắt buộc** nghĩa là key nằm trong required của JSON Schema, độc lập với **Nullable**. Trường response có default vẫn thường xuất hiện vì router không exclude_defaults; các ví dụ thể hiện đủ representation. `—` là không có ràng buộc bổ sung công bố ở schema, không tự suy ra max length từ cột DB. Trường response status/role là string trừ khi có enum/pattern rõ ràng.\n\nQuy ước status: user active/banned/deleted; post pending/active/rejected/deleted (post response nullable theo DTO lịch sử); comment active/hidden; report pending/reviewed/dismissed/resolved. Các trường đếm/scores là kiểu hiện có trong schema, không tự thêm minimum/maximum nếu DTO chưa khai báo. Các field refs liên kết tới định nghĩa DTO ngay trong phần này.\n\n`UtcDateTime` là kiểu Python dùng chung, xuất thành `string (date-time)` trong OpenAPI; nullable datetime vẫn null khi chưa có sự kiện. `PublicUserSummary` chỉ có id, username, full_name, avatar_url, bio, role.\n')
            for name, definition in sorted(schemas.items()):
                out.append(f'### `{name}`\n')
                if name == 'UpdatePostRequest':
                    out.append('Ràng buộc ngoài JSON Schema: ít nhất một key. Chỉ cover_image nullable; title/content/tags/status omittable nhưng không nhận explicit null. Extra field bị từ chối.\n')
                if name == 'UpdateProfileRequest':
                    out.append('Ràng buộc ngoài JSON Schema: ít nhất một key; full_name/interest_tags không nullable; extra field bị từ chối.\n')
                if definition.get('additionalProperties') is False:
                    out.append('`additionalProperties=false`: không chấp nhận field lạ.\n')
                out.append('| Field | Kiểu | Bắt buộc | Nullable | Ràng buộc / mặc định | Ý nghĩa |\n|---|---|---|---|---|---|\n')
                for field, field_schema in definition.get('properties', {}).items():
                    constraint = constraints(field_schema)
                    if name == 'UpdatePostRequest' and field != 'cover_image':
                        constraint += '; explicit null → 422'
                    out.append(f'| `{field}` | `{type_name(field_schema)}` | {"Có" if field in definition.get("required", []) else "Không"} | {"Có" if nullable(field_schema) else "Không"} | {constraint} | {meaning(name, field)} |\n')
                out.append('\n')
        if number == 13:
            out.append('Tất cả lỗi HTTP được handler chuẩn hóa về RFC 9457 `application/problem+json`. type/title/status luôn có; implementation hiện luôn thêm detail/instance/code/request_id; errors chỉ có khi validation. Lỗi >=500 chỉ trả `Internal server error.`; stack trace/SQL/credential chỉ ở log server, không trong payload. Validation bỏ input/context và chỉ trả vị trí, loại, thông điệp khử nhạy cảm.\n\n| Code | HTTP | Điều kiện |\n|---|---|---|\n| `BAD_REQUEST` | 400 | Quy tắc nghiệp vụ không hợp lệ: duplicate register/tag create, reset token sai, tự follow/ban, xóa bài có comment, xóa notification chưa đọc, cặp status/action moderation sai, MIME/signature ảnh sai. |\n| `UNAUTHORIZED` | 401 | Thiếu/sai/hết hạn JWT, sai password, refresh session/token sai; kèm WWW-Authenticate: Bearer. |\n| `FORBIDDEN` | 403 | Banned/inactive, chưa hoàn thành profile, thiếu role/ownership/visibility. |\n| `NOT_FOUND` | 404 | Resource thiếu/deleted, notification không thuộc recipient, parent/comment sai post; login với tài khoản thiếu hiện cũng dùng 404. |\n| `CONFLICT` | 409 | Report trùng, update tag trùng hoặc xung đột nghiệp vụ không có code riêng. |\n| `CONCURRENT_MODIFICATION` | 409 | Không lấy được SQL Server aggregate lock trong thời gian chờ; cân nhắc retry theo tính idempotent. |\n| `POST_ALREADY_MODERATED` | 409 | Post đã có trạng thái terminal khác quyết định yêu cầu. |\n| `REPORT_ALREADY_MODERATED` | 409 | Report đã rời pending và status/action khác quyết định cũ. |\n| `PAYLOAD_TOO_LARGE` | 413 | File ảnh >5 MiB hoặc request multipart >6 MiB. |\n| `VALIDATION_ERROR` | 422 | Sai kiểu, thiếu field, giới hạn/pattern/enum sai, empty PATCH, null/extra bị cấm. |\n| `RATE_LIMITED` | 429 | Dự phòng hợp đồng; chưa có limiter ứng dụng hoặc quota cụ thể. |\n| `METHOD_NOT_ALLOWED` | 405 | Dùng method chưa đăng ký. |\n| `INTERNAL_ERROR` | 500 | Lỗi không dự kiến, DB/storage/provider/config; detail đã che thông tin nội bộ. |\n\nSchema OpenAPI dự phòng nhiều status lỗi cho mỗi business operation; bảng lỗi cụ thể trong mục 4–11 nêu các nhánh thực sự có ý nghĩa. Không suy ra một endpoint tự có rate limiting chỉ vì OpenAPI khai báo 429. Framework có thể dùng HTTP_n cho status không có ánh xạ nêu trên.\n\nVí dụ lỗi validation, không echo password/nội dung request:\n\n' + block(problem_example()) + '\nVí dụ conflict moderation:\n\n' + block(problem_example(409, 'POST_ALREADY_MODERATED', '/api/v1/admin/posts/42/moderation', 'Post has already been moderated.')) + '\nVí dụ thiếu Bearer token:\n\n' + block(problem_example(401, 'UNAUTHORIZED', '/api/v1/users/me', 'Authentication credentials were not provided.')))
        if number == 14:
            out.append('| Nhãn | Endpoint/operation | Quyền bắt buộc |\n|---|---|---|\n')
            for security in AUTH:
                operations = ', '.join('`' + item['operation_id'] + '`' for item in endpoints if item['security'] == security)
                out.append(f'| {security} | {operations} | {AUTH[security]} |\n')
            out.append('\nOwnership bổ sung: users/me và bookmarks chỉ chính mình; notification chỉ recipient; post update chỉ tác giả; post delete tác giả/admin; membership me chỉ người gọi; post visibility V áp dụng interaction/comment; similar chỉ dùng nguồn active và trả rỗng nếu không đủ điều kiện. Profile công khai/author DTO không có email; auth/me/current profile chỉ chính mình; AdminUserResponse có email dành riêng admin. Role kiểm tra server-side, client ẩn nút không thay quyền.\n\nget_current_user không yêu cầu status=active cho mọi trường hợp ngoài banned/deleted; active_user mới bắt buộc active và completed profile. Không dùng is_verified làm gate hiện tại. Profile completion phải có Bearer nhưng không bắt user đã hoàn thành profile để gọi chính nó.\n')
        if number == 15:
            out.append('URL-based major version `/api/v1`. Thay field đang có, type/nullable/required, method/path, semantics/quyền, success status hoặc loại bỏ operation là breaking change cần cập nhật backend, frontend, frozen map/tests và tài liệu cùng release; khi cần phục vụ external consumers lâu dài phải lên kế hoạch major version thực sự. Thêm field response optional hoặc capability độc lập có thể tương thích nếu consumer bỏ qua field lạ; không tự tạo v2 chỉ vì đổi tên mỹ thuật. Không có compatibility alias được giữ lại trong migration này và không có external consumer nào trong repository cần alias.\n\nĐợt migration này là breaking change có phối hợp: namespace /api/v1; PUT update cũ → PATCH; toggle like/bookmark → PUT/DELETE state; follow POST → PUT; notification read POST → PUT; approve/reject gộp PUT moderation; private bookmarks thành users/me; feed có page/page_size/items/meta; public author loại bỏ dữ liệu riêng tư; lỗi ProblemDetails thay detail-only; create=201, queued reset=202, delete/logout=204; GET post không còn tự ghi view, client gọi POST views riêng. Chi tiết đầy đủ ở mapping mục 17. Không đổi JWT rotation/session model hoặc thuật toán recommendation.\n\n**OAuth deployment:** cập nhật Google provider và GOOGLE_REDIRECT_URI trước khi chuyển traffic tới callback v1; callback cũ không còn được đăng ký. Frontend/auth API origin và mọi consumer phải deploy tương thích cùng đợt. Không có DB migration schema mới cho việc đổi contract. Alembic vẫn chạy thành bước riêng; startup không chạy DDL/create_all. Docker Compose, Render và GitHub Actions giữ entrypoint `python -m app`, quy trình migrations không được nhập vào app startup.\n\nCode helper/DTO alias nội bộ không phải HTTP compatibility route. File tag_router cũ không từng được central factory đăng ký nên không phải endpoint public bị loại; danh mục tag hoạt động vẫn được bảo toàn qua tags_list và admin CRUD. Không có independent search/edit-delete-comment/R2 giả.\n')
        if number == 16:
            out.append('Nguồn sự thật: `app.factory.create_app().openapi()` và route đăng ký thực tế; `/openapi.json` dùng cùng schema. Không mở DB để export OpenAPI. Frozen migration inventory: `backend/tests/api_v1_contract.json` (58 legacy business → 60 v1 business); hạ tầng thêm 2, tổng 62. FastAPI/Pydantic dùng dependencies đã pin của backend; tránh export bằng môi trường Python khác version.\n\nTừ thư mục backend, dùng interpreter `.venv/Scripts/python.exe` trên Windows (hoặc `.venv/bin/python` trên POSIX) tương ứng cài requirements:\n\n```powershell\npython -m scripts.check_api_contract --export .tmp/openapi-v1.json\npython -m scripts.render_api_contract\npython -m scripts.check_api_contract --check-docs\npython -m pytest -q\n```\n\nTừ frontend:\n\n```powershell\nnpm run test:contract\nnpx tsc --noEmit\nnpm run lint\nnpm run build\n```\n\ncheck_api_contract kiểm tra OpenAPI 3.1, ref DTO, không trùng route/operation_id, namespace/mapping, success status, request/response DTO, auth, problem content type và field public. --check-docs kiểm tra coverage tất cả operation_id/method-path/schema/field cùng SHA-256 trên contract projection (parameters, body, response, security, components). Marker ở đầu tài liệu phải khớp; không sửa marker thủ công để bỏ qua drift. Renderer dùng schema trực tiếp cho bảng/constraints và behavior đã review trong cùng script, tự kiểm tra inventory/field coverage và ví dụ bằng Pydantic trước khi ghi tài liệu. Khi thay business rule cần review phần ghi chú behavior nữa; fingerprint không chứng minh tính đúng của câu văn. Tài liệu này là output duy nhất, không tạo thêm API reference thủ công.\n\nKiểm tra tích hợp cần SQL Server/migration/provider/email thật phải chạy trong môi trường có hạ tầng đó; unit/contract tests không tự chứng minh provider redirect registration, email delivery, live R2 (chưa triển khai) hoặc production persistence. Lệnh và kết quả thực tế của release phải được báo cáo từ lần chạy thật, không suy ra chỉ từ tài liệu.\n')
            out.append('**Kết quả kiểm chứng đợt chuẩn hóa (19/11/2026):** bộ backend kết hợp chạy bằng môi trường pin đạt **345 passed, 39 warnings** (156.19 giây), gồm kiểm tra contract/nghiệp vụ và bộ HTTP security độc lập. Frontend đạt **13 contract tests**, TypeScript `tsc --noEmit`, lint (4 cảnh báo có từ trước) và Next production build **18 pages**. SQL Server thật đã kiểm tra baseline/adoption, expand-backfill-contract, Outbox, HTTP/private DTO, GET chỉ đọc, share atomic, concurrent likes/reports và migration/app locks; database thử nghiệm được xóa sau kiểm tra. Docker production image đã build và chạy entrypoint mặc định `python -m app`, HTTP health/OpenAPI 62 operations đạt; `docker compose config --quiet` đạt. Schema Linux container và môi trường pin local có cùng fingerprint. Đây là kết quả của đợt chạy cụ thể, không phải bảo đảm mọi môi trường. Browser E2E, cloud deployment, Google provider registration thực tế và email delivery thực tế chưa được kiểm tra; R2 vẫn chưa triển khai.\n')
        if number == 17:
            legacy = {}
            for item in frozen['endpoints']:
                for old in item['legacy']:
                    legacy.setdefault(old, []).append(item)
            assert len(legacy) == frozen['legacy_endpoint_count'] == 58
            out.append('Đủ **58 method/path legacy duy nhất** từ inventory router đã đăng ký. Cột v1 có thể chứa hai method khi tách toggle; hai legacy approve/reject cùng trỏ một operation. Không có route alias cũ được giữ lại.\n\n| Legacy method/path | v1 method/path | Migration/semantics |\n|---|---|---|\n')
            for old, targets in sorted(legacy.items()):
                mapped = '<br>'.join(f'`{item["method"]} {item["path"]}`' for item in targets)
                if len(targets) > 1:
                    note = 'Bỏ toggle; PUT đặt có, DELETE đặt không; retry idempotent.'
                elif old.endswith('/approve'):
                    note = 'Gộp moderation, body {"status":"active"}; terminal trùng 200/khác 409.'
                elif old.endswith('/reject'):
                    note = 'Gộp moderation, body {"status":"rejected"}; terminal trùng 200/khác 409.'
                elif '/bookmarks' in old:
                    note = 'Chỉ dữ liệu chính mình, không nhận username của người khác.'
                elif 'complete-profile' in old:
                    note = 'Chuyển module/path và POST→PUT; authenticated, cho profile chưa hoàn thành.'
                elif old.startswith('GET /auth/users'):
                    note = 'PublicUserSummary không còn email/provider/status/is_verified.'
                elif old == 'GET /api/posts/{post_id}':
                    note = 'GET read-only; ghi view qua POST /api/v1/posts/{post_id}/views.'
                elif old == 'POST /upload/image':
                    note = 'Upload phải active/completed user; MIME+magic+5 MiB/6 MiB; 201; filesystem transitional.'
                elif old.endswith('/forgot-password'):
                    note = '202 queued Outbox, không trả token.'
                elif old.endswith('/logout') or old.startswith('DELETE '):
                    note = 'Success không body 204 (trừ unban có representation).'
                else:
                    note = 'Chuyển prefix/path/method theo bảng; DTO/error/status chuẩn hóa ở contract chi tiết.'
                out.append(f'| `{old}` | {mapped} | {note} |\n')
            out.append('\nOperation mới `POST /api/v1/posts/{post_id}/views` thay side effect cũ của GET, không làm mất capability. Phép đếm: 58 + 2 do tách hai toggle + 1 do tách view − 1 do gộp approve/reject = **60 business**. Tính cả `GET /` và `GET /health` giữ nguyên: **60 tổng legacy → 62 tổng v1**; chỉ tính nghiệp vụ: **58 → 60**. Các capability legacy còn lại được giữ; thay đổi ownership/schema bảo vệ dữ liệu riêng tư là thay đổi có chủ ý, không alias.\n')
    document = '\n'.join(out)
    # Markdown tables cannot contain blank lines between their rows.
    document = re.sub(r'(?m)(^\|[^\n]*\n)\n(?=\|)', r'\1', document)
    return re.sub(r'\n{3,}', '\n\n', document)


def validate_examples(schema):
    """Use the exact runtime Pydantic models, including extra model validators."""
    from pydantic import BaseModel, TypeAdapter
    import app.core.schemas
    import app.modules.auth.schemas
    import app.modules.users.schemas
    import app.modules.posts.schemas
    import app.modules.posts.tag_schemas
    import app.modules.comments.schemas
    import app.modules.feed.schemas
    import app.modules.notifications.schemas
    import app.modules.moderation.schemas
    import app.modules.moderation.router
    import app.modules.media.schemas
    modules = [app.core.schemas, app.modules.auth.schemas, app.modules.users.schemas,
               app.modules.posts.schemas, app.modules.posts.tag_schemas, app.modules.comments.schemas,
               app.modules.feed.schemas, app.modules.notifications.schemas, app.modules.moderation.schemas,
               app.modules.moderation.router, app.modules.media.schemas]
    models = {cls.__name__: cls for module in modules for cls in vars(module).values()
              if isinstance(cls, type) and issubclass(cls, BaseModel)}
    MODELS.update(models)
    for name, definition in schema['components']['schemas'].items():
        if name.startswith('Body_'):
            continue  # binary UploadFile is demonstrated as multipart, not JSON.
        assert name in models, name
        value = example(definition, schema['components']['schemas'], owner=name)
        TypeAdapter(models[name]).validate_python(value)


def main():
    from app.factory import create_app
    schema = validate_implementation(create_app())
    validate_examples(schema)
    document = ROOT / 'docs/API_CONTRACT.md'
    rendered = render(schema)
    assert len(re.findall(r'^## \d+\.', rendered, re.MULTILINE)) == 17
    assert len(re.findall(r'^### `(?:GET|POST|PUT|PATCH|DELETE) /', rendered, re.MULTILINE)) == 62
    assert not re.search(r'(?m)^\|[^\n]*\n\n\|', rendered), 'Broken Markdown table'
    for sample in re.findall(r'```json\n(.*?)\n```', rendered, re.DOTALL):
        json.loads(sample)
    document.write_text(rendered, encoding='utf-8')
    validate_documentation(schema, document)
    print(f'Rendered and validated {document}: 62 operations, 58 legacy routes, {len(schema["components"]["schemas"])} DTOs.')


if __name__ == '__main__':
    main()
