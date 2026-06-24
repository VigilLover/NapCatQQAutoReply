from collections.abc import Mapping, Sequence

from .models import GroupEvent, InboundImage, QQUser


def _as_int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def parse_group_event(payload: Mapping[str, object]) -> GroupEvent | None:
    if payload.get("post_type") != "message" or payload.get("message_type") != "group":
        return None

    group_id = _as_int(payload.get("group_id"))
    message_id = _as_int(payload.get("message_id"))
    user_id = _as_int(payload.get("user_id"))
    if group_id is None or message_id is None or user_id is None:
        return None

    sender = payload.get("sender")
    sender = sender if isinstance(sender, Mapping) else {}
    nickname = str(sender.get("nickname") or user_id)
    card = str(sender.get("card") or "").strip() or None

    text_parts: list[str] = []
    mentions: set[int] = set()
    reply_id: int | None = None
    images: list[InboundImage] = []
    segments = payload.get("message")
    if isinstance(segments, str):
        text_parts.append(segments)
    elif isinstance(segments, Sequence):
        for segment in segments:
            if not isinstance(segment, Mapping):
                continue
            segment_type = segment.get("type")
            data = segment.get("data")
            data = data if isinstance(data, Mapping) else {}
            if segment_type == "text":
                text_parts.append(str(data.get("text") or ""))
            elif segment_type == "at":
                mention = _as_int(data.get("qq"))
                if mention is not None:
                    mentions.add(mention)
            elif segment_type == "reply":
                reply_id = _as_int(data.get("id"))
            elif segment_type == "image":
                source = str(data.get("url") or data.get("file") or "").strip()
                if source:
                    images.append(
                        InboundImage(source=source, file_name=str(data.get("file") or ""))
                    )

    return GroupEvent(
        group_id=group_id,
        message_id=message_id,
        user=QQUser(qq_id=user_id, nickname=nickname, card=card),
        text="".join(text_parts).strip(),
        mentions=mentions,
        reply_id=reply_id,
        images=tuple(images),
    )
