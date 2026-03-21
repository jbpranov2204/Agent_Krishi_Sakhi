from __future__ import annotations

import json
from textwrap import dedent

from crewai import Agent, Crew, LLM, Process, Task

from .config import AppConfig
from .models import FarmerInput


def _build_prompt(farmer_input: FarmerInput, weather_data: dict, soil_data: dict) -> str:
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
        {json.dumps(weather_data, ensure_ascii=True)[:12000]}

        Soil API data (JSON):
        {json.dumps(soil_data, ensure_ascii=True)[:12000]}

        Build a practical, customized 7-day roadmap for this farmer.

        Mandatory response format:
        1) Quick summary: 5 to 7 lines
        2) Risk alerts: weather, soil, pest or disease risk assumptions
        3) Day-wise roadmap from Day 1 to Day 7 with:
           - Morning activities
           - Evening activities
           - Input materials needed
           - Approx labor needed (low/medium/high)
        4) Irrigation strategy adapted to irrigation={"yes" if farmer_input.irrigation else "no"}
        5) Fertility and soil management plan based on soil data
        6) Contingency plan for rain, heat, or water shortage
        7) Weekly checklist and measurable targets

        Keep the advice realistic for small and medium farmers.
        Avoid generic text. Mention why each major recommendation is made.
        """
    ).strip()


def generate_weekly_advisory(
    farmer_input: FarmerInput,
    weather_data: dict,
    soil_data: dict,
    config: AppConfig,
) -> str:
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
        expected_output="A clear 7-day advisory roadmap in plain text with sections and day-wise actions.",
        agent=advisor,
    )

    crew = Crew(
        agents=[advisor],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff()
    return str(result)
