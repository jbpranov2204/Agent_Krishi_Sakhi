from __future__ import annotations

from typing import Any

from flask import Flask, jsonify, request

from krishi_agent.advisory import generate_weekly_advisory
from krishi_agent.clients import fetch_combined_data
from krishi_agent.config import AppConfig
from krishi_agent.models import FarmerInput


app = Flask(__name__)


def _parse_irrigation(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"yes", "y", "true", "1"}:
            return True
        if normalized in {"no", "n", "false", "0"}:
            return False

    raise ValueError("'irrigation' must be a boolean or one of: yes/no, true/false, 1/0")


def _build_farmer_input(payload: dict[str, Any]) -> FarmerInput:
    required_fields = ["location", "crop_type", "land_size", "irrigation", "experience_level"]
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    location = str(payload["location"]).strip()
    crop_type = str(payload["crop_type"]).strip()
    experience_level = str(payload["experience_level"]).strip()

    if not location:
        raise ValueError("'location' cannot be empty")
    if not crop_type:
        raise ValueError("'crop_type' cannot be empty")
    if not experience_level:
        raise ValueError("'experience_level' cannot be empty")

    try:
        land_size = float(payload["land_size"])
    except (TypeError, ValueError) as exc:
        raise ValueError("'land_size' must be a valid number") from exc

    if land_size <= 0:
        raise ValueError("'land_size' must be greater than 0")

    irrigation = _parse_irrigation(payload["irrigation"])

    return FarmerInput(
        location=location,
        crop_type=crop_type,
        land_size=land_size,
        irrigation=irrigation,
        experience_level=experience_level,
    )


@app.get("/")
def root() -> tuple[Any, int]:
    return jsonify({
        "service": "Krishi Advisory API",
        "version": "1.0.0",
        "endpoints": {
            "health": "GET /health",
            "advisory": "POST /api/advisory",
        },
        "usage": {
            "post_endpoint": "POST /api/advisory with JSON",
            "required_fields": ["location", "crop_type", "land_size", "irrigation", "experience_level"],
            "example": {
                "location": "Bengaluru",
                "crop_type": "Paddy",
                "land_size": 2.5,
                "irrigation": True,
                "experience_level": "beginner"
            }
        }
    }), 200


@app.get("/health")
def health() -> tuple[Any, int]:
    return jsonify({"status": "ok"}), 200


@app.post("/api/advisory")
def advisory() -> tuple[Any, int]:
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    try:
        config = AppConfig.from_env()
        farmer_input = _build_farmer_input(payload)
        weather_data, soil_data = fetch_combined_data(farmer_input.location, config)
        advisory_data = generate_weekly_advisory(farmer_input, weather_data, soil_data, config)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": "Failed to generate advisory", "details": str(exc)}), 500

    return jsonify(advisory_data), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
