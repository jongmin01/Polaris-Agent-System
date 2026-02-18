"""Apple Mail ingest for MailOps."""

import hashlib
import logging
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def _provider_from_account(account_name: str) -> str:
    name = (account_name or "").lower()
    if "gmail" in name:
        return "gmail"
    if "outlook" in name or "uic" in name:
        return "outlook"
    return "mail"


def _make_account_id(account_keyword: str, account_name: str) -> str:
    base = account_name or account_keyword or "unknown"
    return base.lower().replace(" ", "_")


class MailOpsIngestor:
    """Ingest unread mail from multiple Apple Mail account keywords."""

    def __init__(self, account_keywords: list[str], reader_factory: Optional[Callable] = None):
        self.account_keywords = [k.strip() for k in account_keywords if k.strip()]
        self.reader_factory = reader_factory or self._default_reader_factory

    def _default_reader_factory(self, account_keyword: str):
        from mail_reader import MailReader

        return MailReader(account_keyword=account_keyword)

    def fetch_unread(self, limit_per_account: int = 20) -> list[dict]:
        collected: list[dict] = []
        for keyword in self.account_keywords:
            try:
                reader = self.reader_factory(keyword)
                mails = reader.get_unread_mails(limit=limit_per_account)
                for mail in mails:
                    collected.append(self._normalize(mail, keyword))
            except Exception as e:
                logger.warning("Mail ingest failed for account keyword '%s': %s", keyword, e)
                continue
        return collected

    def _normalize(self, mail: dict, account_keyword: str) -> dict:
        account_name = mail.get("account", "")
        sender = mail.get("sender", "")
        subject = mail.get("subject", "")
        content = mail.get("content", "")
        date_str = mail.get("date", "")

        # Apple Mail script does not expose message-id. Hash with stable fields.
        hash_input = f"{account_name}|{sender}|{subject}|{date_str}|{content[:160]}"
        ext_id = hashlib.sha1(hash_input.encode("utf-8")).hexdigest()

        return {
            "ext_id": ext_id,
            "thread_id": "",
            "account_id": _make_account_id(account_keyword, account_name),
            "provider": _provider_from_account(account_name),
            "sender": sender,
            "subject": subject,
            "body_preview": content[:500],
            "received_at": date_str or datetime.utcnow().isoformat(),
            "is_unread": True,
            "raw": mail,
        }
