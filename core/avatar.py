import asyncio
import json
import os
from pathlib import Path
from aiohttp import ClientSession, FormData
from aiosteampy.session import SteamSession

from .auth import get_session_file

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config.json"
AVATARS_DIR = BASE_DIR / "avatars"
STATE_FILE = BASE_DIR / "avatar_state.txt"

DEFAULT_HASHES = [
    "fbfe9b170b5ba5928f0a9ba8f67f6e7c8ae4b2bd",
]

HEADERS = {
    "Referer": "https://steamcommunity.com/my/edit/avatar",
    "Origin": "https://steamcommunity.com",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:158.0) Gecko/20100101 Firefox/158.0",
}

def get_avatar_hashes() -> list[str]:
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if cfg.get("selected_hashes"):
                return cfg["selected_hashes"]
        except Exception:
            pass
    return DEFAULT_HASHES

def get_next_hash() -> str:
    hashes = get_avatar_hashes()
    if not hashes:
        return ""
    idx = int(STATE_FILE.read_text().strip()) if STATE_FILE.exists() else 0
    current_sha = hashes[idx % len(hashes)]
    STATE_FILE.write_text(str((idx + 1) % len(hashes)))
    return current_sha

async def apply_avatar(sha: str) -> tuple[bool, str]:
    session_file = get_session_file()
    if not session_file or not session_file.exists():
        return False, "Session file not found"

    with open(session_file, "r", encoding="utf-8") as f:
        session = SteamSession.deserialize(json.load(f))

    try:
        if session.access_token.expired:
            await session.refresh()
            await session.obtain_cookies()
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(session.serialize(), f, indent=2)

        form = FormData()
        form.add_field("sessionid", session.session_id)
        form.add_field("json", "1")
        form.add_field("sha", sha)

        resp = await session.transport.request(
            "POST",
            "https://steamcommunity.com/actions/selectPreviousAvatar",
            data=form,
            headers=HEADERS,
        )

        if resp.status == 200:
            return True, f"[200] Avatar changed to hash {sha}!"
        return False, f"[{resp.status}] Response error"
    except Exception as e:
        return False, f"Error: {e}"
    finally:
        await session.transport.close()

async def fetch_recent_avatars(output_dir: Path = AVATARS_DIR) -> list[str]:
    session_file = get_session_file()
    if not session_file or not session_file.exists():
        print("Error: Session file not found!")
        return []

    with open(session_file, "r", encoding="utf-8") as f:
        session = SteamSession.deserialize(json.load(f))

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        if session.access_token.expired:
            await session.refresh()
            await session.obtain_cookies()
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(session.serialize(), f, indent=2)

        token = session.access_token.raw
        url = f"https://api.steampowered.com/ICommunityService/GetAvatarHistory/v1/?access_token={token}"

        form = FormData()
        form.add_field("input_json", json.dumps({
            "steamid": str(session.steam_id),
            "filter_user_uploaded_only": True,
        }))

        resp = await session.transport.request("POST", url, data=form)
        if resp.status != 200:
            print(f"[{resp.status}] Failed to fetch avatar history")
            return []

        raw_content = resp.content
        if isinstance(raw_content, dict):
            payload = raw_content
        elif isinstance(raw_content, (bytes, bytearray)):
            payload = json.loads(raw_content.decode("utf-8"))
        else:
            payload = json.loads(raw_content)

        avatars = payload.get("response", {}).get("avatars", [])
        hashes = [item["avatar_sha1"] for item in avatars if "avatar_sha1" in item]

        if not hashes:
            print("No recent avatars found on Steam.")
            return []

        print(f"Found {len(hashes)} recent avatars on Steam.")

        existing_files = {p.stem for p in output_dir.glob("*.jpg")}

        async with ClientSession() as http:
            for sha in hashes:
                file_path = output_dir / f"{sha}.jpg"
                if sha in existing_files or file_path.exists():
                    print(f"Skipping {sha}.jpg (already exists)")
                    continue

                img_url = f"https://avatars.steamstatic.com/{sha}_full.jpg"
                async with http.get(img_url) as img_resp:
                    if img_resp.status == 200:
                        file_path.write_bytes(await img_resp.read())
                        print(f"Downloaded {sha}.jpg")
                    else:
                        print(f"[{img_resp.status}] Failed to download {sha}.jpg")

        return hashes
    finally:
        await session.transport.close()
