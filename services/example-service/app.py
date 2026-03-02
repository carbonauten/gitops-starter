import os
import random

from flask import Flask, jsonify, request, make_response

app = Flask(__name__)

@app.route('/')
def hello():
    return jsonify({"message": "Hello from example-service"})


def choose_ab_variant() -> str:
    existing = request.cookies.get("ab_variant")
    if existing in {"A", "B"}:
        return existing

    try:
        percent_a = float(os.getenv("AB_VARIANT_A_PERCENT", "50"))
    except ValueError:
        percent_a = 50.0

    percent_a = max(0.0, min(100.0, percent_a))
    roll = random.random() * 100.0
    return "A" if roll < percent_a else "B"


@app.route("/ab-test")
def ab_test():
    variant = choose_ab_variant()
    response = make_response(
        jsonify(
            {
                "experiment": "example-service-home",
                "variant": variant,
            }
        )
    )
    response.set_cookie("ab_variant", variant, max_age=60 * 60 * 24 * 30, httponly=True)
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
