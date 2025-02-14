import requests
from collections import Counter
from personal_assistant.tools.caching import cached_output


def fetch_ip_api_location():
    """Fetch location from ip-api.com (No API Key Required)."""
    try:
        response = requests.get("http://ip-api.com/json/", timeout=5)
        data = response.json()
        return data.get("city")
    except Exception:
        return None


def fetch_ipwhois_location():
    """Fetch location from ipwhois.app (No API Key Required)."""
    try:
        response = requests.get("https://ipwhois.app/json/", timeout=5)
        data = response.json()
        return data.get("city")
    except Exception:
        return None


def fetch_ipinfo_location():
    """Fetch location from ipinfo.io (No API Key Required)."""
    try:
        response = requests.get("https://ipinfo.io/json", timeout=5)
        data = response.json()
        return data.get("city")
    except Exception:
        return None


def fetch_location():
    """Get the best possible location by checking multiple sources."""
    sources = [
        fetch_ip_api_location(),
        fetch_ipwhois_location(),
        fetch_ipinfo_location(),
    ]

    # Filter out None values
    valid_locations = [loc for loc in sources if loc]

    if valid_locations:
        # Return the most common location (voting mechanism)
        most_common_location = Counter(valid_locations).most_common(1)[0][0]
        return most_common_location

    return "Unknown"


@cached_output(max_age_seconds=300)  # Cache expires in 5 min
def get_location_text():
    location = fetch_location()
    return f"My current location is: {location}"


def get_output():
    output = get_location_text()
    return {
        "plugin_name": "location",
        "output": output,
    }


# Allow standalone testing
if __name__ == "__main__":
    result = get_output()
    print(result["output"])
