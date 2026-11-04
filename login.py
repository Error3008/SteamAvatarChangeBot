import asyncio
from getpass import getpass
from core.auth import login

async def main():
    account_name = input("Input login: ")
    password = getpass("Input password (hidden): ")
    code = input("Steam Guard code (or press Enter for mobile approval): ").strip()
    success, msg = await login(account_name, password, code)
    print(msg)

if __name__ == "__main__":
    asyncio.run(main())
