from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, request

from plc_client import PLCClient, load_plc_config_from_env
from github_client import (
    get_repo,
    get_latest_release,
    list_repos,
    trigger_workflow,
)
from data_store import append as store_append, read_latest as store_read_latest


app = Flask(__name__)
plc_client = PLCClient(load_plc_config_from_env())


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/plc/config", methods=["GET"])
def get_plc_config():
    cfg = plc_client.config
    return (
        jsonify(
            {
                "host": cfg.host,
                "port": cfg.port,
                "unit_id": cfg.unit_id,
            }
        ),
        200,
    )


@app.route("/plc/read", methods=["POST"])
def plc_read():
    body = request.get_json(force=True, silent=True) or {}
    address = body.get("address")
    data_type = body.get("type", "int")

    if not address:
        return jsonify({"error": "address is required"}), 400

    value = plc_client.read_tag(address=address, data_type=data_type)
    return (
        jsonify(
            {
                "address": address,
                "type": data_type,
                "value": value,
            }
        ),
        200,
    )


@app.route("/plc/write", methods=["POST"])
def plc_write():
    body = request.get_json(force=True, silent=True) or {}
    address = body.get("address")
    data_type = body.get("type", "int")
    value = body.get("value")

    if not address:
        return jsonify({"error": "address is required"}), 400

    plc_client.write_tag(address=address, data_type=data_type, value=value)
    return (
        jsonify(
            {
                "address": address,
                "type": data_type,
                "value": value,
                "status": "accepted",
            }
        ),
        202,
    )


# --- GitHub bridge (option 2: PLC -> this API -> GitHub). Set GITHUB_TOKEN in env. ---


@app.route("/github/repos", methods=["GET"])
def github_list_repos():
    status, data = list_repos()
    return jsonify(data), status


@app.route("/github/repo/<owner>/<repo>", methods=["GET"])
def github_get_repo(owner, repo):
    status, data = get_repo(owner, repo)
    return jsonify(data), status


@app.route("/github/workflow-dispatch", methods=["POST"])
def github_workflow_dispatch():
    body = request.get_json(force=True, silent=True) or {}
    owner = body.get("owner") or request.args.get("owner")
    repo = body.get("repo") or request.args.get("repo")
    workflow_id = body.get("workflow_id") or request.args.get("workflow_id")
    ref = body.get("ref", "main")
    inputs = body.get("inputs")

    if not owner or not repo or not workflow_id:
        return (
            jsonify({"error": "missing_params", "message": "owner, repo, workflow_id required"}),
            400,
        )
    status, data = trigger_workflow(owner, repo, workflow_id, ref=ref, inputs=inputs)
    return jsonify(data), status


@app.route("/github/releases/<owner>/<repo>/latest", methods=["GET"])
def github_latest_release(owner, repo):
    status, data = get_latest_release(owner, repo)
    return jsonify(data), status


# --- Store data collected from UniLogic/PLC ---


@app.route("/data/collect", methods=["POST"])
def data_collect():
    """
    Store data sent from UniLogic/PLC. Body: any JSON (e.g. {"tag": "Temp1", "value": 23.5}).
    Optional query param: source=plc (default). Data is appended to a file with a UTC timestamp.
    """
    body = request.get_json(force=True, silent=True) or {}
    source = request.args.get("source", "plc")
    if not body:
        return jsonify({"error": "empty_body", "message": "Send JSON body to store"}), 400
    record = store_append(body, source=source)
    return jsonify({"status": "stored", "id": record["id"], "record": record}), 201


@app.route("/data/latest", methods=["GET"])
def data_latest():
    """Read last N stored records (default 100). Query param: n=50."""
    n = request.args.get("n", type=int) or 100
    n = min(max(1, n), 1000)
    records = store_read_latest(n)
    return jsonify({"count": len(records), "records": records}), 200


# --- Snowflake: load from Azure Blob stage ---


@app.route("/snowflake/load", methods=["POST"])
def snowflake_load():
    """
    Create stage/table/file format if needed, then run COPY INTO to load PLC data
    from the Azure Blob stage into Snowflake. Requires Snowflake + Azure env vars.
    """
    try:
        from snowflake_loader import setup_and_load
        result = setup_and_load()
        if result.get("error"):
            return jsonify(result), 400
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": "snowflake_load_failed", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
