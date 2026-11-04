import asyncio
import json
from pathlib import Path
from aiosteampy.session import SteamSession, GuardConfirmationRequired

BASE_DIR = Path(__file__).resolve().parent.parent
SESSION_FILE = BASE_DIR / "session.json"

def get_session_file() -> Path | None:
    if SESSION_FILE.exists():
        return SESSION_FILE
    # Auto-migrate legacy *.session.json if found
    for legacy in BASE_DIR.glob("*.session.json"):
        try:
            legacy.rename(SESSION_FILE)
            return SESSION_FILE
        except Exception:
            return legacy
    return None

async def get_authenticated_session() -> tuple[SteamSession | None, str]:
    p = get_session_file()
    if not p or not p.exists():
        return None, "No active session file found."

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        session = SteamSession.deserialize(data)
    except Exception as e:
        return None, f"Corrupted session file: {e}"

    try:
        if session.refresh_token.expired:
            await session.transport.close()
            return None, "Session refresh token expired."

        if session.access_token.expired:
            await session.refresh()
            await session.obtain_cookies()
            p.write_text(json.dumps(session.serialize(), indent=2), encoding="utf-8")

        account = session.account_name or "Steam User"
        return session, account
    except Exception as e:
        await session.transport.close()
        return None, f"Session invalid: {e}"

async def validate_session() -> tuple[bool, str]:
    session, info = await get_authenticated_session()
    if not session:
        return False, info
    await session.transport.close()
    return True, info

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

    SESSION_FILE.write_text(json.dumps(session.serialize(), indent=2), encoding="utf-8")
    return True, f"Successfully logged in as {account_name}"
