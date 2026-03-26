# Krishi Advisory Agent (CrewAI)

This project builds a weekly agricultural advisory roadmap using:
- Farmer inputs:
  - crop_type
  - land_size
  - irrigation (yes/no)
  - experience_level
- Weather API data
- Soil API data (SoilGrids-compatible)

## 1) Setup

1. Create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Create .env from sample and update URLs/keys:

```powershell
Copy-Item .env.example .env
```

Then edit .env and set:
- WEATHER_API_URL
- WEATHER_API_KEY
- SOIL_API_URL
- SOIL_API_KEY (if required)
- LLM_BASE_URL
- LLM_MODEL
- LLM_API_KEY
- FARM_LATITUDE
- FARM_LONGITUDE

## 2) Run

```powershell
python app.py
```

The app asks for:
- crop_type
- land_size
- irrigation (yes/no)
- experience_level

Then it fetches weather + soil data and generates a custom 7-day roadmap.

Output file is saved under outputs/.

## 3) Run Flask API

1. Install dependencies:

```powershell
pip install -r requirements.txt
```

2. Start API server:

```powershell
python api.py
```

3. Health check:

```powershell
Invoke-RestMethod -Method GET http://localhost:5000/health
```

4. Generate advisory (POST):

```powershell
$body = @{
  location = "Bengaluru"
  crop_type = "Paddy"
  land_size = 2
  irrigation = $true
  experience_level = "beginner"
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
  -Uri http://localhost:5000/api/advisory `
  -ContentType "application/json" `
  -Body $body
```

The API returns the advisory as nested JSON.

## 4) API Notes

- Weather API request uses query params lat, lon, units, appid (if key provided).
- Soil API request uses lat, lon. If SOIL_API_KEY is set, it sends Authorization: Bearer <key>.
- If your APIs require different params/header names, update clients in krishi_agent/clients.py.
