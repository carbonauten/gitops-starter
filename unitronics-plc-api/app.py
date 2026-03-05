from flask import Flask, jsonify, request

from plc_client import PLCClient, load_plc_config_from_env
from github_client import (
    get_repo,
    get_latest_release,
    list_repos,
    trigger_workflow,
)


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
