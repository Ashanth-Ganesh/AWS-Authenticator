"""Apache entry point. Secrets live outside the repository on EC2."""

from pathlib import Path

from dotenv import load_dotenv

config = Path("/etc/aws-authenticator.env")
if config.is_file():
    load_dotenv(config)

from backend.app import create_app

application = create_app()
