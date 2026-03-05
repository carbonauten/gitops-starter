#!/usr/bin/env python3
"""
Kafka consumer for the data pipeline (A/B control/experiment topics).
Reads KAFKA_BROKERS, KAFKA_TOPIC, KAFKA_CONSUMER_GROUP, PIPELINE_VARIANT from env.
"""
import json
import logging
import os
import signal
import sys

from kafka import KafkaConsumer
from kafka.errors import KafkaError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

SHUTDOWN = False


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    if not value and name.startswith("KAFKA_"):
        logger.warning("Missing env %s", name)
    return value


def get_config() -> dict:
    """Return consumer config from env (used by tests)."""
    return {
        "brokers": _env("KAFKA_BROKERS", "localhost:9092"),
        "topic": _env("KAFKA_TOPIC", "events.v1.control"),
        "group": _env("KAFKA_CONSUMER_GROUP", "datapipeline-consumer"),
        "variant": _env("PIPELINE_VARIANT", "A"),
    }


def main() -> None:
    global SHUTDOWN

    def on_signal(_signum, _frame):  # noqa: ARG001
        nonlocal SHUTDOWN
        SHUTDOWN = True

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    cfg = get_config()
    brokers = cfg["brokers"]
    topic = cfg["topic"]
    group = cfg["group"]
    variant = cfg["variant"]

    logger.info(
        "Starting consumer variant=%s topic=%s group=%s brokers=%s",
        variant,
        topic,
        group,
        brokers,
    )

    try:
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=brokers.split(","),
            group_id=group,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
    except KafkaError as e:
        logger.exception("Failed to create Kafka consumer: %s", e)
        sys.exit(1)

    try:
        for message in consumer:
            if SHUTDOWN:
                break
            try:
                body = message.value
                if body:
                    try:
                        payload = json.loads(body.decode("utf-8"))
                        logger.info("variant=%s key=%s payload=%s", variant, message.key, payload)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        logger.info("variant=%s key=%s raw=%s", variant, message.key, body[:200])
                else:
                    logger.debug("variant=%s empty message", variant)
            except Exception as e:  # noqa: BLE001
                logger.warning("Error processing message: %s", e)
    finally:
        consumer.close()
        logger.info("Consumer stopped.")


if __name__ == "__main__":
    main()
