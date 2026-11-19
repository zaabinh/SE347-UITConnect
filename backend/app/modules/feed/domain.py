"""Pure scoring and text rules used by feed recommendations."""

import math
import re
from datetime import datetime
from collections import Counter
from app.modules.posts.models import Post


def calculate_time_decay(created_at: datetime, hours_old: float = 24) -> float:
    """
    Tính decay score dựa trên tuổi của bài viết.
    Bài viết mới nhất = 1.0, bài viết cũ = 0.1
    """
    now = datetime.utcnow()
    age_hours = (now - created_at).total_seconds() / 3600

    if age_hours < 0:
        return 1.0

    # Exponential decay: e^(-age/24)
    decay = math.exp(-age_hours / hours_old)
    return max(0.1, min(1.0, decay))  # Giữa 0.1 - 1.0



def calculate_trending_score(
    likes_count: int,
    comments_count: int,
    views_count: int,
    shares_count: int,
    created_at: datetime,
    decay_factor: bool = True
) -> float:
    """
    Tính điểm xu hướng của bài viết.

    Công thức:
    - Cơ sở: likes*4 + comments*3 + views*0.5 + shares*2
    - Nếu decay_factor=True: nhân với time decay
    """
    base_score = (
        likes_count * 4 +
        comments_count * 3 +
        views_count * 0.5 +
        shares_count * 2
    )

    if decay_factor:
        time_decay = calculate_time_decay(created_at)
        return base_score * time_decay

    return base_score



def get_trending_reason(
    likes_count: int,
    comments_count: int,
    views_count: int,
    shares_count: int
) -> str:
    """Xác định lý do bài viết trending"""
    stats = [
        ("yêu thích", likes_count),
        ("bình luận", comments_count),
        ("chia sẻ", shares_count),
        ("lượt xem", views_count)
    ]

    # Sắp xếp theo giá trị giảm dần
    stats.sort(key=lambda x: x[1], reverse=True)

    if stats[0][1] > 0:
        return f"Nổi bật do {stats[0][0]}"
    return "Bài viết mới"



def preprocess_text(text: str) -> list[str]:
    """
    Chuẩn hóa text: chuyển thành lowercase, loại bỏ ký tự đặc biệt.
    Trả về danh sách từ khóa.
    """
    if not text:
        return []

    text = text.lower()
    # Loại bỏ ký tự đặc biệt, chỉ giữ chữ, số và khoảng trắng
    text = re.sub(r"[^\w\s]", " ", text)
    # Loại bỏ khoảng trắng dôi dư
    words = text.split()

    # Loại bỏ stop words tiếng Việt/Anh phổ biến
    stop_words = {
        "the", "a", "an", "is", "are", "in", "on", "at", "to", "for", "of",
        "và", "hay", "hoặc", "là", "với", "cái", "chiếc", "những"
    }

    return [word for word in words if word not in stop_words and len(word) > 2]



def calculate_tag_similarity(post1_tags: set[str], post2_tags: set[str]) -> float:
    """
    Tính độ tương đồng giữa 2 tập tag sử dụng Jaccard similarity.
    Công thức: |A ∩ B| / |A ∪ B|
    """
    if not post1_tags and not post2_tags:
        return 0.0

    if not post1_tags or not post2_tags:
        return 0.0

    intersection = len(post1_tags & post2_tags)
    union = len(post1_tags | post2_tags)

    return intersection / union if union > 0 else 0.0



def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    Tính độ tương đồng giữa 2 đoạn text sử dụng TF (Term Frequency).
    Đơn giản hơn TF-IDF, dùng Cosine Similarity.
    """
    if not text1 or not text2:
        return 0.0

    words1 = preprocess_text(text1)
    words2 = preprocess_text(text2)

    if not words1 or not words2:
        return 0.0

    # Tạo vector tần suất
    freq1 = Counter(words1)
    freq2 = Counter(words2)

    # Tính dot product
    dot_product = sum(freq1[word] * freq2[word] for word in freq1 if word in freq2)

    # Tính magnitude
    magnitude1 = math.sqrt(sum(freq**2 for freq in freq1.values()))
    magnitude2 = math.sqrt(sum(freq**2 for freq in freq2.values()))

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    # Cosine similarity
    return dot_product / (magnitude1 * magnitude2)



def calculate_content_similarity(
    post1: Post,
    post2: Post,
    weights: dict | None = None
) -> tuple[float, str]:
    """
    Tính độ tương đồng toàn bộ giữa 2 bài viết.

    Args:
        post1: Bài viết 1
        post2: Bài viết 2
        weights: Trọng số cho từng thành phần
                 {'title': 0.3, 'content': 0.3, 'tags': 0.4}

    Returns:
        (similarity_score, reason)
    """
    if weights is None:
        weights = {"title": 0.2, "content": 0.4, "tags": 0.4}

    # Tương đồng title
    title_sim = calculate_text_similarity(post1.title, post2.title)

    # Tương đồng content
    content_sim = calculate_text_similarity(post1.content, post2.content)

    # Tương đồng tags
    tags1 = {tag.tag.name.lower() for tag in post1.tags if tag.tag}
    tags2 = {tag.tag.name.lower() for tag in post2.tags if tag.tag}
    tags_sim = calculate_tag_similarity(tags1, tags2)

    # Tính weighted average
    similarity = (
        weights["title"] * title_sim +
        weights["content"] * content_sim +
        weights["tags"] * tags_sim
    )

    # Xác định lý do
    reason = ""
    if tags_sim > 0.3:
        reason = "Cùng chủ đề"
    elif content_sim > 0.2:
        reason = "Nội dung tương tự"
    elif title_sim > 0.1:
        reason = "Tiêu đề liên quan"

    if not reason:
        reason = "Bài viết gợi ý"

    return similarity, reason



def _parse_interest_tags(raw_tags: str | None) -> set[str]:
    """Phân tích interest_tags từ string"""
    if not raw_tags:
        return set()
    return {tag.strip().lower() for tag in raw_tags.split(",") if tag.strip()}



def calculate_user_tag_similarity(tags1: set[str], tags2: set[str]) -> float:
    """
    Tính Jaccard similarity giữa 2 tập tag.
    Công thức: |A ∩ B| / |A ∪ B|
    """
    if not tags1 and not tags2:
        return 0.0
    if not tags1 or not tags2:
        return 0.0

    intersection = len(tags1 & tags2)
    union = len(tags1 | tags2)
    return intersection / union if union > 0 else 0.0



def calculate_post_overlap(
    user1_liked: set[int],
    user2_liked: set[int]
) -> float:
    """
    Tính % overlap giữa bài viết mà 2 user yêu thích.
    Công thức: |A ∩ B| / max(|A|, |B|)
    """
    if not user1_liked and not user2_liked:
        return 0.0
    if not user1_liked or not user2_liked:
        return 0.0

    intersection = len(user1_liked & user2_liked)
    max_size = max(len(user1_liked), len(user2_liked))
    return intersection / max_size if max_size > 0 else 0.0



def calculate_follow_overlap(
    user1_follows: set[str],
    user2_follows: set[str]
) -> float:
    """
    Tính overlap giữa những user mà 2 user theo dõi.
    Công thức: |A ∩ B| / max(|A|, |B|)
    """
    if not user1_follows and not user2_follows:
        return 0.0
    if not user1_follows or not user2_follows:
        return 0.0

    intersection = len(user1_follows & user2_follows)
    max_size = max(len(user1_follows), len(user2_follows))
    return intersection / max_size if max_size > 0 else 0.0



def _parse_tags_from_string(raw_tags: str | None) -> set[str]:
    """Phân tích tags từ chuỗi comma-separated"""
    if not raw_tags:
        return set()
    return {tag.strip().lower() for tag in raw_tags.split(",") if tag.strip()}



def _extract_keywords_from_text(text: str | None, max_words: int = 5) -> list[str]:
    """Trích xuất keywords từ text (loại bỏ stop words)"""
    if not text:
        return []

    # Stop words tiếng Việt/Anh
    stop_words = {
        "the", "a", "an", "is", "are", "in", "on", "at", "to", "for", "of",
        "và", "hay", "hoặc", "là", "với", "cái", "chiếc", "những",
        "em", "bạn", "tôi", "anh", "chị", "nó", "họ"
    }

    # Chuyển thành lowercase, loại bỏ ký tự đặc biệt
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    words = text.split()

    # Lọc stop words và từ quá ngắn
    keywords = [
        word for word in words
        if word not in stop_words and len(word) > 2
    ]

    # Đếm tần suất
    word_freq = Counter(keywords)
    # Lấy top words
    return [word for word, _ in word_freq.most_common(max_words)]



def calculate_profile_relevance_score(
    post: Post,
    profile_info: dict,
    weights: dict | None = None
) -> tuple[float, str]:
    """
    Tính điểm liên quan giữa bài viết và profile user.

    Trọng số:
    - Tags trực tiếp: 40%
    - Từ khóa text: 30%
    - Hành vi (like/comment): 30%

    Returns:
        (score, reason)
    """
    if weights is None:
        weights = {
            "direct_tags": 0.40,
            "keywords": 0.30,
            "behavior_tags": 0.30
        }

    # Lấy tags của bài viết
    post_tags = {tag.tag.name.lower() for tag in post.tags if tag.tag}

    # 1. Direct tags match (interest_tags)
    interest_tags = profile_info.get("interest_tags", set())
    direct_overlap = len(post_tags & interest_tags)
    max_direct = max(len(post_tags), len(interest_tags)) if (post_tags or interest_tags) else 1
    direct_score = direct_overlap / max_direct if max_direct > 0 else 0

    # 2. Keywords match (từ major, career_goal, bio)
    keywords = set(profile_info.get("keywords", []))
    post_text = (post.title + " " + post.content).lower()
    keyword_matches = sum(1 for kw in keywords if kw in post_text)
    keywords_score = keyword_matches / len(keywords) if keywords else 0

    # 3. Behavior tags (bài user đã like/comment)
    liked_tags = profile_info.get("liked_tags", set())
    commented_tags = profile_info.get("commented_tags", set())
    behavior_tags = liked_tags | commented_tags

    behavior_overlap = len(post_tags & behavior_tags)
    max_behavior = max(len(post_tags), len(behavior_tags)) if (post_tags or behavior_tags) else 1
    behavior_score = behavior_overlap / max_behavior if max_behavior > 0 else 0

    # Weighted score
    score = (
        weights["direct_tags"] * direct_score +
        weights["keywords"] * keywords_score +
        weights["behavior_tags"] * behavior_score
    )

    # Xác định lý do
    reason = ""
    if direct_score > 0.3:
        reason = "Liên quan đến sở thích của bạn"
    elif keyword_matches > 0:
        reason = "Liên quan đến mục tiêu sự nghiệp"
    elif behavior_score > 0.2:
        reason = "Dựa trên bài viết bạn đã yêu thích"
    else:
        reason = "Đề xuất dựa trên profile"

    return score, reason



