# gitops-starter-datapipeline

Small Python library for A/B routing in a data pipeline.

## Features

- Deterministic assignment of users to variants A/B based on `user_id`.
- Environment-controlled percentage split via `AB_PIPELINE_A_PERCENT`.
- Topic resolution helper to route messages to control vs experiment topics.

## Usage

```python
from datapipeline.routing import resolve_topic

topic, variant = resolve_topic("user-123", base_topic="events.v1")
# topic -> "events.v1.control" or "events.v1.experiment"
```

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Consumer deployment

The **datapipeline consumer** (Kafka consumer for control/experiment topics) is deployed via the main [gitops-starter](https://github.com/carbonauten/gitops-starter) repo: Helm chart `gitops/charts/datapipeline-consumer` and Argo CD Application `platform/argocd/datapipeline-consumer-application.yaml`. Producers can use this library’s `resolve_topic()` to publish to the same topic names the consumer subscribes to.

