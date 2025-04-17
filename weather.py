from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
import os
import sys
import asyncio

# Initialize FastMCP server
mcp = FastMCP("weather")

# Constants
NWS_API_BASE = "https://api.weather.gov"
OPENWEATHER_API_BASE = "https://api.openweathermap.org/data/2.5"
OPENWEATHER_API_KEY = "0cba3520d33d862084acd482ee1ef059"  # Get API key from environment variable
USER_AGENT = "weather-app/1.0"


async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

async def make_openweather_request(url: str, params: dict) -> dict[str, Any] | None:
    """Make a request to the OpenWeatherMap API with proper error handling."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error making OpenWeatherMap request: {e}")
            return None

def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
Description: {props.get('description', 'No description available')}
Instructions: {props.get('instruction', 'No specific instructions provided')}
"""


@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)

@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    # First try OpenWeatherMap for international locations
    if OPENWEATHER_API_KEY:
        return await get_international_forecast(latitude, longitude)
    
    # Fall back to NWS for US locations
    # First get the forecast grid endpoint
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    # Get the forecast URL from the points response
    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    # Format the periods into a readable forecast
    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:  # Only show next 5 periods
        forecast = f"""
{period['name']}:
Temperature: {period['temperature']}°{period['temperatureUnit']}
Wind: {period['windSpeed']} {period['windDirection']}
Forecast: {period['detailedForecast']}
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)

@mcp.tool()
async def get_current_weather(city: str, country_code: str = "") -> str:
    """Get current weather conditions for a city.

    Args:
        city: Name of the city
        country_code: Optional two-letter country code (e.g., IN for India)
    """
    if not OPENWEATHER_API_KEY:
        return "OpenWeatherMap API key is not configured. Please set the OPENWEATHER_API_KEY environment variable."
    
    # Build query parameter
    location_query = city
    if country_code:
        location_query = f"{city},{country_code}"
    
    params = {
        "q": location_query,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric"  # Use metric units (Celsius)
    }
    
    url = f"{OPENWEATHER_API_BASE}/weather"
    data = await make_openweather_request(url, params)
    
    if not data:
        return f"Unable to fetch current weather for {city}."
    
    # Extract and format weather information
    try:
        weather_desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]
        
        # Convert wind speed from m/s to km/h
        wind_speed_kmh = wind_speed * 3.6
        
        return f"""
Current Weather for {city}:
Condition: {weather_desc.title()}
Temperature: {temp}°C (Feels like: {feels_like}°C)
Humidity: {humidity}%
Wind Speed: {wind_speed_kmh:.1f} km/h
"""
    except KeyError:
        return f"Error parsing weather data for {city}."

async def get_international_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for international locations using OpenWeatherMap.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    if not OPENWEATHER_API_KEY:
        return "OpenWeatherMap API key is not configured. Please set the OPENWEATHER_API_KEY environment variable."
    
    params = {
        "lat": latitude,
        "lon": longitude,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",  # Use metric units (Celsius)
        "exclude": "minutely,hourly"  # Exclude minutely and hourly forecasts to reduce data
    }
    
    url = f"{OPENWEATHER_API_BASE}/onecall"
    data = await make_openweather_request(url, params)
    
    if not data:
        return "Unable to fetch forecast data for this location."
    
    # Format current weather
    current = data.get("current", {})
    current_weather = f"""
Current Weather:
Condition: {current.get('weather', [{}])[0].get('description', 'Unknown').title()}
Temperature: {current.get('temp', 'Unknown')}°C (Feels like: {current.get('feels_like', 'Unknown')}°C)
Humidity: {current.get('humidity', 'Unknown')}%
Wind Speed: {current.get('wind_speed', 'Unknown') * 3.6:.1f} km/h
"""
    
    # Format daily forecasts
    daily_forecasts = []
    for day in data.get("daily", [])[:5]:  # Get next 5 days
        date = day.get("dt", 0)
        import datetime
        date_str = datetime.datetime.fromtimestamp(date).strftime("%A, %b %d")
        
        forecast = f"""
{date_str}:
Condition: {day.get('weather', [{}])[0].get('description', 'Unknown').title()}
Temperature: {day.get('temp', {}).get('day', 'Unknown')}°C (Min: {day.get('temp', {}).get('min', 'Unknown')}°C, Max: {day.get('temp', {}).get('max', 'Unknown')}°C)
Humidity: {day.get('humidity', 'Unknown')}%
Wind Speed: {day.get('wind_speed', 'Unknown') * 3.6:.1f} km/h
"""
        daily_forecasts.append(forecast)
    
    return current_weather + "\n---\n" + "\n---\n".join(daily_forecasts)


if __name__ == "__main__":
    # Initialize and run the server
    import asyncio
    
    async def main():
        # Get weather for Delhi, India
        result = await get_current_weather("Delhi", "IN")
        print(result)
        
        # Get forecast for Delhi (approximate coordinates)
        delhi_lat = 28.6139
        delhi_lon = 77.2090
        forecast = await get_international_forecast(delhi_lat, delhi_lon)
        print("\nForecast for Delhi:")
        print(forecast)
    
    # Run the main function
    if len(sys.argv) > 1:
        # If arguments are provided, run the MCP server
        mcp.run(transport='stdio')
    else:
        # Otherwise, run the weather check
        asyncio.run(main())