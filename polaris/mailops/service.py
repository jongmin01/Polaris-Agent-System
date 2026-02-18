"""MailOps orchestration service."""

import os
from typing import Optional

from polaris.mailops.classifier import MailOpsClassifier
from polaris.mailops.ingest import MailOpsIngestor
from polaris.mailops.store import MailOpsStore


class MailOpsService:
    """Ingest, classify, summarize, and alert mail from Apple Mail."""

    def __init__(
        self,
        store: Optional[MailOpsStore] = None,
        classifier: Optional[MailOpsClassifier] = None,
        ingestor: Optional[MailOpsIngestor] = None,
    ):
        self.store = store or MailOpsStore()
        self.classifier = classifier or MailOpsClassifier()

        if ingestor is None:
            account_keywords = os.getenv(
                "POLARIS_MAILOPS_ACCOUNT_KEYWORDS",
                "*",
            )
            ingestor = MailOpsIngestor(account_keywords=account_keywords.split(","))
        self.ingestor = ingestor

    def sync_unread(self, limit_per_account: int = 20) -> dict:
        """Fetch unread mail from Apple Mail and persist triage results."""
        messages = self.ingestor.fetch_unread(limit_per_account=limit_per_account)
        inserted = 0
        urgent_new = 0
        for msg in messages:
            is_new = self.store.upsert_message(msg)
            if is_new:
                inserted += 1
            result = self.classifier.classify(msg)
            self.store.save_classification(
                ext_id=msg["ext_id"],
                category=result["category"],
                confidence=result["confidence"],
                reason=result["reason"],
            )
            if is_new and result["category"] == "urgent":
                urgent_new += 1

        return {
            "fetched": len(messages),
            "inserted": inserted,
            "urgent_new": urgent_new,
        }

    def get_digest(self, limit: int = 20) -> list:
        return self.store.get_digest(limit=limit)

    def get_urgent(self, limit: int = 20) -> list:
        return self.store.get_digest(category="urgent", limit=limit)

    def get_promo(self, limit: int = 20) -> list:
        return self.store.get_digest(category="promo", limit=limit)

    def list_unalerted_urgent(self, limit: int = 10) -> list:
        return self.store.list_unalerted_urgent(limit=limit)

    def mark_urgent_alerted(self, ext_id: str):
        self.store.mark_alerted(ext_id=ext_id, alert_type="urgent")

    def propose_actions(self, target: str = "promo", limit: int = 20) -> list[dict]:
        """Return safe action proposals without mutating mailbox."""
        if target == "urgent":
            items = self.get_urgent(limit=limit)
            action = "label"
            detail = "label=urgent_followup"
        elif target == "promo":
            items = self.get_promo(limit=limit)
            action = "archive"
            detail = "archive promotional messages"
        else:
            items = self.get_digest(limit=limit)
            action = "mark_read"
            detail = "mark informational messages as read"

        proposals = []
        for item in items:
            proposals.append(
                {
                    "ext_id": item["ext_id"],
                    "subject": item.get("subject", ""),
                    "sender": item.get("sender", ""),
                    "category": item.get("category", "info"),
                    "proposed_action": action,
                    "detail": detail,
                }
            )
        return proposals

    def execute_actions(self, action: str, message_ids: list[str], label: str = "") -> dict:
        """R1: safe write actions are logged as queued/manual.

        Apple Mail write operations are intentionally deferred for reliability.
        """
        if action not in {"archive", "label", "mark_read"}:
            self.store.log_action(action=action, status="rejected", detail="Action not allowed in R1")
            return {"status": "error", "message": "Action not allowed in R1"}

        for ext_id in message_ids:
            detail = label if action == "label" else "queued_manual"
            self.store.log_action(action=action, status="queued", detail=detail, ext_id=ext_id)

        return {
            "status": "ok",
            "action": action,
            "count": len(message_ids),
            "message": "Actions queued in log (manual mailbox write in next phase)",
        }
