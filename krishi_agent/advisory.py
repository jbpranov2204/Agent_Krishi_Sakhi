from __future__ import annotations

import json
from datetime import datetime, timedelta
from textwrap import dedent

from crewai import Agent, Crew, LLM, Process, Task

from .config import AppConfig
from .models import FarmerInput


def _extract_json_object(raw: str) -> dict:
    text = raw.strip()

    # Handle fenced code blocks if the model wraps JSON in markdown.
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: extract the largest JSON object in the response.
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("LLM did not return valid JSON content.")
        parsed = json.loads(text[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("LLM JSON response must be a JSON object.")

    return parsed


def _compact_weather_data(weather_data: dict) -> dict:
    location = weather_data.get("location", {})
    current = weather_data.get("current", {})
    forecast_days = weather_data.get("forecast", {}).get("forecastday", [])

    compact_forecast = []
    for day in forecast_days[:7]:
        day_info = day.get("day", {})
        compact_forecast.append(
            {
                "date": day.get("date"),
                "min_temp_c": day_info.get("mintemp_c"),
                "max_temp_c": day_info.get("maxtemp_c"),
                "avg_humidity": day_info.get("avghumidity"),
                "rain_mm": day_info.get("totalprecip_mm"),
                "max_wind_kph": day_info.get("maxwind_kph"),
                "condition": (day_info.get("condition") or {}).get("text"),
            }
        )

    return {
        "location": {
            "name": location.get("name"),
            "region": location.get("region"),
            "country": location.get("country"),
            "lat": location.get("lat"),
            "lon": location.get("lon"),
        },
        "current": {
            "temp_c": current.get("temp_c"),
            "humidity": current.get("humidity"),
            "wind_kph": current.get("wind_kph"),
            "condition": (current.get("condition") or {}).get("text"),
        },
        "forecast": compact_forecast,
    }


def _compact_soil_data(soil_data: dict) -> dict:
    # Keep payload short and useful for the model to avoid token overuse.
    if not isinstance(soil_data, dict):
        return {"raw": str(soil_data)[:1000]}

    compact = {}
    preferred_keys = [
        "dt",
        "moisture",
        "t0",
        "t10",
        "soil",
        "temp",
        "surface_temp",
        "rootzone_temp",
        "ph",
        "nitrogen",
        "phosphorus",
        "potassium",
    ]

    for key in preferred_keys:
        if key in soil_data:
            compact[key] = soil_data[key]

    if not compact:
        # Fall back to first-level scalar fields only.
        for key, value in soil_data.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                compact[key] = value
            if len(compact) >= 12:
                break

    return compact


def _build_default_tasks(crop_type: str, day_number: int) -> list[dict]:
    base_tasks = [
        ("Field inspection", "Inspect crop condition and identify stress signs."),
        ("Water management", "Manage irrigation according to moisture and rainfall."),
        ("Nutrient management", "Apply balanced nutrients based on crop stage."),
        ("Weed control", "Remove weeds and reduce competition for nutrients."),
        ("Pest and disease scouting", "Check leaves and stems for early infestation signs."),
        ("Soil and bund maintenance", "Maintain drainage and field bund integrity."),
        ("Progress review", "Review weekly targets and prepare next-week actions."),
    ]

    title, description = base_tasks[(day_number - 1) % len(base_tasks)]
    return [
        {
            "taskId": f"task_{day_number}",
            "title": f"{crop_type}: {title}",
            "description": description,
            "steps": [
                {
                    "stepNumber": 1,
                    "instruction": "Inspect field conditions and prioritize urgent areas.",
                    "startTime": "06:00 AM",
                    "endTime": "07:00 AM",
                },
                {
                    "stepNumber": 2,
                    "instruction": "Complete the main field operation for the day.",
                    "startTime": "07:00 AM",
                    "endTime": "10:00 AM",
                },
                {
                    "stepNumber": 3,
                    "instruction": "Record observations and prepare inputs for next day.",
                    "startTime": "05:00 PM",
                    "endTime": "06:00 PM",
                },
            ],
            "materials": ["Gloves", "Hand tools", "Record notebook"],
            "precautions": [
                "Avoid field operations during heavy rain or strong wind.",
                "Use protective gear during all manual operations.",
            ],
            "isCompleted": False,
        }
    ]


def _build_fallback_plan(farmer_input: FarmerInput, weather_data: dict) -> dict:
    forecast_days = weather_data.get("forecast", {}).get("forecastday", [])[:7]

    if forecast_days:
        first_date = forecast_days[0].get("date")
    else:
        first_date = datetime.now().strftime("%Y-%m-%d")

    try:
        month_name = datetime.strptime(first_date, "%Y-%m-%d").strftime("%B")
    except Exception:
        month_name = "Current Month"

    days = []
    for i in range(7):
        forecast = forecast_days[i] if i < len(forecast_days) else {}
        day_info = forecast.get("day", {})
        weather_date = forecast.get("date")

        if not weather_date:
            weather_date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")

        min_temp = day_info.get("mintemp_c")
        max_temp = day_info.get("maxtemp_c")
        humidity = day_info.get("avghumidity")
        rainfall = day_info.get("totalprecip_mm")
        wind = day_info.get("maxwind_kph")
        condition = (day_info.get("condition") or {}).get("text", "Unknown")

        days.append(
            {
                "dayId": f"day_{i + 1}",
                "dayNumber": i + 1,
                "weather": {
                    "date": weather_date,
                    "temperature": {
                        "min": int(min_temp) if isinstance(min_temp, (int, float)) else 0,
                        "max": int(max_temp) if isinstance(max_temp, (int, float)) else 0,
                    },
                    "humidity": int(humidity) if isinstance(humidity, (int, float)) else 0,
                    "rainfall": int(rainfall) if isinstance(rainfall, (int, float)) else 0,
                    "windSpeed": int(wind) if isinstance(wind, (int, float)) else 0,
                    "condition": condition,
                    "advisory": "Plan operations in morning hours and avoid risky activities during adverse weather.",
                },
                "tasks": _build_default_tasks(farmer_input.crop_type, i + 1),
            }
        )

    return {
        "planId": "plan_001",
        "crop": farmer_input.crop_type,
        "durationMonths": 1,
        "months": [
            {
                "monthId": "month_1",
                "monthName": month_name,
                "summary": "Weekly operational plan generated from current weather and farmer profile.",
                "weeks": [
                    {
                        "weekId": "week_1",
                        "weekNumber": 1,
                        "summary": "Daily crop management, weather-aware operations, and risk reduction steps.",
                        "days": days,
                    }
                ],
            }
        ],
    }


def _build_prompt(farmer_input: FarmerInput, weather_data: dict, soil_data: dict) -> str:
    compact_weather = _compact_weather_data(weather_data)
    compact_soil = _compact_soil_data(soil_data)

    schema_example = """
{
    "planId": "plan_001",
    "crop": "__CROP__",
    "durationMonths": 1,
    "months": [
        {
            "monthId": "month_1",
            "monthName": "Current Month",
            "summary": "...",
            "weeks": [
                {
                    "weekId": "week_1",
                    "weekNumber": 1,
                    "summary": "...",
                    "days": [
                        {
                            "dayId": "day_1",
                            "dayNumber": 1,
                            "weather": {
                                "date": "YYYY-MM-DD",
                                "temperature": { "min": 0, "max": 0 },
                                "humidity": 0,
                                "rainfall": 0,
                                "windSpeed": 0,
                                "condition": "...",
                                "advisory": "..."
                            },
                            "tasks": [
                                {
                                    "taskId": "task_1",
                                    "title": "...",
                                    "description": "...",
                                    "steps": [
                                        {
                                            "stepNumber": 1,
                                            "instruction": "...",
                                            "startTime": "06:00 AM",
                                            "endTime": "07:00 AM"
                                        }
                                    ],
                                    "materials": ["..."],
                                    "precautions": ["..."],
                                    "isCompleted": false
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ]
}
""".strip().replace("__CROP__", farmer_input.crop_type)

    return dedent(
        f"""
        You are an expert agricultural advisory planner.

        Farmer profile:
        - location: {farmer_input.location}
        - crop_type: {farmer_input.crop_type}
        - land_size (acres): {farmer_input.land_size}
        - irrigation available: {"yes" if farmer_input.irrigation else "no"}
        - experience_level: {farmer_input.experience_level}

        Weather API data (JSON):
        {json.dumps(compact_weather, ensure_ascii=True)}

        Soil API data (JSON):
        {json.dumps(compact_soil, ensure_ascii=True)}

        Build a practical, customized farming plan for this farmer.

        Return ONLY valid JSON with no markdown, no backticks, no explanation text.
        Follow this exact JSON structure and key names:
        {schema_example}

        Requirements:
        - Generate exactly 7 days inside month_1/week_1 (day_1 to day_7).
        - Tailor tasks to the crop and farmer profile.
        - Use weather and soil data for practical advisories.
        - Keep values realistic and operational for small and medium farmers.
        """
    ).strip()


def generate_weekly_advisory(
    farmer_input: FarmerInput,
    weather_data: dict,
    soil_data: dict,
    config: AppConfig,
) -> dict:
    llm = LLM(
        model=config.llm_model,
        base_url=config.llm_base_url,
        api_key=config.llm_api_key,
        temperature=0.3,
    )

    advisor = Agent(
        role="Senior Agricultural Advisory Specialist",
        goal="Create an actionable and localized weekly farm roadmap using weather and soil data.",
        backstory=(
            "You support farmers with practical daily crop operations, irrigation planning, "
            "and climate-resilient decisions."
        ),
        allow_delegation=False,
        verbose=False,
        llm=llm,
    )

    task = Task(
        description=_build_prompt(farmer_input, weather_data, soil_data),
        expected_output="A strict JSON object in the requested nested plan format.",
        agent=advisor,
    )

    crew = Crew(
        agents=[advisor],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    result_text = str(crew.kickoff())

    try:
        return _extract_json_object(result_text)
    except ValueError:
        return _build_fallback_plan(farmer_input, weather_data)
