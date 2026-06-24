from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class QQUser:
    qq_id: int
    nickname: str
    card: str | None = None

    @property
    def display_name(self) -> str:
        return self.card or self.nickname or str(self.qq_id)


@dataclass(frozen=True, slots=True)
class InboundImage:
    source: str
    file_name: str = ""


@dataclass(frozen=True, slots=True)
class LocalImage:
    path: Path
    mime_type: str = "image/jpeg"


@dataclass(frozen=True, slots=True)
class GroupEvent:
    group_id: int
    message_id: int
    user: QQUser
    text: str
    mentions: set[int] = field(default_factory=set)
    reply_id: int | None = None
    images: tuple[InboundImage, ...] = ()


@dataclass(frozen=True, slots=True)
class BotResponse:
    text: str
    attachments: tuple[LocalImage, ...] = ()
