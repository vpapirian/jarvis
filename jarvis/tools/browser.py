"""Browser control: open tabs / run web searches in your default browser."""
import webbrowser
from urllib.parse import quote_plus


def open_browser_tab(url: str) -> dict:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    ok = webbrowser.open_new_tab(url)
    return {"opened": ok, "url": url}


def web_search(query: str) -> dict:
    url = f"https://www.google.com/search?q={quote_plus(query)}"
    ok = webbrowser.open_new_tab(url)
    return {"opened": ok, "url": url}
