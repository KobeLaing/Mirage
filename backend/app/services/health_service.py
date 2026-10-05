import logging

from sqlalchemy.orm import Session

from app.repositories import maintenance_repo

log = logging.getLogger("mirage.health")


def database_ok(db: Session) -> bool:
    try:
        maintenance_repo.ping(db)
        return True
    except Exception:
        log.exception("health.database_unreachable")
        return False
