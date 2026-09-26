import logging
import sys
from app.core.config import settings

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging():
    level = logging.DEBUG if settings.app_env == "development" else logging.INFO
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    # Suppress overly noisy third party loggers
    logging.getLogger("passlib").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return logging.getLogger("sih26027")


logger = setup_logging()
