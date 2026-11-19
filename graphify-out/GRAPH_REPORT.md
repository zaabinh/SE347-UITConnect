# Graph Report - SE347-UITConnect  (2026-11-19)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1108 nodes · 3420 edges · 109 communities (28 shown, 81 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 461 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e933ecdf`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 75
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 108

## God Nodes (most connected - your core abstractions)
1. `User` - 122 edges
2. `UnitOfWork` - 63 edges
3. `Post` - 62 edges
4. `ApplicationError` - 60 edges
5. `AuthApplicationService` - 41 edges
6. `Comment` - 38 edges
7. `ModerationRepository` - 38 edges
8. `PostRepository` - 32 edges
9. `Notification` - 30 edges
10. `PostLike` - 28 edges

## Surprising Connections (you probably didn't know these)
- `run_migrations_offline()` --indirect_call--> `verify_version_step()`  [INFERRED]
  alembic/env.py → scripts/migration_policy.py
- `test_comment_report_duplicate_and_parent_post_scope()` --uses--> `ApplicationError`  [INFERRED]
  tests/test_comments_transactions.py → app/core/exceptions.py
- `test_notification_ownership_and_read_before_delete()` --uses--> `ApplicationError`  [INFERRED]
  tests/test_comments_transactions.py → app/core/exceptions.py
- `test_admin_endpoints_reject_non_admin()` --uses--> `ApplicationError`  [INFERRED]
  tests/test_moderation_transactions.py → app/core/exceptions.py
- `test_ban_permissions_leave_no_writes()` --uses--> `ApplicationError`  [INFERRED]
  tests/test_moderation_transactions.py → app/core/exceptions.py

## Import Cycles
- None detected.

## Communities (109 total, 81 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.12
Nodes (16): PaginationMeta, CollaborativePostListResponse, CollaborativePostResponse, ProfileAnalysisResponse, ProfileBasedPostListResponse, ProfileBasedPostResponse, SimilarPostListResponse, SimilarPostResponse (+8 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (43): ApplicationError, create_access_token(), create_refresh_token(), _create_token(), hash_password(), verify_password(), UnitOfWork, AuthApplicationService (+35 more)

### Community 2 - "Community 2"
Cohesion: 0.15
Nodes (8): calculate_content_similarity(), calculate_tag_similarity(), calculate_text_similarity(), calculate_time_decay(), calculate_trending_score(), get_trending_reason(), preprocess_text(), get_trending_posts()

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (50): application_exception_handler(), Comment, CommentBase, CommentCreate, CommentResponse, AdminAuditLog, Report, ReportCreate (+42 more)

### Community 4 - "Community 4"
Cohesion: 0.14
Nodes (10): Settings, config_env(), test_development_can_use_default_secret(), test_environment_overrides_dotenv(), test_frontend_url_has_local_default(), test_invalid_environment_values(), test_production_accepts_custom_secret_and_redacts_secrets(), test_production_fails_before_startup_side_effects() (+2 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (48): build_comment_tree(), create_comment(), get_comments(), report_comment(), require_found(), require_unreported(), CommentRepository, create_comment() (+40 more)

### Community 7 - "Community 7"
Cohesion: 0.12
Nodes (8): lifespan(), create_app(), health_check(), register_middleware(), register_routers(), root(), test_factory_creates_independent_apps_without_io(), test_feed_still_requires_authentication()

### Community 8 - "Community 8"
Cohesion: 0.05
Nodes (84): get_feed_rows(), create_post(), delete_post(), get_all_tags(), get_post_detail(), get_post_or_404(), get_posts_by_tag(), get_tags() (+76 more)

### Community 9 - "Community 9"
Cohesion: 0.26
Nodes (6): include_object(), run_migrations_offline(), run_migrations_online(), migrate(), review_autogenerate(), verify_version_step()

### Community 10 - "Community 10"
Cohesion: 0.27
Nodes (8): run_seed(), create_database_if_missing(), get_database_url(), main(), parse_args(), quote_sqlserver_identifier(), run_seed(), run_upgrade()

### Community 11 - "Community 11"
Cohesion: 0.10
Nodes (3): runtime_app(), test_http_errors_keep_status_detail_and_headers(), test_unhandled_errors_are_generic_logged_and_respect_cors()

### Community 12 - "Community 12"
Cohesion: 0.20
Nodes (3): register_exception_handlers(), unhandled_exception_handler(), validation_exception_handler()

### Community 13 - "Community 13"
Cohesion: 0.26
Nodes (9): collation_name(), baseline_snapshot(), verify_baseline(), apply(), expect_rejection(), main(), test_baseline_artifact_tampering_is_rejected(), test_frozen_live_baseline_and_offline_replay() (+1 more)

### Community 14 - "Community 14"
Cohesion: 0.10
Nodes (20): dispatch_one(), enqueue_email(), OutboxEvent, OutboxRepository, utcnow(), Repository, send_email_message(), main() (+12 more)

### Community 15 - "Community 15"
Cohesion: 0.07
Nodes (43): _current_profile(), follow_user(), get_my_profile(), get_user_bookmarks(), get_user_comments(), get_user_posts(), get_user_profile(), _profile() (+35 more)

### Community 75 - "Community 75"
Cohesion: 0.10
Nodes (33): require_role(), AdminAnalyticsResponse, AdminPostModerationResponse, AdminPostsListResponse, AdminReportsListResponse, AdminUserResponse, AdminUsersListResponse, analytics_overview() (+25 more)

### Community 85 - "Community 85"
Cohesion: 0.25
Nodes (9): upgrade(), column_sql(), index_keys(), inventory(), qualified(), quote(), render_baseline(), rows() (+1 more)

### Community 86 - "Community 86"
Cohesion: 0.24
Nodes (4): canonical(), alembic_config(), main(), main()

### Community 87 - "Community 87"
Cohesion: 0.11
Nodes (35): decode_token(), get_current_user(), build_current_user_response(), complete_profile(), create_session_tokens(), forgot_password(), get_me(), get_user_by_id() (+27 more)

### Community 88 - "Community 88"
Cohesion: 0.10
Nodes (15): calculate_follow_overlap(), calculate_post_overlap(), calculate_profile_relevance_score(), calculate_user_tag_similarity(), _extract_keywords_from_text(), _parse_interest_tags(), _parse_tags_from_string(), analyze_user_profile() (+7 more)

### Community 89 - "Community 89"
Cohesion: 0.13
Nodes (10): get_profile_analysis_endpoint(), get_profile_summary_endpoint(), get_collaborative_recommendations_endpoint(), get_posts_feed(), get_profile_analysis_endpoint(), get_profile_recommendations_endpoint(), get_profile_summary_endpoint(), get_similar_posts_endpoint() (+2 more)

### Community 90 - "Community 90"
Cohesion: 0.22
Nodes (5): ConfigurationError, get_db(), normalize_database_url(), require_active_verified_user(), NotificationResponse

### Community 91 - "Community 91"
Cohesion: 0.16
Nodes (9): get_collaborative_recommendations_endpoint(), get_posts_feed(), get_profile_recommendations_endpoint(), get_similar_posts_endpoint(), get_trending_suggestions(), get_trending_tags_endpoint(), get_similar_posts(), get_trending_tags() (+1 more)

### Community 93 - "Community 93"
Cohesion: 0.14
Nodes (6): test_feed_keeps_query_validation(), test_feed_returns_only_active_posts_with_pagination_without_commit(), test_image_upload_saves_bytes_and_uses_configured_public_url(), test_trending_and_similar_responses_preserve_scores_flags_and_vietnamese_reasons(), test_upload_preserves_filesystem_failure_response(), upload_client()

### Community 94 - "Community 94"
Cohesion: 0.21
Nodes (8): delete_read_notification(), get_my_notifications(), mark_notification_read(), require_notification(), require_read(), delete_read_notification(), get_my_notifications(), mark_notification_read()

### Community 97 - "Community 97"
Cohesion: 0.21
Nodes (8): differences(), split_batches(), validate_expand(), test_catalog_verification_refuses_sqlite(), test_expand_autogenerate_accepts_additive_changes(), test_expand_autogenerate_rejects_destructive_or_restrictive_changes(), test_metadata_comparison_and_sql_batch_boundaries(), test_revision_template_preserves_phase_and_enforces_guard()

### Community 98 - "Community 98"
Cohesion: 0.43
Nodes (3): calls(), test_domain_modules_never_commit_or_rollback(), test_routers_and_applications_do_not_construct_database_queries()

### Community 99 - "Community 99"
Cohesion: 0.60
Nodes (4): downgrade(), upgrade(), require_phase(), test_contract_requires_explicit_opt_in()

## Knowledge Gaps
- **1 isolated node(s):** `uitconnect-backend`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 310 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **81 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `User` connect `Community 75` to `Community 0`, `Community 1`, `Community 3`, `Community 6`, `Community 8`, `Community 15`, `Community 87`, `Community 88`, `Community 89`, `Community 90`, `Community 94`?**
  _High betweenness centrality (0.182) - this node is a cross-community bridge._
- **Are the 83 inferred relationships involving `User` (e.g. with `AuthApplicationService` and `get_current_user()`) actually correct?**
  _`User` has 83 INFERRED edges - model-reasoned connections that need verification._
- **What connects `uitconnect-backend` to the rest of the system?**
  _1 weakly-connected nodes found - possible missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.12299465240641712 - nodes in this community are weakly interconnected._
- **Why does `UnitOfWork` connect `Community 1` to `Community 3`, `Community 6`, `Community 8`, `Community 13`, `Community 14`, `Community 15`, `Community 94`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `UnitOfWork` (e.g. with `AuthApplicationService` and `test_invalid_refresh_removes_session_before_rejection()`) actually correct?**
  _`UnitOfWork` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.052922139729678276 - nodes in this community are weakly interconnected._