import json
import logging
from typing import Dict, Optional

import httpx

from library.openrouter import OPENROUTER_API_KEY, OPENROUTER_MODEL

OPENROUTER_ENDPOINT = "https://openrouter.ai/v1/chat/completions"
OPENROUTER_TIMEOUT = 15
OPENROUTER_CACHE: Dict[str, Dict[str, Optional[str]]] = {}

PROMPT_TEMPLATE = """
You are a media librarian helping normalize TorBox downloads into the best possible file names for `.strm` mounts.
Original filename: {original_filename}
Current metadata filename: {metadata_filename}
TorBox metadata title: {metadata_title}
TorBox metadata root folder: {metadata_rootfolder}
TorBox metadata type: {metadata_mediatype}
TorBox metadata year(s): {metadata_years}
TorBox season: {metadata_season}
TorBox episode: {metadata_episode}
File extension: {extension}
Folder name: {folder_name}

Return only a single JSON object with the following keys:
  * `filename` – the desired `.strm` file name (include the original extension, e.g. `Title (Year).mkv`)
  * `media_type` – one of `movie` or `series`

If you are confident this is a TV show or anime, be sure the filename follows the `Title - SXXEXX.ext` format, otherwise use `Title (Year).ext`. Keep the extension the same as the one provided above.
If you cannot improve the name, return the same title and type you already had.
"""


def _build_prompt(download: dict) -> str:
    return PROMPT_TEMPLATE.format(
        original_filename=download.get("file_name", "unknown"),
        metadata_filename=download.get("metadata_filename", "unknown"),
        metadata_title=download.get("metadata_title", "unknown"),
        metadata_rootfolder=download.get("metadata_rootfoldername", "unknown"),
        metadata_mediatype=download.get("metadata_mediatype", "unknown"),
        metadata_years=download.get("metadata_years", "unknown"),
        metadata_season=download.get("metadata_season", "unknown"),
        metadata_episode=download.get("metadata_episode", "unknown"),
        extension=download.get("extension", ""),
        folder_name=download.get("folder_name", "unknown"),
    ).strip()


def _normalize_media_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    candidate = value.strip().lower()
    if "movie" in candidate and "series" not in candidate and "show" not in candidate:
        return "movie"
    for keyword in ("series", "show", "tv", "anime"):
        if keyword in candidate:
            return "series"
    return None


def _extract_json(content: str) -> Dict:
    payload = content.strip()
    if payload.startswith("```"):
        payload = payload.strip("`").strip()
        if payload.endswith("```"):
            payload = payload[: payload.rfind("```")].strip()
    if not payload.startswith("{"):
        start = payload.find("{")
        end = payload.rfind("}")
        if start != -1 and end != -1:
            payload = payload[start : end + 1]
    if not payload.startswith("{"):
        raise ValueError("JSON object not found in response")
    return json.loads(payload)


def _ensure_extension(filename: str, extension: str) -> str:
    if not extension:
        return filename
    if filename.lower().endswith(extension.lower()):
        return filename
    stripped = filename.rstrip(". ")
    return f"{stripped}{extension}"


def suggest_strm_name(download: dict) -> Optional[Dict[str, Optional[str]]]:
    if not OPENROUTER_API_KEY:
        return None
    cache_key = download.get("file_name")
    if not cache_key:
        return None
    if cache_key in OPENROUTER_CACHE:
        return OPENROUTER_CACHE[cache_key]

    payload = {
        "model": OPENROUTER_MODEL,
        "temperature": 0.2,
        "max_tokens": 400,
        "messages": [{"role": "user", "content": _build_prompt(download)}],
    }

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}

    try:
        response = httpx.post(OPENROUTER_ENDPOINT, headers=headers, json=payload, timeout=OPENROUTER_TIMEOUT)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logging.debug("OpenRouter naming request failed: %s", exc)
        return None

    try:
        choices = response.json().get("choices") or []
        if not choices:
            logging.debug("OpenRouter returned no choices for %s", cache_key)
            return None
        content = choices[0].get("message", {}).get("content", "")
        suggestion = _extract_json(content)
    except (ValueError, json.JSONDecodeError) as exc:
        logging.debug("Failed to parse OpenRouter response for %s: %s", cache_key, exc)
        return None

    if not suggestion:
        return None

    filename = suggestion.get("filename")
    if filename:
        filename = _ensure_extension(filename.strip(), download.get("extension", ""))

    media_type = _normalize_media_type(suggestion.get("media_type")) or _normalize_media_type(
        download.get("metadata_mediatype")
    )

    result = {
        "filename": filename,
        "media_type": media_type,
    }

    OPENROUTER_CACHE[cache_key] = result
    logging.debug("OpenRouter naming suggestion %s for %s", result, cache_key)
    return result
