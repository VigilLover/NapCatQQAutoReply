from dataclasses import dataclass
from collections import OrderedDict
import re
import time

from napcat_qq_auto_reply.onebot.models import GroupEvent


@dataclass(frozen=True)
class RoutedMessage:
    prompt: str
    event: GroupEvent


class MessageRouter:
    def __init__(
        self,
        allowed_groups: set[int],
        trigger_words: set[str],
        *,
        dedupe_ttl_seconds: float = 600,
    ):
        self.allowed_groups = allowed_groups
        self.trigger_words = {word for word in trigger_words if word}
        self.dedupe_ttl_seconds = dedupe_ttl_seconds
        self._seen: OrderedDict[int, float] = OrderedDict()

    def route(self, event: GroupEvent, bot_id: int) -> RoutedMessage | None:
        if event.group_id not in self.allowed_groups or event.user.qq_id == bot_id:
            return None
        now = time.monotonic()
        while self._seen and next(iter(self._seen.values())) < now - self.dedupe_ttl_seconds:
            self._seen.popitem(last=False)
        if event.message_id in self._seen:
            return None

        by_mention = bot_id in event.mentions
        matched_words = [word for word in self.trigger_words if word in event.text]
        if not by_mention and not matched_words:
            return None

        self._seen[event.message_id] = now
        prompt = event.text
        for word in matched_words:
            prompt = prompt.replace(word, "", 1)
        if by_mention:
            prompt = re.sub(r"@(?:bot|\S+)", "", prompt, count=1, flags=re.IGNORECASE)
        return RoutedMessage(prompt=prompt.strip(), event=event)
