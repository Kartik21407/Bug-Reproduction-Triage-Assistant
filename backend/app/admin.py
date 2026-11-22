"""Command line for whoever operates the server to manage administrators.

There is no way to become an administrator through the API or the
interface: it is granted here, by someone with access to the server
(US-03 criterion 3, ADR-030).

    python -m app.admin make-admin EMAIL
    python -m app.admin revoke-admin EMAIL
    python -m app.admin list-admins

Inside Docker Compose, prefix with `docker compose exec backend`.
"""

import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import User


def set_admin(db: Session, email: str, is_admin: bool) -> str:
    """Grants or removes the administrator role, and says what happened.
    Raises LookupError for an unknown email."""
    user = db.execute(select(User).where(User.email == email.strip().lower())).scalar_one_or_none()
    if user is None:
        raise LookupError(f"No account with the email {email}")
    if user.is_admin == is_admin:
        return f"{user.email} {'is already' if is_admin else 'is not'} an administrator."
    user.is_admin = is_admin
    db.commit()
    return f"{user.email} {'is now' if is_admin else 'is no longer'} an administrator."


def admin_emails(db: Session) -> list[str]:
    return list(
        db.execute(select(User.email).where(User.is_admin.is_(True)).order_by(User.email))
        .scalars()
        .all()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.admin")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, text in (
        ("make-admin", "Make an existing account an administrator"),
        ("revoke-admin", "Remove the administrator role from an account"),
    ):
        command = commands.add_parser(name, help=text)
        command.add_argument("email")
    commands.add_parser("list-admins", help="List every administrator")
    args = parser.parse_args(argv)

    # Imported here so `--help` works without a database configured.
    from app.db import SessionLocal

    with SessionLocal() as db:
        if args.command == "list-admins":
            emails = admin_emails(db)
            print("\n".join(emails) if emails else "There are no administrators yet.")
            return 0
        try:
            print(set_admin(db, args.email, is_admin=args.command == "make-admin"))
        except LookupError as error:
            print(error, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
