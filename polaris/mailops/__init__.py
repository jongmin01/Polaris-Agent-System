"""MailOps package for multi-account Apple Mail ingest and triage."""

from .service import MailOpsService
from .poller import MailOpsPoller

__all__ = ["MailOpsService", "MailOpsPoller"]
