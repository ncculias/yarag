import argparse
import getpass

from yarag.db import SessionLocal, init_db
from yarag.models import User
from yarag.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="建立使用者帳號")
    parser.add_argument("username")
    parser.add_argument("display_name")
    args = parser.parse_args()
    password = getpass.getpass("密碼：")
    if len(password) < 8:
        raise SystemExit("密碼至少 8 個字元")
    init_db()
    with SessionLocal() as db:
        db.add(
            User(
                username=args.username,
                display_name=args.display_name,
                password_hash=hash_password(password),
            )
        )
        db.commit()
    print(f"已建立帳號 {args.username}")


if __name__ == "__main__":
    main()
