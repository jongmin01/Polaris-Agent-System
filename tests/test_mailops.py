"""Tests for MailOps R1 modules."""

import json

from polaris.mailops.classifier import MailOpsClassifier
from polaris.mailops.service import MailOpsService
from polaris.mailops.store import MailOpsStore


class _FakeIngestor:
    def __init__(self, rows):
        self.rows = rows

    def fetch_unread(self, limit_per_account=20):
        return self.rows[:limit_per_account]


def _mail(ext_id: str, subject: str, sender: str, body_preview: str, account_id: str = "uic"):
    return {
        "ext_id": ext_id,
        "thread_id": "",
        "account_id": account_id,
        "provider": "mail",
        "sender": sender,
        "subject": subject,
        "body_preview": body_preview,
        "received_at": "2026-02-17T09:00:00",
        "is_unread": True,
    }


def test_classifier_categories():
    cls = MailOpsClassifier()
    urgent = cls.classify({"subject": "URGENT deadline today", "sender": "prof@uic.edu", "body_preview": ""})
    promo = cls.classify({"subject": "50% deal coupon", "sender": "newsletter@store.com", "body_preview": ""})
    action = cls.classify({"subject": "Please review this", "sender": "student@uic.edu", "body_preview": ""})
    info = cls.classify({"subject": "Weekly update", "sender": "dept@uic.edu", "body_preview": "announcement"})

    assert urgent["category"] == "urgent"
    assert promo["category"] == "promo"
    assert action["category"] == "action"
    assert info["category"] == "info"


def test_mailops_sync_and_digest(tmp_path):
    store = MailOpsStore(str(tmp_path / "mailops.db"))
    rows = [
        _mail("m1", "URGENT payment failed", "billing@service.com", "fix now", "gmail_us"),
        _mail("m2", "Big sale today", "newsletter@shop.com", "coupon inside", "gmail_kr"),
        _mail("m3", "Please review homework", "student@uic.edu", "need reply", "uic"),
    ]
    service = MailOpsService(store=store, classifier=MailOpsClassifier(), ingestor=_FakeIngestor(rows))

    result = service.sync_unread()
    digest = service.get_digest(limit=10)
    urgent = service.get_urgent(limit=10)
    promo = service.get_promo(limit=10)

    assert result["fetched"] == 3
    assert result["inserted"] == 3
    assert len(digest) == 3
    assert len(urgent) == 1
    assert len(promo) == 1


def test_unalerted_urgent_tracking(tmp_path):
    store = MailOpsStore(str(tmp_path / "mailops.db"))
    rows = [_mail("m1", "URGENT deadline", "prof@uic.edu", "today")]
    service = MailOpsService(store=store, classifier=MailOpsClassifier(), ingestor=_FakeIngestor(rows))
    service.sync_unread()

    first = service.list_unalerted_urgent(limit=5)
    assert len(first) == 1

    service.mark_urgent_alerted(first[0]["ext_id"])
    second = service.list_unalerted_urgent(limit=5)
    assert second == []


def test_tools_mailops_registered_and_callable(tmp_path, monkeypatch):
    from polaris.tools.mailops_tools import handle_fetch_mail_digest

    class _Svc:
        def sync_unread(self, limit_per_account=20):
            return {"fetched": 0, "inserted": 0, "urgent_new": 0}

        def get_digest(self, limit=20):
            return [{"ext_id": "m1", "subject": "hello"}]

    monkeypatch.setattr("polaris.tools.mailops_tools.MailOpsService", lambda: _Svc())

    result = handle_fetch_mail_digest(limit=5, sync_first=True)
    parsed = json.loads(result)
    assert parsed["count"] == 1
