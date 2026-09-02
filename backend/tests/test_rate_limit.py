import pytest

from app.core.rate_limit import RateLimitError, SlidingWindowRateLimiter


def test_allows_attempts_up_to_the_limit():
    limiter = SlidingWindowRateLimiter(max_attempts=3, window_seconds=60)
    for _ in range(3):
        limiter.check("1.2.3.4")


def test_rejects_the_next_attempt_once_the_limit_is_reached():
    limiter = SlidingWindowRateLimiter(max_attempts=3, window_seconds=60)
    for _ in range(3):
        limiter.check("1.2.3.4")
    with pytest.raises(RateLimitError):
        limiter.check("1.2.3.4")


def test_different_keys_have_independent_buckets():
    limiter = SlidingWindowRateLimiter(max_attempts=1, window_seconds=60)
    limiter.check("1.2.3.4:a@example.com")
    limiter.check("1.2.3.4:b@example.com")  # different email, same IP -> unaffected
    with pytest.raises(RateLimitError):
        limiter.check("1.2.3.4:a@example.com")


def test_old_attempts_fall_out_of_the_window():
    limiter = SlidingWindowRateLimiter(max_attempts=1, window_seconds=0.05)
    limiter.check("1.2.3.4")
    with pytest.raises(RateLimitError):
        limiter.check("1.2.3.4")

    import time

    time.sleep(0.1)
    limiter.check("1.2.3.4")  # window has elapsed, so this succeeds
