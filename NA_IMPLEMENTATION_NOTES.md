# NA – Frontend Smart Tag Suggestions: bàn giao và đối chiếu yêu cầu

## Phạm vi

- Không thay đổi bất kỳ file có sẵn trong ZIP gốc. Tính năng được tích hợp bằng `frontend/middleware.ts` rewrite các URL cũ sang route bổ sung, không chỉnh `PostEditor.tsx`/`app/create/page.tsx`/`app/edit/[id]/page.tsx`.
- FE-01 là prerequisite về integration/moving files. Các file bổ sung được đóng trong `frontend/features/smart-tags`, không sửa/di chuyển feature gốc. Khi FE-01 hoàn tất, FE owner cần kiểm tra và hòa nhập rule middleware vào kiến trúc chính thức.
- Backend hiện tại **chưa có** endpoint gợi ý tag theo nội dung; route mới của Next.js là `POST /api/fe/tag-suggestions`, mặc định xếp hạng từ `GET /api/posts/tags` của backend hiện tại (lexical heuristic, không giả danh AI).
- Có tùy chọn nối endpoint backend mới qua biến `TAG_SUGGESTIONS_UPSTREAM_PATH` khi Backend Owner công bố đường dẫn và contract.

## Tiến độ theo yêu cầu

| Yêu cầu | Thực hiện |
| --- | --- |
| New endpoint với title + content | `app/api/fe/tag-suggestions/route.ts`, `suggestionsApi.ts` |
| Debounce 600–800ms | 700 ms, `requestController.ts` |
| 5–10 gợi ý | tối đa 8, `tagLogic.ts` |
| Dedup/hide selected | `filterSuggestedTags`, `SmartTagPicker.tsx` |
| Abort/stale/timeout | AbortController + generation counter, timeout 5 giây ở client; upstream 4.5 giây |
| Loading/error/empty states | `useSmartTagSuggestions.ts`, `SmartTagPicker.tsx` |
| Client fallback | xếp hạng từ `getTags()` đã tải; báo lỗi nếu không có dữ liệu |
| Separate Suggested/Search | hai vùng UI riêng, không auto-select |
| Manual tag + moderation | tự nhập tag/Enter, lưu trong payload gốc; Edit giữ `requested_new_tags` |
| Create/Edit preservation | `toPostWritePayload`, `toEditDraft`; các hàm API gốc được tái sử dụng |
| Tests | `smart-tags.test.mjs` (9 passing), HTTP smoke script + checklist manual trong hướng dẫn |

## Kiểm tra thực tế

- Đã chạy: `node --experimental-strip-types --test frontend/tests/smart-tags.test.mjs`: **9 passed, 0 failed**.
- Đã kiểm tra syntax tất cả file TS/TSX mới bằng TypeScript 5.8.3 transpile diagnostics: **0 lỗi cú pháp**.
- **Chưa xác nhận** `npm run build` và E2E được xác thực với backend/SQL Server: quá trình cài `npm ci` tại môi trường đóng gói chưa hoàn thành, không có local database và credential đăng nhập. Người nhận cần chạy `npm ci`, `npm run build`, HTTP smoke và checklist auth trong `HUONG_DAN_CHAY_LOCAL_NA.md` trên máy của mình.

## Ghi chú kỹ thuật

- Frontend đã refactor thành feature modules theo FE-01 trong tương lai: cần di chuyển các file mới vào vị trí feature mới và loại bỏ middleware rewrite sau khi đổi import vào route gốc được cho phép.
- Hiện tại khi không được phép sửa file gốc, rewrite sang màn hình bổ sung là cách tích hợp không xâm lấn nhưng có chi phí: nội dung Create/Edit UI trùng một phần với bản cũ. Không nên duy trì hai phiên bản lâu dài sau khi kết thúc ràng buộc add-only.
- API hiện mặc định gợi ý lexical trong tập tag đã duyệt. Để đạt chất lượng semantic/AI theo roadmap nhóm, cần backend endpoint hoặc AI service thật. Frontend có sẵn cấu hình proxy và fallback để tích hợp.
- Nên bổ sung Playwright E2E ở CI sau khi FE-01 cung cấp test runner/chạy được database test; bản này không thêm dependency và không thay `package.json`/`package-lock.json` gốc.
