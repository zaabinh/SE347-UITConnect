"""Compatibility exports for report reason normalization."""

from app.modules.moderation.domain import STANDARD_REPORT_REASONS, normalize_report_reason

__all__ = ["STANDARD_REPORT_REASONS", "normalize_report_reason"]
