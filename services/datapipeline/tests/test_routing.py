import os

import pytest

from services.datapipeline.routing import assign_variant, resolve_topic, DEFAULT_PERCENT_A


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    monkeypatch.delenv("AB_PIPELINE_A_PERCENT", raising=False)
    yield


def test_assign_variant_uses_env_percentage(monkeypatch):
    monkeypatch.setenv("AB_PIPELINE_A_PERCENT", "100")
    assert assign_variant("any-user") == "A"

    monkeypatch.setenv("AB_PIPELINE_A_PERCENT", "0")
    assert assign_variant("any-user") == "B"


def test_assign_variant_is_sticky_for_user():
    user_id = "user-123"
    first = assign_variant(user_id, percent_a=DEFAULT_PERCENT_A)
    for _ in range(10):
        assert assign_variant(user_id, percent_a=DEFAULT_PERCENT_A) == first


def test_assign_variant_distribution_reasonable():
    # With 50% A we expect roughly half the users in A.
    users = [f"user-{i}" for i in range(1000)]
    variants = [assign_variant(u, percent_a=50.0) for u in users]
    count_a = variants.count("A")

    # Just check it's within a broad band (30-70%)
    assert 300 <= count_a <= 700


def test_resolve_topic_returns_correct_suffix():
    topic_a, variant_a = resolve_topic("user-a", base_topic="events.v1", percent_a=100.0)
    assert topic_a.endswith(".control")
    assert variant_a == "A"

    topic_b, variant_b = resolve_topic("user-b", base_topic="events.v1", percent_a=0.0)
    assert topic_b.endswith(".experiment")
    assert variant_b == "B"

