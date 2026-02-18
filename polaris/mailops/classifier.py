"""Rule-based classifier for MailOps categories."""

import re


class MailOpsClassifier:
    """Classify mail into urgent/action/info/promo with lightweight rules."""

    URGENT_PATTERNS = [
        r"\burgent\b",
        r"\basap\b",
        r"deadline",
        r"due\s+today",
        r"마감",
        r"긴급",
        r"즉시",
        r"final notice",
        r"payment failed",
    ]

    ACTION_PATTERNS = [
        r"\breply\b",
        r"\bplease\s+review\b",
        r"\brsvp\b",
        r"필요",
        r"확인해",
        r"요청",
        r"submit",
    ]

    PROMO_PATTERNS = [
        r"\bsale\b",
        r"\bdeal\b",
        r"\bdiscount\b",
        r"\bcoupon\b",
        r"프로모션",
        r"할인",
        r"특가",
        r"무료배송",
        r"limited time",
    ]

    def classify(self, message: dict) -> dict:
        """Return category, confidence, and short reason."""
        subject = (message.get("subject") or "").lower()
        sender = (message.get("sender") or "").lower()
        body = (message.get("body_preview") or message.get("content") or "").lower()
        text = f"{subject}\n{sender}\n{body}"

        if self._matches_any(text, self.URGENT_PATTERNS):
            return {
                "category": "urgent",
                "confidence": 0.92,
                "reason": "Matched urgent keyword pattern",
            }

        if self._is_promo_sender(sender) or self._matches_any(text, self.PROMO_PATTERNS):
            return {
                "category": "promo",
                "confidence": 0.88,
                "reason": "Promotion sender/keyword detected",
            }

        if self._matches_any(text, self.ACTION_PATTERNS):
            return {
                "category": "action",
                "confidence": 0.76,
                "reason": "Action-needed keywords detected",
            }

        return {
            "category": "info",
            "confidence": 0.65,
            "reason": "No urgent/action/promo pattern",
        }

    def _matches_any(self, text: str, patterns: list[str]) -> bool:
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _is_promo_sender(self, sender: str) -> bool:
        promo_sender_markers = [
            "noreply",
            "no-reply",
            "newsletter",
            "marketing",
            "deals",
            "offers",
            "coupon",
            "store",
        ]
        return any(marker in sender for marker in promo_sender_markers)
