import random
import re
from pathlib import Path

from .context import ContextStore
from .pet import PetService


class CommandHandler:
    def __init__(self, store, data_dir, pet=None):
        self.store: ContextStore = store
        self.data_dir = Path(data_dir)
        self.pet = pet or PetService(self.data_dir)

    async def handle(self, text, group_id, user_id, display_name):
        if "【帮助】" in text:
            return (
                "发送 @机器人 或人格关键词即可聊天。\n"
                "可用命令：`【清除历史】`、`【投掷】ndm`、`【rua】`。"
            )
        if "【清除历史】" in text:
            self.store.clear_history(group_id)
            return "已清除当前群的对话历史。"
        if "【投掷】" in text:
            match = re.search(r"【投掷】\s*(\d*)d\s*(\d+)", text, re.IGNORECASE)
            if not match:
                return "请使用 `【投掷】ndm`，例如 `【投掷】3d6`。"
            count = int(match.group(1) or "1")
            sides = int(match.group(2))
            if count <= 0 or sides <= 0:
                return "n 和 m 必须是正整数。"
            if count > 100:
                return "投掷数量请限制在100以内。"
            values = [random.randint(1, sides) for _ in range(count)]
            return f"你投掷了 {count} 个 1 到 {sides} 之间的随机数：" + ", ".join(
                map(str, values)
            )
        # if "【rua】" in text:
        #     user_text = text.split("【rua】", 1)[1].strip()
        #     return await self.pet.rua(user_id, display_name, user_text)
        return None
