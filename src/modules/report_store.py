"""
File-based report store with subscription tracking.
Tracks report status: pending → analyzing → ready → active (subscribed).
Associates reports with Twitter users for access control.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"


@dataclass
class ReportRecord:
    report_id: str
    startup_name: str
    target: str  # URL or @handle
    tweet_id: str
    author_username: str
    author_id: str  # Twitter user ID of requester
    status: str = "pending"  # pending | analyzing | ready | active | canceled | failed
    checkout_url: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())
    paid_at: str = ""
    last_updated_at: str = ""  # when the report was last refreshed with new data
    update_count: int = 0  # how many times the report has been updated
    error: str = ""
    # Subscription fields
    subscription_id: str = ""  # Stripe subscription ID
    customer_id: str = ""  # Stripe customer ID
    subscriber_twitter_id: str = ""  # Twitter ID of the paying subscriber
    tier: str = ""  # starter | growth | enterprise


def _record_path(report_id: str) -> Path:
    return REPORTS_DIR / report_id / "record.json"


def save_record(record: ReportRecord) -> None:
    path = _record_path(record.report_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(asdict(record), f, indent=2)


def load_record(report_id: str) -> ReportRecord | None:
    path = _record_path(report_id)
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    # Handle records created before new fields were added
    for fld in ("last_updated_at", "update_count", "subscription_id", "customer_id", "subscriber_twitter_id"):
        if fld not in data:
            data[fld] = "" if fld != "update_count" else 0
    return ReportRecord(**data)


def update_status(report_id: str, status: str, **kwargs) -> ReportRecord | None:
    record = load_record(report_id)
    if not record:
        return None
    record.status = status
    for k, v in kwargs.items():
        if hasattr(record, k):
            setattr(record, k, v)
    save_record(record)
    return record


def find_reports_by_twitter_id(twitter_id: str) -> list[ReportRecord]:
    """Find all reports owned by a specific Twitter user (requester or subscriber)."""
    results = []
    if not REPORTS_DIR.exists():
        return results
    for d in REPORTS_DIR.iterdir():
        if d.is_dir():
            record = load_record(d.name)
            if record and (record.author_id == twitter_id or record.subscriber_twitter_id == twitter_id):
                results.append(record)
    return sorted(results, key=lambda r: r.created_at, reverse=True)


def find_active_subscriptions() -> list[ReportRecord]:
    """Find all reports with active subscriptions (for periodic updates)."""
    results = []
    if not REPORTS_DIR.exists():
        return results
    for d in REPORTS_DIR.iterdir():
        if d.is_dir():
            record = load_record(d.name)
            if record and record.status == "active" and record.subscription_id:
                results.append(record)
    return results


def list_reports(status: str | None = None) -> list[ReportRecord]:
    """List all reports, optionally filtered by status."""
    records = []
    if not REPORTS_DIR.exists():
        return records
    for d in REPORTS_DIR.iterdir():
        if d.is_dir():
            record = load_record(d.name)
            if record and (status is None or record.status == status):
                records.append(record)
    return sorted(records, key=lambda r: r.created_at, reverse=True)
