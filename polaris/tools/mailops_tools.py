"""MailOps tools for multi-account mail digest and triage."""

import json

from polaris.mailops import MailOpsService


TOOLS = [
    {
        "name": "fetch_mail_digest",
        "description": "Apple Mail 통합 메일 요약 조회 (Outlook UIC + Gmail KR/US).",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max rows (default: 20)"},
                "sync_first": {"type": "boolean", "description": "Sync unread mail before digest"},
            },
            "required": [],
        },
    },
    {
        "name": "fetch_urgent_mails",
        "description": "urgent 카테고리 메일 조회.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max rows (default: 20)"},
                "sync_first": {"type": "boolean", "description": "Sync unread mail before query"},
            },
            "required": [],
        },
    },
    {
        "name": "fetch_promo_deals",
        "description": "promo(딜/프로모션) 메일 조회.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max rows (default: 20)"},
                "sync_first": {"type": "boolean", "description": "Sync unread mail before query"},
            },
            "required": [],
        },
    },
    {
        "name": "propose_mail_actions",
        "description": "메일 액션 제안 생성 (archive/label/mark_read).",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "promo|urgent|all"},
                "limit": {"type": "integer", "description": "Max proposals"},
            },
            "required": [],
        },
    },
    {
        "name": "execute_mail_actions",
        "description": "R1 안전 액션 실행(archive/label/mark_read). 삭제는 미지원.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "archive|label|mark_read"},
                "message_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Target ext_id list",
                },
                "label": {"type": "string", "description": "Label name for label action"},
            },
            "required": ["action", "message_ids"],
        },
    },
]


def _service() -> MailOpsService:
    return MailOpsService()


def handle_fetch_mail_digest(limit: int = 20, sync_first: bool = True) -> str:
    service = _service()
    if sync_first:
        sync = service.sync_unread(limit_per_account=20)
    else:
        sync = {"status": "skipped"}
    rows = service.get_digest(limit=limit)
    return json.dumps({"sync": sync, "items": rows, "count": len(rows)}, default=str)


def handle_fetch_urgent_mails(limit: int = 20, sync_first: bool = True) -> str:
    service = _service()
    if sync_first:
        sync = service.sync_unread(limit_per_account=20)
    else:
        sync = {"status": "skipped"}
    rows = service.get_urgent(limit=limit)
    return json.dumps({"sync": sync, "items": rows, "count": len(rows)}, default=str)


def handle_fetch_promo_deals(limit: int = 20, sync_first: bool = True) -> str:
    service = _service()
    if sync_first:
        sync = service.sync_unread(limit_per_account=20)
    else:
        sync = {"status": "skipped"}
    rows = service.get_promo(limit=limit)
    return json.dumps({"sync": sync, "items": rows, "count": len(rows)}, default=str)


def handle_propose_mail_actions(target: str = "promo", limit: int = 20) -> str:
    service = _service()
    proposals = service.propose_actions(target=target, limit=limit)
    return json.dumps({"target": target, "proposals": proposals, "count": len(proposals)}, default=str)


def handle_execute_mail_actions(action: str, message_ids: list, label: str = "") -> str:
    service = _service()
    result = service.execute_actions(action=action, message_ids=message_ids, label=label)
    return json.dumps(result, default=str)


HANDLERS = {
    "fetch_mail_digest": handle_fetch_mail_digest,
    "fetch_urgent_mails": handle_fetch_urgent_mails,
    "fetch_promo_deals": handle_fetch_promo_deals,
    "propose_mail_actions": handle_propose_mail_actions,
    "execute_mail_actions": handle_execute_mail_actions,
}
