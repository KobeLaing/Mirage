from app.ratelimit import InMemoryRateLimiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_sliding_window():
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock)
    assert limiter.hit("u1:vote", 2, 60) is None
    assert limiter.hit("u1:vote", 2, 60) is None
    retry = limiter.hit("u1:vote", 2, 60)
    assert retry == 60
    assert limiter.hit("u2:vote", 2, 60) is None  # separate key

    clock.now += 30
    assert limiter.hit("u1:vote", 2, 60) == 30
    clock.now += 30.001
    assert limiter.hit("u1:vote", 2, 60) is None  # oldest hits expired
