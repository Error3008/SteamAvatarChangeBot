import asyncio
import json
import os
from pathlib import Path
from dotenv import set_key, load_dotenv
from aiosteampy.session import SteamSession, GuardConfirmationRequired

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

def get_session_file() -> Path | None:
    session_env = os.getenv("STEAM_SESSION_FILE")
    if session_env and Path(session_env).exists():
        return Path(session_env)
    return next(BASE_DIR.glob("*.session.json"), None)

def get_active_account() -> str:
    p = get_session_file()
    if p and p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data.get("account_name", p.stem.replace(".session", ""))
        except Exception:
            return p.stem.replace(".session", "")
    return "None"

async def validate_session() -> tuple[bool, str]:
    p = get_session_file()
    if not p or not p.exists():
        return False, "No active session file found."

    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return False, "Corrupted session file."

    session = None
    try:
        session = SteamSession.deserialize(data)
        if session.refresh_token.expired:
            return False, "Session refresh token expired."

        if session.access_token.expired:
            await session.refresh()
            await session.obtain_cookies()
            with open(p, "w", encoding="utf-8") as f:
                json.dump(session.serialize(), f, indent=2)

        account = session.account_name or p.stem.replace(".session", "")
        return True, account
    except Exception as e:
        return False, f"Session invalid: {e}"
    finally:
        if session:
            await session.transport.close()

async def login(account_name: str, password: str, guard_code: str = "") -> tuple[bool, str]:
    session = SteamSession()

    try:
        await session.with_credentials(account_name, password)
    except GuardConfirmationRequired as e:
        code = guard_code.strip()
        if e.device_code:
            if code:
                await session.submit_auth_code(code, "device")
        elif e.email_code:
            if code:
                await session.submit_auth_code(code, "email")
            else:
                await session.transport.close()
                return False, "Email confirmation code is required."
    except Exception as e:
        await session.transport.close()
        return False, f"Login error: {e}"

    try:
        await session.finalize(timeout=60)
        await session.obtain_cookies()
    except Exception as e:
        await session.transport.close()
        return False, f"Session finalization error: {e}"
    finally:
        await session.transport.close()

    session_file = BASE_DIR / f"{account_name}.session.json"
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(session.serialize(), f, indent=2)

    ENV_PATH.touch(exist_ok=True)
    set_key(str(ENV_PATH), "STEAM_SESSION_FILE", str(session_file))

    return True, f"Successfully logged in as {account_name}"
