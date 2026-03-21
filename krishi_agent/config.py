from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv(override=True)


@dataclass
class AppConfig:
    weather_api_url: str
    weather_api_key: str
    soil_api_url: str
    soil_api_key: str
    llm_model: str
    llm_base_url: str
    llm_api_key: str
    farm_latitude: float
    farm_longitude: float
    weather_units: str
    weather_days: int
    request_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        weather_api_url = os.getenv("WEATHER_API_URL", "").strip()
        weather_api_key = os.getenv("WEATHER_API_KEY", "").strip()
        soil_api_url = os.getenv("SOIL_API_URL", "").strip()
        soil_api_key = os.getenv("SOIL_API_KEY", "").strip()
        llm_model = os.getenv("LLM_MODEL", "openai/gpt-oss-120b").strip()
        llm_base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").strip()
        llm_api_key = os.getenv("LLM_API_KEY", "").strip()

        # CrewAI routes Groq models correctly when prefixed with "groq/".
        if "api.groq.com" in llm_base_url and llm_model.startswith("openai/"):
            llm_model = f"groq/{llm_model}"

        if not weather_api_url:
            raise ValueError("Missing WEATHER_API_URL in environment.")
        if not soil_api_url:
            raise ValueError("Missing SOIL_API_URL in environment.")
        if not llm_api_key:
            raise ValueError("Missing LLM_API_KEY in environment.")

        try:
            farm_latitude = float(os.getenv("FARM_LATITUDE", ""))
            farm_longitude = float(os.getenv("FARM_LONGITUDE", ""))
        except ValueError as exc:
            raise ValueError("FARM_LATITUDE and FARM_LONGITUDE must be valid floats.") from exc

        weather_units = os.getenv("WEATHER_UNITS", "metric").strip() or "metric"

        try:
            weather_days = int(os.getenv("WEATHER_DAYS", "7"))
            request_timeout_seconds = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
        except ValueError as exc:
            raise ValueError("WEATHER_DAYS and REQUEST_TIMEOUT_SECONDS must be integers.") from exc

        if weather_days < 1 or weather_days > 7:
            weather_days = 7

        return cls(
            weather_api_url=weather_api_url,
            weather_api_key=weather_api_key,
            soil_api_url=soil_api_url,
            soil_api_key=soil_api_key,
            llm_model=llm_model,
            llm_base_url=llm_base_url,
            llm_api_key=llm_api_key,
            farm_latitude=farm_latitude,
            farm_longitude=farm_longitude,
            weather_units=weather_units,
            weather_days=weather_days,
            request_timeout_seconds=request_timeout_seconds,
        )
