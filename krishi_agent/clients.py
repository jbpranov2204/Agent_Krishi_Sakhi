from __future__ import annotations

from typing import Any

import requests

from .config import AppConfig


def _safe_json(response: requests.Response) -> dict[str, Any]:
    try:
        return response.json()
    except ValueError:
        return {"raw_text": response.text}


def get_weather_data(location: str, api_key: str, api_url: str, timeout: int) -> dict[str, Any]:
    """Fetch weather data from weatherapi.com using location name."""
    params = {
        "q": location,
        "aqi": "yes",
        "key": api_key,
    }

    response = requests.get(
        api_url,
        params=params,
        timeout=timeout,
    )
    response.raise_for_status()
    return _safe_json(response)


def extract_coordinates(weather_data: dict[str, Any]) -> tuple[float, float]:
    """Extract latitude and longitude from weather API response."""
    lat = weather_data["location"]["lat"]
    lon = weather_data["location"]["lon"]
    return lat, lon


def create_polygon(
    lat: float, lon: float, agro_api_key: str, timeout: int
) -> str:
    """Create a polygon in AgroMonitoring API and return polygon_id."""
    polygon_url = "https://api.agromonitoring.com/agro/1.0/polygons"
    # Keep polygon small to satisfy common AgroMonitoring area constraints.
    delta = 0.001

    polygon_body = {
        "name": "Krishi Farm",
        "geo_json": {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [lon, lat],
                        [lon + delta, lat],
                        [lon + delta, lat + delta],
                        [lon, lat + delta],
                        [lon, lat],
                    ]
                ],
            },
        },
    }

    params = {"appid": agro_api_key, "duplicated": "true"}
    response = requests.post(
        polygon_url,
        json=polygon_body,
        params=params,
        timeout=timeout,
    )
    if not response.ok:
        error_detail = _safe_json(response)
        raise requests.HTTPError(
            f"Polygon creation failed ({response.status_code}): {error_detail}",
            response=response,
        )
    data = _safe_json(response)
    return data["id"]


def get_soil_data(polygon_id: str, agro_api_key: str, soil_api_url: str, timeout: int) -> dict[str, Any]:
    """Fetch soil data for a given polygon_id from AgroMonitoring API."""
    params = {
        "polygon_id": polygon_id,
        "appid": agro_api_key,
    }

    response = requests.get(
        soil_api_url,
        params=params,
        timeout=timeout,
    )
    response.raise_for_status()
    return _safe_json(response)


def fetch_combined_data(location: str, config: AppConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    """Orchestrate full workflow: weather → extract coords → create polygon → fetch soil."""
    # Step 1: Fetch weather data
    weather_data = get_weather_data(
        location=location,
        api_key=config.weather_api_key,
        api_url=config.weather_api_url,
        timeout=config.request_timeout_seconds,
    )

    # Step 2: Extract coordinates
    lat, lon = extract_coordinates(weather_data)

    # Step 3: Create polygon in AgroMonitoring
    polygon_id = create_polygon(
        lat=lat,
        lon=lon,
        agro_api_key=config.soil_api_key,
        timeout=config.request_timeout_seconds,
    )

    # Step 4: Fetch soil data
    soil_data = get_soil_data(
        polygon_id=polygon_id,
        agro_api_key=config.soil_api_key,
        soil_api_url=config.soil_api_url,
        timeout=config.request_timeout_seconds,
    )

    return weather_data, soil_data
