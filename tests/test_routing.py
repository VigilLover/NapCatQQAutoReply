from napcat_qq_auto_reply.bot.routing import MessageRouter
from napcat_qq_auto_reply.onebot.models import GroupEvent, QQUser


def event(*, group=100, user=300, text="你好", mentions=frozenset(), message_id=1):
    return GroupEvent(
        group_id=group,
        message_id=message_id,
        user=QQUser(qq_id=user, nickname="u", card=None),
        text=text,
        mentions=set(mentions),
    )


def test_router_accepts_allowlisted_mention_and_strips_trigger():
    router = MessageRouter({100}, {"【小狼】"})
    result = router.route(event(text=" @bot 你好", mentions={42}), bot_id=42)
    assert result is not None
    assert result.prompt == "你好"


def test_router_accepts_persona_keyword():
    router = MessageRouter({100}, {"【小狼】"})
    result = router.route(event(text="【小狼】 晚上好"), bot_id=42)
    assert result is not None
    assert result.prompt == "晚上好"


def test_router_rejects_other_groups_self_and_duplicates():
    router = MessageRouter({100}, {"【小狼】"})
    assert router.route(event(group=101, text="【小狼】 hi"), bot_id=42) is None
    assert router.route(event(user=42, text="【小狼】 hi"), bot_id=42) is None
    accepted = event(text="【小狼】 hi", message_id=9)
    assert router.route(accepted, bot_id=42) is not None
    assert router.route(accepted, bot_id=42) is None
