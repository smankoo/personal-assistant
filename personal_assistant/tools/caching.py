import os
import inspect
from datetime import datetime
from functools import wraps


CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.cache")

# Ensure the cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)


def get_caller_filename():
    """Retrieve the filename of the script defining the decorated function."""
    # Walk up the call stack to find the first non-caching script
    frame = inspect.currentframe()
    while frame:
        caller_file = frame.f_code.co_filename
        if "caching.py" not in caller_file:  # Ignore the caching script itself
            return os.path.splitext(os.path.basename(caller_file))[0]
        frame = frame.f_back
    return "unknown"  # Fallback if no valid caller found


def set_cache(data):
    """Store data in the cache with metadata."""
    caller_filename = get_caller_filename()
    cache_file = os.path.join(CACHE_DIR, f"{caller_filename}.cache.txt")

    timestamp = datetime.now().isoformat()
    with open(cache_file, "w") as f:
        # Write metadata
        f.write(f"---\ntimestamp: {timestamp}\n---\n")
        # Write content
        f.write(data)


def get_cache(max_age_seconds):
    """Retrieve cached data if it's still valid."""
    caller_filename = get_caller_filename()
    cache_file = os.path.join(CACHE_DIR, f"{caller_filename}.cache.txt")

    if not os.path.exists(cache_file):
        return None  # Cache doesn't exist

    with open(cache_file, "r") as f:
        lines = f.readlines()

    # Parse metadata
    metadata = {}
    if lines[0].strip() == "---":
        idx = lines.index("---\n", 1)  # Find the closing delimiter
        for line in lines[1:idx]:
            key, value = line.strip().split(": ", 1)
            metadata[key] = value
        content = "".join(lines[idx + 1 :])  # Remaining lines are content
    else:
        return None  # Invalid format

    # Check timestamp
    cache_time = datetime.fromisoformat(metadata.get("timestamp", ""))
    age = (datetime.now() - cache_time).total_seconds()
    if age > max_age_seconds:
        return None  # Cache expired

    return content


def cached_output(max_age_seconds):
    """Decorator to handle caching of function output."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Automatically manage caching
            cache_data = get_cache(max_age_seconds=max_age_seconds)
            if cache_data is not None and cache_data != "":
                print("[DEBUG] Using cached data.")
                return cache_data
            print("[DEBUG] Cache is expired or missing. Fetching new data...")
            output = func(*args, **kwargs)
            set_cache(output)
            return output

        return wrapper

    return decorator
