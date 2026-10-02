"""
Spotify control via the real Spotify Web API (spotipy). Requires:
  1. A free Spotify Developer app (see README.md for the 2-minute setup) --
     gives you a Client ID + Client Secret.
  2. Spotify Premium -- the playback-control endpoints (play/pause/skip/
     volume) require Premium; free accounts can still search.
  3. An active Spotify device -- have the Spotify app open (desktop, phone,
     or web player) so there's something for the API to control. First run
     opens a browser window for you to log in and approve access once;
     after that a cached token is reused.
"""
import logging

from ..config import config

log = logging.getLogger("jarvis.tools.spotify")

_client = None
_unavailable_reason = None


def _get_client():
    global _client, _unavailable_reason
    if _client is not None or _unavailable_reason is not None:
        return _client

    if not config.spotify_client_id or not config.spotify_client_secret:
        _unavailable_reason = (
            "Spotify isn't configured -- set SPOTIFY_CLIENT_ID and "
            "SPOTIFY_CLIENT_SECRET in .env (see README.md)."
        )
        return None

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth

        auth = SpotifyOAuth(
            client_id=config.spotify_client_id,
            client_secret=config.spotify_client_secret,
            redirect_uri=config.spotify_redirect_uri,
            scope="user-modify-playback-state user-read-playback-state user-read-currently-playing",
            cache_path=".spotify_token_cache",
            open_browser=True,
        )
        _client = spotipy.Spotify(auth_manager=auth)
        return _client
    except Exception as e:  # noqa: BLE001
        _unavailable_reason = f"Failed to authenticate with Spotify: {e}"
        return None


def _active_device_id(sp) -> str | None:
    devices = sp.devices().get("devices", [])
    if not devices:
        return None
    active = next((d for d in devices if d.get("is_active")), None)
    return (active or devices[0])["id"]


def spotify_play(query: str = "") -> dict:
    sp = _get_client()
    if sp is None:
        return {"ok": False, "reason": _unavailable_reason}
    try:
        device_id = _active_device_id(sp)
        if not device_id:
            return {
                "ok": False,
                "reason": "No active Spotify device found -- open Spotify on this "
                "computer or phone first.",
            }
        if query:
            results = sp.search(q=query, type="track", limit=1)
            items = results.get("tracks", {}).get("items", [])
            if not items:
                return {"ok": False, "reason": f"No track found for '{query}'."}
            track = items[0]
            sp.start_playback(device_id=device_id, uris=[track["uri"]])
            return {
                "ok": True,
                "now_playing": f"{track['name']} by {track['artists'][0]['name']}",
            }
        else:
            sp.start_playback(device_id=device_id)
            return {"ok": True, "action": "resumed"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)}


def spotify_pause() -> dict:
    sp = _get_client()
    if sp is None:
        return {"ok": False, "reason": _unavailable_reason}
    try:
        sp.pause_playback()
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)}


def spotify_next() -> dict:
    sp = _get_client()
    if sp is None:
        return {"ok": False, "reason": _unavailable_reason}
    try:
        sp.next_track()
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)}


def spotify_previous() -> dict:
    sp = _get_client()
    if sp is None:
        return {"ok": False, "reason": _unavailable_reason}
    try:
        sp.previous_track()
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)}


def spotify_set_volume(level: int) -> dict:
    sp = _get_client()
    if sp is None:
        return {"ok": False, "reason": _unavailable_reason}
    try:
        level = max(0, min(100, int(level)))
        sp.volume(level)
        return {"ok": True, "volume": level}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)}


def spotify_now_playing() -> dict:
    sp = _get_client()
    if sp is None:
        return {"ok": False, "reason": _unavailable_reason}
    try:
        current = sp.current_playback()
        if not current or not current.get("item"):
            return {"ok": True, "playing": False}
        item = current["item"]
        return {
            "ok": True,
            "playing": current.get("is_playing", False),
            "track": item["name"],
            "artist": item["artists"][0]["name"],
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)}
