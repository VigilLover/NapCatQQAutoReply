from itertools import islice

from napcat_qq_auto_reply.app import reconnect_delays


def test_reconnect_delays_are_bounded_exponential():
    assert list(islice(reconnect_delays(), 7)) == [1, 2, 4, 8, 16, 30, 30]
