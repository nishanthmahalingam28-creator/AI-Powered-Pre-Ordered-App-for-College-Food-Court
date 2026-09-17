#!/usr/bin/env python3
"""
Command-Line Administrator Account Provisioning & Password Reset Tool.

Usage:
  Interactive (prompted):
    python backend/manage_admin.py

  Non-Interactive (flags):
    python backend/manage_admin.py --email admin@kpriet.ac.in --password mysecurepassword

  Environment Variables:
    ADMIN_EMAIL=admin@kpriet.ac.in ADMIN_PASSWORD=mysecurepassword python backend/manage_admin.py
"""

import os
import sys
import argparse
import getpass

# Add backend to sys.path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv
load_dotenv()

from services.admin_bootstrap import create_or_reset_admin, validate_admin_email


def main():
    parser = argparse.ArgumentParser(description="Food Court Admin Account Provisioning & Password Reset Tool")
    parser.add_argument("--email", "-e", help="Administrator email address (e.g. admin@kpriet.ac.in)")
    parser.add_argument("--password", "-p", help="Administrator password (min 6 characters)")
    args = parser.parse_args()

    email = args.email or os.getenv("ADMIN_EMAIL")
    password = args.password or os.getenv("ADMIN_PASSWORD")

    # If email not provided, prompt interactively
    if not email:
        default_email = "admin@kpriet.ac.in"
        input_email = input(f"Enter administrator email [{default_email}]: ").strip()
        email = input_email if input_email else default_email

    if not validate_admin_email(email):
        print(f"Error: Invalid email format '{email}'", file=sys.stderr)
        sys.exit(1)

    # If password not provided, securely prompt interactively
    if not password:
        password = getpass.getpass("Enter administrator password (min 6 chars): ").strip()
        confirm = getpass.getpass("Confirm administrator password: ").strip()
        if password != confirm:
            print("Error: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    if len(password) < 6:
        print("Error: Password must be at least 6 characters long.", file=sys.stderr)
        sys.exit(1)

    try:
        res = create_or_reset_admin(email, password)
        print(f"\nSUCCESS: Administrator account for '{res['email']}' was {res['action']} successfully!")
        print("You can now log in at: /pages/admin/login.html\n")
    except Exception as err:
        print(f"\nFAILURE: Could not create or reset administrator account: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
