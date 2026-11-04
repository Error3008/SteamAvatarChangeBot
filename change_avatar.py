import asyncio
from core.avatar import get_next_hash, apply_avatar

async def main():
    sha = get_next_hash()
    if not sha:
        print("Error: No avatar hashes available!")
        return

    success, msg = await apply_avatar(sha)
    print(msg)

if __name__ == "__main__":
    asyncio.run(main())
