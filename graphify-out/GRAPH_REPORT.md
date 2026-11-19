# Graph Report - SE347-UITConnect  (2026-11-19)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1288 nodes · 3802 edges · 138 communities (51 shown, 87 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 262 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fd3be42f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- feed/router.py
- json
- test_moderation_transactions.py
- pytest
- posts/application.py
- feed/repository.py
- .query
- auth/router.py
- test_feed_upload_api.py
- test_notifications.py
- ApplicationError
- User
- posts/router.py
- verify_migrations.py
- seed_data.py
- exceptions.py
- test_auth_users_v1.py
- test_discovery_v1.py
- test_app.py
- auth/application.py
- auth/service.py
- Post
- posts/repository.py
- test_api_security_v1.py
- UnitOfWork
- test_content_v1.py
- comments/application.py
- create_app
- collaborative_filtering_service.py
- factory.py
- UserRepository
- setup_local_db.py
- test_auth_transactions.py
- security.py
- users/application.py
- test_posts_transactions.py
- migration_policy.py
- FakeQuery
- test_users_transactions.py
- env.py
- lifespan.py
- AuthApplicationService
- users/domain.py
- db_schema.py
- config.py
- comments/schemas.py
- core/schemas.py
- hash_password
- get
- moderation/schemas.py
- get_user_profile_summary
- get_trending_tags
- delete_read_notification
- test_transaction_architecture.py
- get_posts_by_tag
- follow_user
- ConfigurationError
- test_upload_hides_filesystem_failures_and_cleans_partial_file
- uitconnect-backend

## God Nodes (most connected - your core abstractions)
1. `User` - 115 edges
2. `ApplicationError` - 71 edges
3. `UnitOfWork` - 66 edges
4. `Post` - 42 edges
5. `AuthApplicationService` - 42 edges
6. `ModerationRepository` - 31 edges
7. `PostRepository` - 28 edges
8. `get()` - 27 edges
9. `Comment` - 26 edges
10. `moderate_report()` - 26 edges

## Surprising Connections (you probably didn't know these)
- `test_google_endpoints_return_declared_redirects()` --uses--> `AuthApplicationService`  [INFERRED]
  tests/test_auth_users_v1.py → app/modules/auth/application.py
- `test_logout_is_bodyless_and_forgot_password_is_generic_queued()` --uses--> `AuthApplicationService`  [INFERRED]
  tests/test_auth_users_v1.py → app/modules/auth/application.py
- `test_onboarding_routes_accept_authenticated_incomplete_user()` --indirect_call--> `require_active_verified_user()`  [INFERRED]
  tests/test_auth_users_v1.py → app/modules/auth/dependencies.py
- `main()` --uses--> `OutboxEvent`  [INFERRED]
  scripts/verify_migrations.py → app/db/outbox.py
- `db()` --uses--> `OutboxEvent`  [INFERRED]
  tests/test_auth_transactions.py → app/db/outbox.py

## Import Cycles
- None detected.

## Communities (138 total, 87 thin omitted)

### Community 0 - "feed/router.py"
Cohesion: 0.07
Nodes (28): PaginationMeta, get_collaborative_recommendations_endpoint(), get_posts_feed(), get_profile_analysis_endpoint(), get_profile_recommendations_endpoint(), get_similar_posts_endpoint(), get_trending_suggestions(), get_collaborative_recommendations_endpoint() (+20 more)

### Community 1 - "json"
Cohesion: 0.10
Nodes (22): dispatch_one(), enqueue_email(), OutboxEvent, OutboxRepository, utcnow(), Repository, send_email_message(), verify_api() (+14 more)

### Community 2 - "test_moderation_transactions.py"
Cohesion: 0.10
Nodes (13): AdminAuditLog, Report, db(), seed(), sqlite_identifier(), test_comment_report_duplicate_and_parent_post_scope(), test_comment_report_failure_rolls_back_report_and_notifications(), test_reply_notification_failure_rolls_back_comment_and_first_notification() (+5 more)

### Community 3 - "pytest"
Cohesion: 0.07
Nodes (16): Settings, upload_image(), upload_image(), config_env(), test_development_can_use_default_secret(), test_environment_overrides_dotenv(), test_frontend_url_has_local_default(), test_invalid_environment_values() (+8 more)

### Community 4 - "posts/application.py"
Cohesion: 0.12
Nodes (25): create_post(), delete_post(), get_all_tags(), get_post_detail(), get_post_or_404(), get_tags(), record_view(), report_post() (+17 more)

### Community 5 - "feed/repository.py"
Cohesion: 0.10
Nodes (14): calculate_content_similarity(), calculate_profile_relevance_score(), calculate_tag_similarity(), calculate_text_similarity(), calculate_time_decay(), calculate_trending_score(), _extract_keywords_from_text(), get_trending_reason() (+6 more)

### Community 6 - ".query"
Cohesion: 0.10
Nodes (19): analytics_overview(), approve_post(), create_tag(), delete_tag(), list_pending_posts(), list_reports(), list_tags(), list_users() (+11 more)

### Community 7 - "auth/router.py"
Cohesion: 0.14
Nodes (30): build_current_user_response(), complete_profile(), create_session_tokens(), forgot_password(), get_me(), get_user_by_id(), google_callback(), login() (+22 more)

### Community 8 - "test_feed_upload_api.py"
Cohesion: 0.10
Nodes (7): get_db(), require_active_verified_user(), UploadImageResponse, NotificationResponse, test_feed_keeps_query_validation(), test_feed_returns_only_active_posts_with_pagination_without_commit(), test_image_upload_saves_bytes_and_uses_configured_public_url()

### Community 9 - "test_notifications.py"
Cohesion: 0.14
Nodes (23): _approve_post(), approve_post(), Notification, create_notification(), notify_admins(), notify_followers(), collect_notifications(), FakeSession (+15 more)

### Community 10 - "ApplicationError"
Cohesion: 0.12
Nodes (25): ApplicationError, _ban_author(), ban_user(), moderate_report(), unban_user(), ban_user(), ensure_new_tag(), hide_comment() (+17 more)

### Community 11 - "User"
Cohesion: 0.14
Nodes (23): require_role(), AdminAnalyticsResponse, AdminPostModerationResponse, AdminPostsListResponse, AdminReportsListResponse, AdminUserResponse, AdminUsersListResponse, analytics_overview() (+15 more)

### Community 12 - "posts/router.py"
Cohesion: 0.14
Nodes (20): bookmark_post(), create_post(), delete_post(), get_post_detail(), get_tags(), like_post(), record_view(), report_post() (+12 more)

### Community 13 - "verify_migrations.py"
Cohesion: 0.16
Nodes (15): canonical(), collation_name(), inventory(), rows(), alembic_config(), main(), baseline_snapshot(), verify_baseline() (+7 more)

### Community 14 - "seed_data.py"
Cohesion: 0.21
Nodes (21): _activity_weight(), _affinity_score(), create_data(), _interaction_time(), _interest_set(), _lower(), _major_tag_hints(), _norm() (+13 more)

### Community 15 - "exceptions.py"
Cohesion: 0.14
Nodes (7): application_exception_handler(), http_exception_handler(), problem(), register_exception_handlers(), unhandled_exception_handler(), validation_exception_handler(), send_with_id()

### Community 16 - "test_auth_users_v1.py"
Cohesion: 0.09
Nodes (12): client(), make_app(), test_auth_user_routes_match_frozen_contract(), test_duplicate_follow_race_succeeds_only_after_existing_membership_is_confirmed(), test_follow_does_not_swallow_unrelated_integrity_failure(), test_google_endpoints_return_declared_redirects(), test_invalid_profile_patch_is_problem_details(), test_logout_is_bodyless_and_forgot_password_is_generic_queued() (+4 more)

### Community 17 - "test_discovery_v1.py"
Cohesion: 0.13
Nodes (16): PostLike, test_discovery_operation_ids_and_no_legacy_aliases(), test_discovery_requires_authentication(), test_nonempty_collaborative_keeps_ranking_flags_and_offset(), test_nonempty_trending_tags_aggregate_each_post_without_commit(), test_trending_scores_before_offset_and_has_stable_id_ties(), test_upload_enforces_exact_size_boundary_and_cleans_rejection(), test_upload_openapi_requires_a_binary_multipart_file() (+8 more)

### Community 18 - "test_app.py"
Cohesion: 0.10
Nodes (5): assert_problem(), runtime_app(), test_factory_creates_independent_apps_without_io(), test_http_errors_keep_status_detail_and_headers(), test_unhandled_errors_are_generic_logged_and_respect_cors()

### Community 19 - "auth/application.py"
Cohesion: 0.16
Nodes (11): verify_password(), require_available_user(), require_password(), require_public_user(), require_reset_token(), should_reset_password(), build_google_auth_url(), exchange_google_code() (+3 more)

### Community 20 - "auth/service.py"
Cohesion: 0.19
Nodes (10): build_password_reset_link(), build_verification_link(), AuthSession, EmailVerificationToken, PasswordResetToken, AuthRepository, create_email_verification_token(), create_password_reset_token() (+2 more)

### Community 21 - "Post"
Cohesion: 0.17
Nodes (13): Comment, Bookmark, Post, PostShare, PostTag, PostView, Tag, Follow (+5 more)

### Community 22 - "posts/repository.py"
Cohesion: 0.21
Nodes (14): get_feed_rows(), normalize_tags(), slugify(), build_post_query(), build_stats_for_post(), _paginate_bounds(), paginate_latest_posts_fast(), paginate_query() (+6 more)

### Community 23 - "test_api_security_v1.py"
Cohesion: 0.20
Nodes (18): assert_problem(), auth(), concrete_path(), test_account_state_is_rechecked_after_token_issuance(), test_actual_login_refresh_logout_lifecycle_and_bodyless_logout(), test_chunked_upload_transport_limit_cannot_be_bypassed_without_content_length(), test_every_admin_route_uses_database_role_not_elevated_jwt_claim(), test_every_protected_route_rejects_anonymous_http() (+10 more)

### Community 24 - "UnitOfWork"
Cohesion: 0.16
Nodes (9): UnitOfWork, delete_read_notification(), get_my_notifications(), mark_notification_read(), require_notification(), require_read(), NotificationRepository, test_notification_ownership_and_read_before_delete() (+1 more)

### Community 25 - "test_content_v1.py"
Cohesion: 0.10
Nodes (6): get_current_user(), api(), user(), test_interactions_require_visibility(), test_membership_idempotency(), test_owner_and_admin_pending_visibility()

### Community 26 - "comments/application.py"
Cohesion: 0.21
Nodes (10): build_comment_tree(), create_comment(), get_comments(), report_comment(), require_found(), require_unreported(), CommentRepository, normalize_report_reason() (+2 more)

### Community 27 - "create_app"
Cohesion: 0.20
Nodes (13): create_app(), contract_digest(), contract_projection(), frozen_contract(), main(), schema_name(), validate_documentation(), validate_implementation() (+5 more)

### Community 28 - "collaborative_filtering_service.py"
Cohesion: 0.16
Nodes (8): calculate_follow_overlap(), calculate_post_overlap(), calculate_user_tag_similarity(), _parse_interest_tags(), calculate_user_similarity(), find_similar_users(), get_collaborative_recommendations(), get_personalized_feed()

### Community 29 - "factory.py"
Cohesion: 0.15
Nodes (6): configure_openapi(), RequestIdMiddleware, health_check(), register_middleware(), register_routers(), root()

### Community 30 - "UserRepository"
Cohesion: 0.22
Nodes (11): follow_user(), get_user_bookmarks(), get_user_comments(), get_user_posts(), get_user_profile(), _require_user(), unfollow_user(), follow_response_state() (+3 more)

### Community 31 - "setup_local_db.py"
Cohesion: 0.18
Nodes (9): run_seed(), create_database_if_missing(), get_database_url(), main(), parse_args(), quote_sqlserver_identifier(), run_seed(), run_upgrade() (+1 more)

### Community 32 - "test_auth_transactions.py"
Cohesion: 0.18
Nodes (12): add_user(), count_commits(), db(), sqlite_identifier(), test_google_user_and_session_roll_back_together(), test_invalid_refresh_removes_session_before_rejection(), test_login_persists_session_once(), test_password_reset_commit_failure_rolls_back_token_and_outbox() (+4 more)

### Community 33 - "security.py"
Cohesion: 0.22
Nodes (9): create_access_token(), create_refresh_token(), _create_token(), decode_token(), require_refresh_session(), refresh_token(), RefreshTokenRequest, test_invalid_jwt_never_authenticates() (+1 more)

### Community 34 - "users/application.py"
Cohesion: 0.26
Nodes (6): CurrentUserProfileResponse, FollowResponse, PublicUserProfileResponse, UpdateProfileRequest, UserCommentResponse, UserPostResponse

### Community 35 - "test_posts_transactions.py"
Cohesion: 0.19
Nodes (9): assert_no_share(), count(), test_like_and_bookmark_are_idempotent_memberships(), test_owner_update_returns_pending_post_and_requests_unknown_tags(), test_share_failure_rolls_back_post_tags_share_and_notifications(), fail_after(), test_share_success_commits_once_with_tags_and_both_notifications(), test_student_cannot_view_another_pending_post_or_update_as_admin() (+1 more)

### Community 36 - "migration_policy.py"
Cohesion: 0.20
Nodes (7): upgrade(), downgrade(), upgrade(), baseline_statements(), require_phase(), test_baseline_artifact_tampering_is_rejected(), test_contract_requires_explicit_opt_in()

### Community 38 - "test_users_transactions.py"
Cohesion: 0.21
Nodes (7): commits(), count(), test_follow_and_notification_commit_together_once(), test_follow_commit_failure_rolls_back_follow_and_notification(), test_follow_notification_failure_rolls_back_follow(), test_profile_update_commits_once_and_normalizes_fields(), users_db()

### Community 39 - "env.py"
Cohesion: 0.23
Nodes (9): include_object(), run_migrations_offline(), run_migrations_online(), migrate(), review_autogenerate(), validate_expand(), verify_version_step(), test_expand_autogenerate_accepts_additive_changes() (+1 more)

### Community 42 - "users/domain.py"
Cohesion: 0.23
Nodes (10): _current_profile(), get_my_profile(), _profile(), update_my_profile(), can_view_non_active_posts(), normalize_interest_tags(), normalize_optional(), parse_interest_tags() (+2 more)

### Community 43 - "db_schema.py"
Cohesion: 0.30
Nodes (8): column_sql(), differences(), index_keys(), qualified(), quote(), render_baseline(), split_batches(), test_metadata_comparison_and_sql_batch_boundaries()

### Community 45 - "comments/schemas.py"
Cohesion: 0.27
Nodes (6): create_comment(), get_comments(), report_comment(), CommentBase, CommentResponse, CreateCommentRequest

### Community 46 - "core/schemas.py"
Cohesion: 0.36
Nodes (6): as_utc(), HealthResponse, ProblemDetails, PublicUserSummary, RootResponse, ValidationIssue

### Community 47 - "hash_password"
Cohesion: 0.36
Nodes (3): hash_password(), create_admin(), create_demo_user()

### Community 48 - "get"
Cohesion: 0.33
Nodes (7): get_my_profile(), get_user_bookmarks(), get_user_comments(), get_user_posts(), get_user_profile(), update_my_profile(), get()

### Community 49 - "moderation/schemas.py"
Cohesion: 0.39
Nodes (5): BanUserRequest, CreateReportRequest, ModeratePostRequest, ModerateReportRequest, ReportResponse

### Community 50 - "get_user_profile_summary"
Cohesion: 0.33
Nodes (3): get_profile_summary_endpoint(), get_user_profile_summary(), get_profile_summary_endpoint()

### Community 51 - "get_trending_tags"
Cohesion: 0.33
Nodes (3): get_trending_tags_endpoint(), get_trending_tags(), get_trending_tags_endpoint()

### Community 52 - "delete_read_notification"
Cohesion: 0.33
Nodes (3): delete_read_notification(), get_my_notifications(), mark_notification_read()

### Community 53 - "test_transaction_architecture.py"
Cohesion: 0.53
Nodes (3): calls(), test_domain_modules_never_commit_or_rollback(), test_routers_and_applications_do_not_construct_database_queries()

### Community 54 - "get_posts_by_tag"
Cohesion: 0.50
Nodes (3): get_posts_by_tag(), get_all_tags(), get_posts_by_tag()

## Knowledge Gaps
- **1 isolated node(s):** `uitconnect-backend`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 357 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **87 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `User` connect `User` to `feed/router.py`, `json`, `test_moderation_transactions.py`, `pytest`, `feed/repository.py`, `auth/router.py`, `test_feed_upload_api.py`, `test_notifications.py`, `posts/router.py`, `seed_data.py`, `auth/application.py`, `auth/service.py`, `Post`, `posts/repository.py`, `test_api_security_v1.py`, `test_content_v1.py`, `test_auth_transactions.py`, `users/application.py`, `test_posts_transactions.py`, `test_users_transactions.py`, `comments/schemas.py`, `hash_password`, `get`, `get_user_profile_summary`, `get_trending_tags`, `delete_read_notification`, `follow_user`?**
  _High betweenness centrality (0.153) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `User` (e.g. with `get_current_user()` and `require_active_verified_user()`) actually correct?**
  _`User` has 15 INFERRED edges - model-reasoned connections that need verification._
- **What connects `uitconnect-backend` to the rest of the system?**
  _1 weakly-connected nodes found - possible missing edges._
- **Should `feed/router.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06836055656382335 - nodes in this community are weakly interconnected._
- **Why does `UnitOfWork` connect `UnitOfWork` to `test_auth_transactions.py`, `json`, `users/application.py`, `test_moderation_transactions.py`, `posts/application.py`, `.query`, `AuthApplicationService`, `ApplicationError`, `users/domain.py`, `verify_migrations.py`, `hash_password`, `auth/application.py`, `auth/service.py`, `test_content_v1.py`, `comments/application.py`, `UserRepository`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `ApplicationError` (e.g. with `UnitOfWork` and `AuthApplicationService`) actually correct?**
  _`ApplicationError` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Should `json` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._