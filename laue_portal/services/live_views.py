"""Small publication-revision queries; scientific files are opened only on change."""

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from laue_portal.database import db_schema as db
from laue_portal.database import session_utils


def publication(run_id, kind, *, engine=None):
    column = db.LiveSession.reconstruction_id if kind == "reconstruction" else db.LiveSession.indexing_id
    try:
        with Session(engine or session_utils.get_engine()) as session:
            row = session.execute(
                select(db.LiveSession.id, db.LiveSession.revision, db.LiveSession.state).where(column == run_id)
            ).first()
    except OperationalError as error:
        if "no such table: live_session" in str(error):
            return None
        raise
    return dict(row._mapping) if row else None
