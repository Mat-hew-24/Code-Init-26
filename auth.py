import os
import getpass
import json
from pathlib import Path

TOKEN_PATH = Path.home() / ".gridx" / "token"


def login_user(email: str | None):
    if not email:
        email = input("Email: ").strip()

    password = getpass.getpass("Password: ")

    # 👇 mock validation
    if not email or not password:
        print("❌ Invalid credentials")
        return

    # pretend backend issued this token
    token = f"dev-token-{hash(email) & 0xfffffff}"

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(token)

    print("✅ Logged in successfully")
    print(f"Token saved to {TOKEN_PATH}")


def load_token() -> str:
    if not TOKEN_PATH.exists():
        raise Exception("Not logged in. Run `gridx login` first.")

    return TOKEN_PATH.read_text().strip()
