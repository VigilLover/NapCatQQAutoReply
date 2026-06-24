from napcat_qq_auto_reply.onebot.parser import parse_group_event


def test_parse_mixed_onebot_segments():
    payload = {
        "post_type": "message",
        "message_type": "group",
        "group_id": 100,
        "message_id": 200,
        "user_id": 300,
        "sender": {"nickname": "小明", "card": "群名片"},
        "message": [
            {"type": "at", "data": {"qq": "42"}},
            {"type": "text", "data": {"text": " 你好 "}},
            {"type": "reply", "data": {"id": "199"}},
            {
                "type": "image",
                "data": {"file": "abc.jpg", "url": "https://example.invalid/a.jpg"},
            },
        ],
    }

    event = parse_group_event(payload)

    assert event is not None
    assert event.group_id == 100
    assert event.user.qq_id == 300
    assert event.user.display_name == "群名片"
    assert event.text == "你好"
    assert event.mentions == {42}
    assert event.reply_id == 199
    assert event.images[0].source == "https://example.invalid/a.jpg"


def test_ignore_non_group_message():
    assert parse_group_event({"post_type": "message", "message_type": "private"}) is None
