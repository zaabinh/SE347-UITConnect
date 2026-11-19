# Graph Report - SE347-UITConnect  (2026-11-19)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1317 nodes · 3871 edges · 135 communities (51 shown, 84 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 257 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `cd0d65b3`
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
- Base

## God Nodes (most connected - your core abstractions)
1. `User` - 115 edges
2. `ApplicationError` - 71 edges
3. `UnitOfWork` - 65 edges
4. `AuthApplicationService` - 42 edges
5. `Post` - 42 edges
6. `ModerationRepository` - 31 edges
7. `PostRepository` - 27 edges
8. `get()` - 27 edges
9. `Comment` - 26 edges
10. `moderate_report()` - 26 edges

## Surprising Connections (you probably didn't know these)
- `test_google_endpoints_return_declared_redirects()` --uses--> `AuthApplicationService`  [INFERRED]
  tests/test_auth_users_v1.py → app/modules/auth/application.py
- `test_logout_is_bodyless_and_forgot_password_is_generic_queued()` --uses--> `AuthApplicationService`  [INFERRED]
  tests/test_auth_users_v1.py → app/modules/auth/application.py
- `count()` --calls--> `sessions()`  [INFERRED]
  scripts/api_sqlserver_checks.py → tests/test_db_transactions.py
- `get_test_db()` --calls--> `sessions()`  [INFERRED]
  scripts/api_sqlserver_checks.py → tests/test_db_transactions.py
- `test_onboarding_routes_accept_authenticated_incomplete_user()` --indirect_call--> `require_active_verified_user()`  [INFERRED]
  tests/test_auth_users_v1.py → app/modules/auth/dependencies.py

## Import Cycles
- None detected.

## Communities (135 total, 84 thin omitted)

### Community 0 - "feed/router.py"
Cohesion: 0.06
Nodes (50): application_exception_handler(), ApplicationError, analytics_overview(), approve_post(), _approve_post(), _ban_author(), ban_user(), create_tag() (+42 more)

### Community 1 - "json"
Cohesion: 0.05
Nodes (36): lifespan(), create_app(), contract_digest(), contract_projection(), frozen_contract(), main(), schema_name(), validate_documentation() (+28 more)

### Community 2 - "test_moderation_transactions.py"
Cohesion: 0.06
Nodes (38): _current_profile(), follow_user(), get_my_profile(), get_user_bookmarks(), get_user_comments(), get_user_posts(), get_user_profile(), _profile() (+30 more)

### Community 3 - "pytest"
Cohesion: 0.05
Nodes (20): configure_openapi(), apply_error_cors(), http_exception_handler(), problem(), unhandled_exception_handler(), validation_exception_handler(), RequestIdMiddleware, send_with_id() (+12 more)

### Community 4 - "posts/application.py"
Cohesion: 0.11
Nodes (34): decode_token(), get_current_user(), build_current_user_response(), complete_profile(), create_session_tokens(), forgot_password(), get_me(), google_callback() (+26 more)

### Community 5 - "feed/repository.py"
Cohesion: 0.14
Nodes (3): Repository, AdminAuditLog, Report

### Community 6 - ".query"
Cohesion: 0.15
Nodes (19): dispatch_one(), enqueue_email(), OutboxEvent, OutboxRepository, utcnow(), UnitOfWork, send_email_message(), enqueue() (+11 more)

### Community 7 - "auth/router.py"
Cohesion: 0.12
Nodes (21): get_user_by_id(), get_collaborative_recommendations_endpoint(), get_posts_feed(), get_profile_recommendations_endpoint(), get_profile_summary_endpoint(), get_similar_posts_endpoint(), get_trending_suggestions(), get_trending_tags_endpoint() (+13 more)

### Community 8 - "test_feed_upload_api.py"
Cohesion: 0.12
Nodes (12): Settings, config_env(), test_development_can_use_default_secret(), test_environment_overrides_dotenv(), test_frontend_url_has_local_default(), test_invalid_environment_values(), test_production_accepts_custom_secret_and_redacts_secrets(), test_production_fails_before_startup_side_effects() (+4 more)

### Community 9 - "test_notifications.py"
Cohesion: 0.13
Nodes (13): PaginationMeta, get_profile_analysis_endpoint(), get_profile_analysis_endpoint(), CollaborativePostListResponse, ProfileAnalysisResponse, ProfileBasedPostListResponse, SimilarPostListResponse, SimilarPostResponse (+5 more)

### Community 10 - "ApplicationError"
Cohesion: 0.13
Nodes (14): AuthApplicationService, google_login(), add_user(), count_commits(), db(), sqlite_identifier(), test_google_user_and_session_roll_back_together(), test_invalid_refresh_removes_session_before_rejection() (+6 more)

### Community 11 - "User"
Cohesion: 0.18
Nodes (21): create_access_token(), _create_token(), assert_problem(), auth(), concrete_path(), test_account_state_is_rechecked_after_token_issuance(), test_actual_login_refresh_logout_lifecycle_and_bodyless_logout(), test_chunked_upload_transport_limit_cannot_be_bypassed_without_content_length() (+13 more)

### Community 12 - "posts/router.py"
Cohesion: 0.13
Nodes (12): verify_password(), require_available_user(), require_password(), require_public_user(), require_refresh_session(), require_reset_token(), should_reset_password(), build_google_auth_url() (+4 more)

### Community 13 - "verify_migrations.py"
Cohesion: 0.18
Nodes (16): collect_notifications(), FakeSession, make_comment(), make_post(), make_user(), test_admin_delete_post_notifies_author(), test_comment_and_reply_create_expected_notifications(), test_create_notification_builds_unread_notification() (+8 more)

### Community 14 - "seed_data.py"
Cohesion: 0.09
Nodes (7): api(), user(), test_interactions_require_visibility(), test_membership_idempotency(), test_owner_and_admin_pending_visibility(), test_short_title_after_trim_rejected_before_writes(), test_whitespace_comment_rejected_before_writes_and_listing_stays_valid()

### Community 15 - "exceptions.py"
Cohesion: 0.20
Nodes (13): Bookmark, Post, PostLike, PostShare, PostTag, PostView, Tag, Follow (+5 more)

### Community 16 - "test_auth_users_v1.py"
Cohesion: 0.21
Nodes (21): _activity_weight(), _affinity_score(), create_data(), _interaction_time(), _interest_set(), _lower(), _major_tag_hints(), _norm() (+13 more)

### Community 17 - "test_discovery_v1.py"
Cohesion: 0.14
Nodes (16): require_role(), AdminAnalyticsResponse, AdminPostModerationResponse, AdminPostsListResponse, AdminReportsListResponse, AdminUserResponse, AdminUsersListResponse, analytics_overview() (+8 more)

### Community 18 - "test_app.py"
Cohesion: 0.15
Nodes (8): calculate_content_similarity(), calculate_tag_similarity(), calculate_text_similarity(), calculate_time_decay(), calculate_trending_score(), get_trending_reason(), preprocess_text(), get_trending_posts()

### Community 19 - "auth/application.py"
Cohesion: 0.13
Nodes (8): create_database_if_missing(), get_database_url(), main(), parse_args(), quote_sqlserver_identifier(), run_seed(), run_upgrade(), main()

### Community 20 - "auth/service.py"
Cohesion: 0.20
Nodes (10): build_password_reset_link(), build_verification_link(), AuthSession, EmailVerificationToken, PasswordResetToken, AuthRepository, create_email_verification_token(), create_password_reset_token() (+2 more)

### Community 21 - "Post"
Cohesion: 0.13
Nodes (11): get_collaborative_recommendations_endpoint(), get_posts_feed(), get_profile_recommendations_endpoint(), get_similar_posts_endpoint(), get_trending_suggestions(), get_profile_based_recommendations(), get_similar_posts(), CollaborativePostResponse (+3 more)

### Community 22 - "posts/repository.py"
Cohesion: 0.14
Nodes (16): test_discovery_operation_ids_and_no_legacy_aliases(), test_discovery_requires_authentication(), test_nonempty_collaborative_keeps_ranking_flags_and_offset(), test_nonempty_trending_tags_aggregate_each_post_without_commit(), test_trending_scores_before_offset_and_has_stable_id_ties(), test_upload_bounds_reads_when_stream_is_larger_than_limit(), read(), test_upload_enforces_exact_size_boundary_and_cleans_rejection() (+8 more)

### Community 23 - "test_api_security_v1.py"
Cohesion: 0.18
Nodes (14): upgrade(), collation_name(), column_sql(), differences(), index_keys(), inventory(), qualified(), quote() (+6 more)

### Community 24 - "UnitOfWork"
Cohesion: 0.16
Nodes (10): delete_read_notification(), get_my_notifications(), mark_notification_read(), require_notification(), require_read(), NotificationRepository, delete_read_notification(), get_my_notifications() (+2 more)

### Community 25 - "test_content_v1.py"
Cohesion: 0.13
Nodes (13): build_comment_tree(), Comment, http_api(), test_profile_activity_hides_posts_viewer_cannot_access(), db(), seed(), sqlite_identifier(), test_comment_report_duplicate_and_parent_post_scope() (+5 more)

### Community 26 - "comments/application.py"
Cohesion: 0.13
Nodes (10): register_exception_handlers(), client(), make_app(), test_auth_user_routes_match_frozen_contract(), test_follow_does_not_swallow_unrelated_integrity_failure(), test_google_endpoints_return_declared_redirects(), test_invalid_profile_patch_is_problem_details(), test_logout_is_bodyless_and_forgot_password_is_generic_queued() (+2 more)

### Community 27 - "create_app"
Cohesion: 0.16
Nodes (8): calculate_follow_overlap(), calculate_post_overlap(), calculate_user_tag_similarity(), _parse_interest_tags(), calculate_user_similarity(), find_similar_users(), get_collaborative_recommendations(), get_personalized_feed()

### Community 28 - "collaborative_filtering_service.py"
Cohesion: 0.20
Nodes (10): update_post(), BookmarkResponse, CreatePostRequest, LikeResponse, PostBase, PostListResponse, PostResponse, SharePostRequest (+2 more)

### Community 29 - "factory.py"
Cohesion: 0.20
Nodes (12): get_feed_rows(), normalize_tags(), build_post_query(), _paginate_bounds(), paginate_latest_posts_fast(), paginate_query(), paginate_trending_posts_fast(), Pagination (+4 more)

### Community 30 - "UserRepository"
Cohesion: 0.18
Nodes (10): include_object(), run_migrations_offline(), run_migrations_online(), migrate(), downgrade(), upgrade(), require_phase(), review_autogenerate() (+2 more)

### Community 31 - "setup_local_db.py"
Cohesion: 0.15
Nodes (6): report_post(), set_bookmark(), set_like(), build_stats_for_post(), PostRepository, test_like_and_bookmark_are_idempotent_memberships()

### Community 32 - "test_auth_transactions.py"
Cohesion: 0.19
Nodes (10): verify_api(), count(), get_test_db(), baseline_snapshot(), verify_baseline(), apply(), expect_rejection(), main() (+2 more)

### Community 33 - "security.py"
Cohesion: 0.23
Nodes (5): create_refresh_token(), hash_password(), create_admin(), run_seed(), create_demo_user()

### Community 34 - "users/application.py"
Cohesion: 0.27
Nodes (5): require_unreported(), Notification, create_notification(), notify_admins(), notify_followers()

### Community 35 - "test_posts_transactions.py"
Cohesion: 0.26
Nodes (15): create_post(), delete_post(), get_post_detail(), get_post_or_404(), record_view(), _response(), _sync_tags(), update_post() (+7 more)

### Community 37 - "FakeQuery"
Cohesion: 0.27
Nodes (4): ConfigurationError, get_db(), normalize_database_url(), require_active_verified_user()

### Community 38 - "test_users_transactions.py"
Cohesion: 0.18
Nodes (6): get_profile_summary_endpoint(), calculate_profile_relevance_score(), _extract_keywords_from_text(), _parse_tags_from_string(), analyze_user_profile(), get_user_profile_summary()

### Community 39 - "env.py"
Cohesion: 0.21
Nodes (9): bookmark_post(), create_post(), delete_post(), get_post_detail(), like_post(), report_post(), share_post(), unbookmark_post() (+1 more)

### Community 40 - "lifespan.py"
Cohesion: 0.16
Nodes (6): test_feed_keeps_query_validation(), test_feed_returns_only_active_posts_with_pagination_without_commit(), test_image_upload_saves_bytes_and_uses_configured_public_url(), test_trending_and_similar_responses_preserve_scores_flags_and_vietnamese_reasons(), test_upload_hides_filesystem_failures_and_cleans_partial_file(), read()

### Community 42 - "users/domain.py"
Cohesion: 0.17
Nodes (8): share_post(), assert_no_share(), count(), test_owner_update_returns_pending_post_and_requests_unknown_tags(), test_share_failure_rolls_back_post_tags_share_and_notifications(), fail_after(), test_share_success_commits_once_with_tags_and_both_notifications(), test_student_share_stays_pending_and_notifies_original_author()

### Community 43 - "db_schema.py"
Cohesion: 0.24
Nodes (3): canonical(), main(), main()

### Community 44 - "config.py"
Cohesion: 0.21
Nodes (6): alembic_config(), validate_expand(), test_expand_autogenerate_accepts_additive_changes(), test_expand_autogenerate_rejects_destructive_or_restrictive_changes(), test_frozen_live_baseline_and_offline_replay(), test_revision_template_preserves_phase_and_enforces_guard()

### Community 45 - "comments/schemas.py"
Cohesion: 0.47
Nodes (5): create_comment(), get_comments(), report_comment(), require_found(), CommentRepository

### Community 46 - "core/schemas.py"
Cohesion: 0.33
Nodes (3): CommentBase, CommentResponse, CreateCommentRequest

### Community 47 - "hash_password"
Cohesion: 0.36
Nodes (5): ban_user(), delete_tag(), moderate_post(), moderate_report(), unban_user()

### Community 48 - "get"
Cohesion: 0.43
Nodes (5): apply_update(), initial_status(), make_shared_post(), require_owner(), slugify()

### Community 49 - "moderation/schemas.py"
Cohesion: 0.48
Nodes (5): BanUserRequest, CreateReportRequest, ModeratePostRequest, ModerateReportRequest, ReportResponse

### Community 51 - "get_trending_tags"
Cohesion: 0.47
Nodes (3): normalize_report_reason(), test_normalize_report_reason_fallback(), test_normalize_report_reason_maps_aliases()

### Community 52 - "delete_read_notification"
Cohesion: 0.40
Nodes (4): get_all_tags(), get_posts_by_tag(), get_all_tags(), get_posts_by_tag()

### Community 53 - "test_transaction_architecture.py"
Cohesion: 0.50
Nodes (3): create_comment(), get_comments(), report_comment()

## Knowledge Gaps
- **1 isolated node(s):** `uitconnect-backend`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 364 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **84 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `User` connect `auth/router.py` to `feed/router.py`, `test_moderation_transactions.py`, `pytest`, `posts/application.py`, `feed/repository.py`, `test_notifications.py`, `ApplicationError`, `User`, `posts/router.py`, `verify_migrations.py`, `seed_data.py`, `exceptions.py`, `test_auth_users_v1.py`, `test_discovery_v1.py`, `auth/service.py`, `UnitOfWork`, `test_content_v1.py`, `collaborative_filtering_service.py`, `test_auth_transactions.py`, `security.py`, `test_posts_transactions.py`, `migration_policy.py`, `FakeQuery`, `env.py`, `core/schemas.py`, `hash_password`, `test_transaction_architecture.py`?**
  _High betweenness centrality (0.150) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `User` (e.g. with `get_current_user()` and `require_active_verified_user()`) actually correct?**
  _`User` has 15 INFERRED edges - model-reasoned connections that need verification._
- **What connects `uitconnect-backend` to the rest of the system?**
  _1 weakly-connected nodes found - possible missing edges._
- **Should `feed/router.py` be split into smaller, more focused modules?**
  _Cohesion score 0.055381400208986416 - nodes in this community are weakly interconnected._
- **Why does `UnitOfWork` connect `.query` to `feed/router.py`, `security.py`, `users/application.py`, `test_posts_transactions.py`, `test_moderation_transactions.py`, `test_auth_transactions.py`, `ApplicationError`, `users/domain.py`, `posts/router.py`, `comments/schemas.py`, `seed_data.py`, `auth/service.py`, `UnitOfWork`, `test_content_v1.py`, `setup_local_db.py`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `ApplicationError` (e.g. with `UnitOfWork` and `AuthApplicationService`) actually correct?**
  _`ApplicationError` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Should `json` be split into smaller, more focused modules?**
  _Cohesion score 0.051643192488262914 - nodes in this community are weakly interconnected._