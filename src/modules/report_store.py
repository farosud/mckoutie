"""
Simple file-based report store.
Tracks report status: pending → analyzing → ready → paid.
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
    author_id: str
    status: str = "pending"  # pending | analyzing | ready | paid | failed
    checkout_url: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())
    paid_at: str = ""
    error: str = ""


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
