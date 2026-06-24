from pathlib import Path

import pytest

from napcat_qq_auto_reply.bot.commands import CommandHandler
from napcat_qq_auto_reply.bot.context import ContextStore
from napcat_qq_auto_reply.bot.pet import PetService
from napcat_qq_auto_reply.onebot.models import GroupEvent, QQUser


def make_event(group: int, index: int) -> GroupEvent:
    return GroupEvent(
        group_id=group,
        message_id=index,
        user=QQUser(qq_id=index, nickname=f"u{index}", card=None),
        text=f"m{index}",
    )


def test_context_limits_and_group_isolation():
    store = ContextStore(recent_limit=20, history_turn_limit=8)
    for index in range(25):
        store.add_event(make_event(1, index))
    store.add_event(make_event(2, 99))
    for index in range(10):
        store.add_turn(1, f"q{index}", f"a{index}")

    assert [item.text for item in store.recent(1)] == [f"m{i}" for i in range(5, 25)]
    assert [item.text for item in store.recent(2)] == ["m99"]
    assert store.history(1)[0] == ("q2", "a2")
    store.clear_history(1)
    assert store.history(1) == []
    assert len(store.recent(1)) == 20


@pytest.mark.asyncio
async def test_clear_and_roll_commands(tmp_path: Path):
    store = ContextStore()
    store.add_turn(1, "q", "a")
    commands = CommandHandler(store=store, data_dir=tmp_path)

    assert (await commands.handle("【清除历史】", group_id=1, user_id=2, display_name="u")) == "已清除当前群的对话历史。"
    assert store.history(1) == []
    assert "1 到 6" in (await commands.handle("【投掷】3d6", 1, 2, "u"))
    assert "100以内" in (await commands.handle("【投掷】101d6", 1, 2, "u"))


@pytest.mark.asyncio
async def test_rua_command_uses_pet_service(tmp_path: Path):
    class FakePet:
        async def rua(self, user_id, display_name, user_text):
            assert (user_id, display_name, user_text) == (2, "昵称", "轻轻摸摸")
            return "嗷呜~"

    commands = CommandHandler(ContextStore(), tmp_path, pet=FakePet())
    assert await commands.handle("【rua】轻轻摸摸", 1, 2, "昵称") == "嗷呜~"


@pytest.mark.asyncio
async def test_pet_service_persists_bounded_state(tmp_path: Path):
    pet = PetService(tmp_path)
    response = await pet.rua(2, "昵称", "")
    state = pet.load_state()
    assert "耐心" in response
    assert set(state) == {"patience", "wisdom", "chaos"}
    assert all(-100 <= value <= 100 for value in state.values())
    assert (tmp_path / "pet_state.json").exists()
