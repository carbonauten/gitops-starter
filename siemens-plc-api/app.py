from flask import Flask, jsonify, request

from plc_client import PLCClient, load_plc_config_from_env


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
                "rack": cfg.rack,
                "slot": cfg.slot,
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)

