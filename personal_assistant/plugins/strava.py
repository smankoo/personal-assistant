import os
import requests
import datetime
from dotenv import load_dotenv

# Import the caching decorator from your project
from personal_assistant.tools.caching import cached_output

load_dotenv()

# Environment variables for Strava credentials
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("STRAVA_ACCESS_TOKEN")
REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")

STRAVA_AUTH_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"


def update_env_vars(**kwargs):
    """
    Updates the .env file with provided key-value pairs.
    """
    env_path = ".env"
    env_vars = {}

    # Load existing .env values
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()

    # Update with new values
    for key, value in kwargs.items():
        env_vars[key] = value

    # Write back the .env file
    with open(env_path, "w") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    print(f"[INFO] Updated {env_path} with latest token information.")


def refresh_access_token():
    """
    Refreshes the Strava access token using the stored refresh token.
    """
    global ACCESS_TOKEN, REFRESH_TOKEN

    response = requests.post(
        STRAVA_AUTH_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
    )

    try:
        response_data = response.json()
    except requests.exceptions.JSONDecodeError:
        raise Exception("Failed to parse token refresh response. Check credentials.")

    if "access_token" in response_data:
        new_access_token = response_data["access_token"]
        new_refresh_token = response_data["refresh_token"]
        # Update in-memory tokens and persist to .env
        ACCESS_TOKEN = new_access_token
        REFRESH_TOKEN = new_refresh_token
        os.environ["STRAVA_ACCESS_TOKEN"] = new_access_token
        os.environ["STRAVA_REFRESH_TOKEN"] = new_refresh_token
        update_env_vars(
            STRAVA_ACCESS_TOKEN=new_access_token,
            STRAVA_REFRESH_TOKEN=new_refresh_token,
        )
        return new_access_token
    else:
        raise Exception(f"Failed to refresh token: {response_data}")


def authorize_and_exchange_code():
    """
    Guides the user to reauthorize the application in Strava and exchange the code for new tokens.
    """
    authorize_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri=http://localhost/exchange_token"
        f"&approval_prompt=force"
        f"&scope=read,activity:read"
    )
    print("\n[!] Missing required permission `activity:read` or invalid token.")
    print("1. Visit the following URL and authorize the app:")
    print(f"   {authorize_url}")
    print("2. After granting access, you’ll be redirected to a URL like:")
    print("   http://localhost/exchange_token?state=&code=...&scope=read,activity:read")
    print(
        "3. Copy the 'code' parameter from your browser's address bar and paste it below.\n"
    )

    user_code = input("Enter the authorization code here: ").strip()
    if not user_code:
        print("No code entered. Exiting.")
        exit(1)

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": user_code,
        "grant_type": "authorization_code",
    }
    resp = requests.post(STRAVA_AUTH_URL, data=data)
    if resp.status_code != 200:
        print(f"Error exchanging code for token: {resp.status_code} {resp.text}")
        exit(1)

    token_data = resp.json()
    if "access_token" not in token_data:
        print(f"Unexpected token response: {token_data}")
        exit(1)

    new_access_token = token_data["access_token"]
    new_refresh_token = token_data["refresh_token"]

    global ACCESS_TOKEN, REFRESH_TOKEN
    ACCESS_TOKEN = new_access_token
    REFRESH_TOKEN = new_refresh_token
    os.environ["STRAVA_ACCESS_TOKEN"] = new_access_token
    os.environ["STRAVA_REFRESH_TOKEN"] = new_refresh_token
    update_env_vars(
        STRAVA_ACCESS_TOKEN=new_access_token,
        STRAVA_REFRESH_TOKEN=new_refresh_token,
    )
    print("[INFO] Successfully obtained new tokens! They have been saved to .env.")


def get_activity_details(activity_id):
    """
    Fetches detailed information for a given activity using its ID.
    """
    detail_url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    response = requests.get(detail_url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"[WARNING] Unable to fetch details for activity {activity_id}.")
        return {}


def get_strava_activities(days=30):
    """
    Fetches Strava activities from the past 'days' days.
    """
    global ACCESS_TOKEN
    after_timestamp = int(
        (datetime.datetime.now() - datetime.timedelta(days=days)).timestamp()
    )
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    params = {"after": after_timestamp, "per_page": 50}

    response = requests.get(STRAVA_ACTIVITIES_URL, headers=headers, params=params)

    # Handle token expiration or missing permission issues
    if response.status_code in (401, 403):
        try:
            error_data = response.json()
        except requests.exceptions.JSONDecodeError:
            raise Exception("Strava API error with non-JSON response. Check logs.")

        # If missing required scope, trigger reauthorization
        if any(
            err.get("code") == "missing"
            and "activity:read_permission" in err.get("field", "")
            for err in error_data.get("errors", [])
        ):
            authorize_and_exchange_code()
            headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
            response = requests.get(
                STRAVA_ACTIVITIES_URL, headers=headers, params=params
            )
        elif response.status_code == 401:
            print("[INFO] Access token may be expired; attempting to refresh...")
            try:
                ACCESS_TOKEN = refresh_access_token()
                headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
                response = requests.get(
                    STRAVA_ACTIVITIES_URL, headers=headers, params=params
                )
            except Exception as e:
                print("[ERROR] Token refresh failed. Reauthorization required.")
                authorize_and_exchange_code()
                headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
                response = requests.get(
                    STRAVA_ACTIVITIES_URL, headers=headers, params=params
                )

    if response.status_code != 200:
        raise Exception(
            f"Error fetching activities. HTTP {response.status_code}: {response.text}"
        )

    try:
        activities = response.json()
        return activities
    except requests.exceptions.JSONDecodeError:
        raise Exception("Failed to parse Strava API response.")


def format_activity(activity):
    """
    Formats a single activity into a human-readable string.
    """
    try:
        # Convert distance from meters to kilometers
        dist_km = activity.get("distance", 0) / 1000.0
        # Parse local start date
        date_local_str = activity.get("start_date_local", "")
        if date_local_str:
            date_local_obj = datetime.datetime.fromisoformat(
                date_local_str.replace("Z", "+00:00")
            )
            formatted_date = date_local_obj.strftime("%B %d, %Y at %I:%M %p")
        else:
            formatted_date = "Unknown date"

        name = activity.get("name", "Unnamed Activity")
        raw_type = activity.get("type", "Unknown")
        trainer = activity.get("trainer", 0)
        # For running or riding activities, note if they were indoor
        if raw_type.lower() in ["run", "ride"]:
            activity_variant = (
                f"Indoor {raw_type}" if trainer else f"Outdoor {raw_type}"
            )
        else:
            activity_variant = raw_type

        moving_time = str(datetime.timedelta(seconds=activity.get("moving_time", 0)))
        elapsed_time = str(datetime.timedelta(seconds=activity.get("elapsed_time", 0)))
        total_elevation_gain = activity.get("total_elevation_gain", 0)
        average_hr = activity.get("average_heartrate", "N/A")
        max_hr = activity.get("max_heartrate", "N/A")
        suffer_score = activity.get("suffer_score", "N/A")

        if isinstance(suffer_score, (int, float)):
            if suffer_score > 100:
                difficulty = "Hard"
            elif suffer_score > 50:
                difficulty = "Moderate"
            else:
                difficulty = "Easy"
        else:
            difficulty = "N/A"

        # Try to get a description (notes) if available
        description = (activity.get("description") or "").strip()
        if not description:
            details = get_activity_details(activity.get("id"))
            description = (details.get("description") or "").strip()

        formatted_activity = (
            f"{formatted_date} - {name} ({activity_variant}, {dist_km:.2f} km)\n"
            f"  Moving time: {moving_time}, Elapsed time: {elapsed_time}\n"
            f"  Elevation gain: {total_elevation_gain} m\n"
            f"  Average HR: {average_hr}, Max HR: {max_hr}\n"
            f"  Difficulty: {difficulty} (Suffer Score: {suffer_score})\n"
        )
        if description:
            formatted_activity += f"  Notes: {description}\n"
        return formatted_activity
    except Exception as e:
        return f"Error formatting activity: {e}\n"


@cached_output(max_age_seconds=14400)  # Cache expires in 4 hours (4 * 3600 seconds)
def get_strava_text():
    """
    Fetches and formats Strava activities into a string.
    This function is cached to avoid repeated API calls.
    """
    activities = get_strava_activities(days=30)
    if not activities:
        return "No recent Strava activities found."

    output_lines = ["### Strava Activities (Last 30 Days) ###", ""]
    for activity in activities:
        output_lines.append(format_activity(activity))
        output_lines.append("-" * 40)
    return "\n".join(output_lines)


def get_output():
    """
    Plugin entry point.
    Returns a dictionary with the plugin's name and the cached formatted output.
    """
    try:
        output_text = get_strava_text()
        return {"plugin_name": "strava", "output": output_text}
    except Exception as e:
        return {
            "plugin_name": "strava",
            "output": f"Error fetching Strava activities: {e}",
        }


if __name__ == "__main__":
    # Standalone testing of the plugin
    result = get_output()
    print(result["output"])
