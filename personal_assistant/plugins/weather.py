import requests
from datetime import datetime
import pytz
from personal_assistant.tools.caching import cached_output
import os

from dotenv import load_dotenv

load_dotenv()

WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")

if not WEATHER_API_KEY:
    raise ValueError("WEATHER_API_KEY environment variable not set")


LAT = 43.7315  # Latitude for Brampton
LON = -79.7624  # Longitude for Brampton
TIMEZONE = "America/Toronto"


# Function to fetch current date and time
def get_current_datetime():
    tz = pytz.timezone(TIMEZONE)
    current_time = datetime.now(tz)
    return current_time.strftime("%Y-%m-%d %H:%M:%S")


# Function to fetch weather data (current, hourly, and daily using free APIs)
def fetch_weather():
    try:
        # Current Weather API
        current_url = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={WEATHER_API_KEY}&units=metric"
        current_response = requests.get(current_url)
        current_response.raise_for_status()
        current_data = current_response.json()

        current_weather = {
            "temperature": current_data["main"]["temp"],
            "description": current_data["weather"][0]["description"],
            "wind_speed": current_data["wind"]["speed"],
        }

        # 5 Day / 3 Hour Forecast API
        forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={LAT}&lon={LON}&appid={WEATHER_API_KEY}&units=metric"
        forecast_response = requests.get(forecast_url)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()

        # Process hourly forecast (next 12 hours)
        hourly_forecast = []
        tz = pytz.timezone(TIMEZONE)
        for entry in forecast_data["list"][
            :4
        ]:  # 4 entries = ~12 hours (3-hour intervals)
            hourly_forecast.append(
                {
                    "time": datetime.fromtimestamp(entry["dt"], tz).strftime(
                        "%I:%M %p"
                    ),
                    "temperature": entry["main"]["temp"],
                    "description": entry["weather"][0]["description"],
                    "precipitation": entry.get("pop", 0)
                    * 100,  # Probability of precipitation
                }
            )

        # Process daily forecast (next 5 days)
        daily_forecast = []
        daily_data = {}
        for entry in forecast_data["list"]:
            date = datetime.fromtimestamp(entry["dt"], tz).date()
            if date not in daily_data:
                daily_data[date] = {
                    "high": entry["main"]["temp"],
                    "low": entry["main"]["temp"],
                    "description": entry["weather"][0]["description"],
                }
            else:
                daily_data[date]["high"] = max(
                    daily_data[date]["high"], entry["main"]["temp"]
                )
                daily_data[date]["low"] = min(
                    daily_data[date]["low"], entry["main"]["temp"]
                )

        for date, data in daily_data.items():
            daily_forecast.append(
                {
                    "date": date.strftime("%A, %b %d"),
                    "high": data["high"],
                    "low": data["low"],
                    "description": data["description"],
                }
            )

        return {
            "current_weather": current_weather,
            "hourly_forecast": hourly_forecast,
            "daily_forecast": daily_forecast[:5],  # Limit to next 5 days
        }
    except Exception as e:
        return {"error": f"Failed to fetch weather data: {e}"}


@cached_output(max_age_seconds=3600)  # Cache expires in 1 hour
def get_weather_text():
    weather = fetch_weather()
    if "error" in weather:
        return f"Error: {weather['error']}"

    # Format output
    output = "### Current Weather ###\n"
    output += (
        f"{weather['current_weather']['temperature']}°C, {weather['current_weather']['description']}, "
        f"Wind Speed: {weather['current_weather']['wind_speed']} m/s\n\n"
    )

    output += "### Hourly Forecast (Next 12 Hours) ###\n"
    for hour in weather["hourly_forecast"]:
        output += (
            f"{hour['time']}: {hour['temperature']}°C, {hour['description']}, "
            f"Precipitation: {hour['precipitation']}%\n"
        )

    output += "\n### Daily Forecast (Next 5 Days) ###\n"
    for day in weather["daily_forecast"]:
        output += f"{day['date']}: High {day['high']}°C, Low {day['low']}°C, {day['description']}\n"

    return output


def get_output():
    output = get_weather_text()

    return {
        "plugin_name": "weather",
        "output": output,
    }


# Allow standalone testing
if __name__ == "__main__":
    result = get_output()
    print(result["output"])
