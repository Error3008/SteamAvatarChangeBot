import json
from pathlib import Path
from aiohttp import ClientSession, FormData
from .auth import get_authenticated_session

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config.json"
AVATARS_DIR = BASE_DIR / "avatars"

DEFAULT_CONFIG = {
    "interval_minutes": 15,
    "mode": "Sequential",
    "selected_hashes": [],
    "minimize_to_tray": False,
    "current_index": 0,
}

HEADERS = {
    "Referer": "https://steamcommunity.com/my/edit/avatar",
    "Origin": "https://steamcommunity.com",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
}

def load_config() -> dict:
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update(data)
        except Exception:
            pass
    return cfg

def save_config(cfg: dict) -> None:
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Error saving config: {e}")

async def apply_avatar(sha: str) -> tuple[bool, str]:
    session, err = await get_authenticated_session()
    if not session:
        return False, err

    try:
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
    session, err = await get_authenticated_session()
    if not session:
        print(f"Error: {err}")
        return []

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
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
