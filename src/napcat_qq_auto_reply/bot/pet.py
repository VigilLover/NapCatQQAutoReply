import asyncio
import json
import random
from pathlib import Path


class PetService:
    MOODS = (
        ("开心", "嗷呜，被rua得很舒服。", {"patience": 3, "wisdom": 1, "chaos": -1}),
        ("害羞", "耳朵抖了一下……只许再摸一会儿。", {"patience": 1, "wisdom": 0, "chaos": 2}),
        ("困倦", "小狼缩成一团，含糊地哼了一声。", {"patience": 2, "wisdom": -1, "chaos": 0}),
        ("警觉", "尾巴一炸：你这手法是不是有点可疑？", {"patience": -2, "wisdom": 2, "chaos": 2}),
    )

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.data_dir / "pet_state.json"
        self._lock = asyncio.Lock()

    def load_state(self) -> dict[str, int]:
        default = {"patience": 0, "wisdom": 0, "chaos": 0}
        if not self.state_path.exists():
            return default
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            return {key: max(-100, min(100, int(raw.get(key, 0)))) for key in default}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return default

    def _save_state(self, state: dict[str, int]) -> None:
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _bar(value: int) -> str:
        filled = max(0, min(10, round((value + 100) / 20)))
        return "■" * filled + "□" * (10 - filled)

    async def rua(self, user_id: int, display_name: str, user_text: str) -> str:
        del user_id
        async with self._lock:
            state = self.load_state()
            mood, default_text, deltas = random.choice(self.MOODS)
            for key, delta in deltas.items():
                state[key] = max(-100, min(100, state[key] + delta + random.randint(-1, 1)))
            self._save_state(state)
        action = user_text.strip()
        prefix = f"{display_name}{action}" if action else display_name
        return (
            f"【{mood}】{prefix}rua了小狼。{default_text}\n"
            f"耐心 [{self._bar(state['patience'])}] {state['patience']}\n"
            f"智慧 [{self._bar(state['wisdom'])}] {state['wisdom']}\n"
            f"混沌 [{self._bar(state['chaos'])}] {state['chaos']}"
        )
