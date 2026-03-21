from __future__ import annotations

from datetime import datetime
from pathlib import Path

from krishi_agent.advisory import generate_weekly_advisory
from krishi_agent.clients import fetch_combined_data
from krishi_agent.config import AppConfig
from krishi_agent.models import FarmerInput


def _ask_bool(prompt: str) -> bool:
    while True:
        value = input(prompt).strip().lower()
        if value in {"yes", "y"}:
            return True
        if value in {"no", "n"}:
            return False
        print("Please enter yes or no.")


def _ask_float(prompt: str) -> float:
    while True:
        value = input(prompt).strip()
        try:
            return float(value)
        except ValueError:
            print("Please enter a valid number.")


def collect_farmer_input() -> FarmerInput:
    location = input("Location (city name): ").strip()
    crop_type = input("Crop type: ").strip()
    land_size = _ask_float("Land size (in acres): ")
    irrigation = _ask_bool("Irrigation available? (yes/no): ")
    experience_level = input("Experience level (beginner/intermediate/expert): ").strip()

    return FarmerInput(
        location=location,
        crop_type=crop_type,
        land_size=land_size,
        irrigation=irrigation,
        experience_level=experience_level,
    )


def save_output(report: str) -> Path:
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"weekly_advisory_{timestamp}.md"
    output_file.write_text(report, encoding="utf-8")
    return output_file


def main() -> None:
    print("=== Krishi Weekly Advisory Agent (CrewAI) ===")

    config = AppConfig.from_env()
    farmer_input = collect_farmer_input()

    print(f"\nFetching weather and soil data for {farmer_input.location}...")
    try:
        weather_data, soil_data = fetch_combined_data(farmer_input.location, config)
        print(f"✓ Weather data fetched")
        print(f"✓ Polygon created and soil data fetched")
    except Exception as e:
        print(f"✗ Error fetching data: {e}")
        return

    print("\nGenerating weekly advisory roadmap...\n")
    advisory = generate_weekly_advisory(farmer_input, weather_data, soil_data, config)

    print(advisory)
    output_file = save_output(advisory)
    print(f"\nSaved advisory to: {output_file}")


if __name__ == "__main__":
    main()
