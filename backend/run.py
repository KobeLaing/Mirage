"""One command to run the API: applies migrations, then serves with uvicorn.

    python run.py            (add --reload while developing)
"""

import sys

import uvicorn

from app.config import get_settings
from app.db.migrate import upgrade_head
from app.logging_setup import configure_logging


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    upgrade_head(settings.database_url, settings.upload_dir)
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
        reload="--reload" in sys.argv,
        log_config=None,  # logging is configured by the app (JSON)
        server_header=False,
    )


if __name__ == "__main__":
    main()
