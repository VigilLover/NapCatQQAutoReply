from collections import defaultdict, deque

from napcat_qq_auto_reply.onebot.models import GroupEvent


class ContextStore:
    def __init__(self, recent_limit=20, history_turn_limit=8):
        self.recent_limit = recent_limit
        self.history_turn_limit = history_turn_limit
        self._recent: dict[int, deque[GroupEvent]] = defaultdict(
            lambda: deque(maxlen=self.recent_limit)
        )
        self._history: dict[int, deque[tuple[str, str]]] = defaultdict(
            lambda: deque(maxlen=self.history_turn_limit)
        )

    def add_event(self, event: GroupEvent) -> None:
        if any(item.message_id == event.message_id for item in self._recent[event.group_id]):
            return
        self._recent[event.group_id].append(event)

    def recent(self, group_id: int) -> list[GroupEvent]:
        return list(self._recent[group_id])

    def add_turn(self, group_id: int, prompt: str, response: str) -> None:
        self._history[group_id].append((prompt, response))

    def history(self, group_id: int) -> list[tuple[str, str]]:
        return list(self._history[group_id])

    def clear_history(self, group_id: int) -> None:
        self._history.pop(group_id, None)
