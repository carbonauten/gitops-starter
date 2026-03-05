"""Tests for the datapipeline Kafka consumer."""
from unittest.mock import patch

import pytest

from consumer import get_config, main


def test_get_config_defaults(monkeypatch):
    monkeypatch.delenv("KAFKA_BROKERS", raising=False)
    monkeypatch.delenv("KAFKA_TOPIC", raising=False)
    monkeypatch.delenv("KAFKA_CONSUMER_GROUP", raising=False)
    monkeypatch.delenv("PIPELINE_VARIANT", raising=False)
    cfg = get_config()
    assert cfg["brokers"] == "localhost:9092"
    assert cfg["topic"] == "events.v1.control"
    assert cfg["group"] == "datapipeline-consumer"
    assert cfg["variant"] == "A"


def test_get_config_from_env(monkeypatch):
    monkeypatch.setenv("KAFKA_BROKERS", "kafka:9092")
    monkeypatch.setenv("KAFKA_TOPIC", "events.v1.experiment")
    monkeypatch.setenv("KAFKA_CONSUMER_GROUP", "my-group")
    monkeypatch.setenv("PIPELINE_VARIANT", "B")
    cfg = get_config()
    assert cfg["brokers"] == "kafka:9092"
    assert cfg["topic"] == "events.v1.experiment"
    assert cfg["group"] == "my-group"
    assert cfg["variant"] == "B"


def test_main_exits_when_kafka_connection_fails(monkeypatch):
    from kafka.errors import KafkaError

    monkeypatch.setenv("KAFKA_BROKERS", "kafka:9092")
    monkeypatch.setenv("KAFKA_TOPIC", "events.v1.control")
    monkeypatch.setenv("KAFKA_CONSUMER_GROUP", "cg")
    monkeypatch.setenv("PIPELINE_VARIANT", "A")

    with patch("consumer.KafkaConsumer") as mock_consumer:
        mock_consumer.side_effect = KafkaError("connection refused")
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
