# Graph Report - SE347-UITConnect  (2026-11-18)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 667 nodes · 1941 edges · 86 communities (12 shown, 74 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 296 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `fb4e6f02`
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
- Community 75

## God Nodes (most connected - your core abstractions)
1. `User` - 108 edges
2. `Post` - 56 edges
3. `Comment` - 37 edges
4. `Tag` - 28 edges
5. `PostLike` - 25 edges
6. `create_notification()` - 24 edges
7. `Bookmark` - 22 edges
8. `PostTag` - 21 edges
9. `MessageResponse` - 20 edges
10. `PostView` - 20 edges

## Surprising Connections (you probably didn't know these)
- `test_admin_delete_post_notifies_author()` --uses--> `Comment`  [INFERRED]
  tests/test_notifications.py → app/modules/comments/models.py
- `test_comment_and_reply_create_expected_notifications()` --uses--> `Comment`  [INFERRED]
  tests/test_notifications.py → app/modules/comments/models.py
- `test_post_report_notifies_admins_and_post_author()` --uses--> `Report`  [INFERRED]
  tests/test_notifications.py → app/modules/moderation/models.py
- `_seed_comments()` --uses--> `Post`  [INFERRED]
  scripts/seed_data.py → app/modules/posts/models.py
- `_seed_natural_interactions()` --uses--> `Post`  [INFERRED]
  scripts/seed_data.py → app/modules/posts/models.py

## Import Cycles
- None detected.

## Communities (86 total, 74 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (41): build_comment_tree(), create_comment(), get_comments(), report_comment(), CommentBase, CommentCreate, CommentResponse, ReportCreate (+33 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (52): create_access_token(), create_refresh_token(), _create_token(), decode_token(), verify_password(), get_current_user(), build_password_reset_link(), build_verification_link() (+44 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (47): Comment, analyze_user_profile(), calculate_profile_relevance_score(), _extract_keywords_from_text(), get_profile_based_recommendations(), _parse_tags_from_string(), get_posts_feed(), calculate_content_similarity() (+39 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (12): EmailVerificationToken, calculate_follow_overlap(), calculate_post_overlap(), calculate_tag_similarity(), calculate_user_similarity(), find_similar_users(), get_collaborative_recommendations(), get_personalized_feed() (+4 more)

### Community 4 - "Community 4"
Cohesion: 0.14
Nodes (9): Settings, config_env(), test_development_can_use_default_secret(), test_environment_overrides_dotenv(), test_invalid_environment_values(), test_production_accepts_custom_secret_and_redacts_secrets(), test_production_fails_before_startup_side_effects(), test_production_rejects_missing_default_and_weak_secrets() (+1 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (28): PaginationMeta, get_user_profile_summary(), get_collaborative_recommendations_endpoint(), get_profile_analysis_endpoint(), get_profile_recommendations_endpoint(), get_profile_summary_endpoint(), get_similar_posts_endpoint(), get_trending_suggestions() (+20 more)

### Community 6 - "Community 6"
Cohesion: 0.14
Nodes (18): require_active_verified_user(), follow_user(), FollowResponse, unfollow_user(), build_profile_response(), CurrentProfileResponse, get_my_profile(), get_user_bookmarks() (+10 more)

### Community 7 - "Community 7"
Cohesion: 0.14
Nodes (6): create_app(), health_check(), register_middleware(), register_routers(), root(), test_factory_creates_independent_apps_without_io()

### Community 8 - "Community 8"
Cohesion: 0.21
Nodes (21): _activity_weight(), _affinity_score(), create_data(), _interaction_time(), _interest_set(), _lower(), _major_tag_hints(), _norm() (+13 more)

### Community 9 - "Community 9"
Cohesion: 0.14
Nodes (30): require_role(), Report, add_admin_audit_log(), AdminAnalyticsResponse, AdminPostModerationResponse, AdminPostsListResponse, AdminReportsListResponse, AdminUserResponse (+22 more)

### Community 10 - "Community 10"
Cohesion: 0.07
Nodes (21): ConfigurationError, hash_password(), get_db(), normalize_database_url(), main(), get_all_tags(), get_posts_by_tag(), create_admin() (+13 more)

### Community 12 - "Community 12"
Cohesion: 0.20
Nodes (3): register_exception_handlers(), unhandled_exception_handler(), validation_exception_handler()

## Knowledge Gaps
- **1 isolated node(s):** `uitconnect-backend`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 222 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **74 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `User` connect `Community 9` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 5`, `Community 6`, `Community 8`, `Community 10`?**
  _High betweenness centrality (0.185) - this node is a cross-community bridge._
- **Are the 81 inferred relationships involving `User` (e.g. with `get_current_user()` and `require_active_verified_user()`) actually correct?**
  _`User` has 81 INFERRED edges - model-reasoned connections that need verification._
- **What connects `uitconnect-backend` to the rest of the system?**
  _1 weakly-connected nodes found - possible missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.052941176470588235 - nodes in this community are weakly interconnected._
- **Why does `Post` connect `Community 2` to `Community 0`, `Community 3`, `Community 5`, `Community 6`, `Community 8`, `Community 9`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 37 inferred relationships involving `Post` (e.g. with `create_comment()` and `get_collaborative_recommendations()`) actually correct?**
  _`Post` has 37 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.0689873417721519 - nodes in this community are weakly interconnected._