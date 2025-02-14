import requests
from bs4 import BeautifulSoup
import random
import time
from fake_useragent import UserAgent  # Install with `pip install fake-useragent`
import re
import unicodedata

# Initialize user-agent generator
ua = UserAgent()


def get_structured_content(url="https://example.com", proxies=None):
    """
    Fetch and structure content from a web page while preserving hierarchy.

    Args:
        url (str): The URL to scrape.
        proxies (dict, optional): Proxy settings (e.g., {"http": "http://proxy.com:1234"}).

    Returns:
        str: Structured text content from the web page or an error message.
    """
    try:
        # Configure retries for robust requests
        session = requests.Session()
        retries = requests.adapters.Retry(
            total=5, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504]
        )
        session.mount("http://", requests.adapters.HTTPAdapter(max_retries=retries))
        session.mount("https://", requests.adapters.HTTPAdapter(max_retries=retries))

        # Random headers
        headers = {
            "User-Agent": ua.random,
            "Accept-Language": "en-US,en;q=0.9",
        }

        # Random delay to mimic human browsing
        time.sleep(random.uniform(2, 5))

        # Perform the request
        response = session.get(url, headers=headers, proxies=proxies, timeout=15)
        response.raise_for_status()

        # Detect CAPTCHA
        if "captcha" in response.text.lower():
            return "CAPTCHA detected. Manual solving required."

        # Parse the HTML content
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove unwanted sections
        for selector in ["header", "footer", "nav", ".ads", ".social-links"]:
            for elem in soup.select(selector):
                elem.decompose()  # Removes the element from the DOM

        # Structure and clean content
        structured_content = build_hierarchical_output(soup)
        return structured_content

    except requests.exceptions.RequestException as e:
        return f"Error fetching the URL: {e}"
    except Exception as e:
        return f"Error processing the URL: {e}"


def build_hierarchical_output(soup):
    """
    Build a visually structured output by combining content hierarchy.

    Args:
        soup (BeautifulSoup): Parsed HTML content.

    Returns:
        str: Structured content as a string.
    """
    output = []
    for tag in soup.find_all(["h1", "h2", "h3", "p"]):
        text = tag.get_text(strip=True)
        if tag.name == "h1":
            output.append(f"\n# {text}\n")
        elif tag.name == "h2":
            output.append(f"\n## {text}\n")
        elif tag.name == "h3":
            output.append(f"\n### {text}\n")
        elif tag.name == "p":
            output.append(f"    {text}")  # Indent paragraphs for clarity
    return "\n".join(output)


def clean_scraped_text(text):
    """
    Clean the scraped web content by:
    - Removing excessive blank lines and whitespace.
    - Removing repetitive or irrelevant sections like "link copied" or "Advertisement".
    - Normalizing text encoding issues.
    - Stripping out lines with minimal content.

    Args:
        text (str): Raw text content.

    Returns:
        str: Cleaned text content.
    """
    # Normalize text to handle encoding issues
    text = unicodedata.normalize("NFKC", text)

    # Remove common irrelevant patterns
    patterns_to_remove = [
        r"link copied",  # Matches repeated "link copied" text
        r"Advertisement",  # Matches advertisements
        r"\b(Read more|Install Now|Click Here)\b",  # Common phrases for ads or CTAs
        r"© Copyright .*",  # Copyright footers
        r"This website follows the .*",  # Compliance text
        r"^[^a-zA-Z0-9]*$",  # Lines with only special characters
    ]
    for pattern in patterns_to_remove:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Remove lines with less than a certain length (e.g., menu items)
    text = "\n".join(line for line in text.splitlines() if len(line.strip()) > 20)

    # Collapse multiple blank lines into one
    text = re.sub(r"\n\s*\n", "\n", text).strip()

    return text


if __name__ == "__main__":
    url_to_scrape = "https://mankoo.ca"
    structured_content = get_structured_content(url=url_to_scrape)
    print(structured_content)
