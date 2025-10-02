import dash
import dash_bootstrap_components as dbc
from laue_portal.database.session_utils import init_db, get_engine
import laue_portal.database.db_utils as db_utils
from laue_portal.processing.redis_utils import init_redis_status
import os
import config
import logging

dbc_css = "https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates/dbc.min.css"


def ensure_database_exists():
    """
    Ensure the database file exists and create it if it doesn't.
    Uses the shared engine and centralized init_db/load_all_models to
    guarantee all ORM mappers are loaded before table creation.
    """
    db_path = config.db_file
    file_exists = os.path.exists(db_path)
    if not file_exists:
        logging.info(f"Database file '{db_path}' not found. Creating new database...")

    # Ensure tables exist on the shared app engine (idempotent) and create file if missing
    init_db()

    if not file_exists:
        logging.info(f"Database '{db_path}' created successfully with all tables.")
    else:
        logging.info(f"Database file '{db_path}' already exists. Running on existing database.")


# Initialize Redis status BEFORE creating the Dash app
# This ensures the status is set before pages (and navbar) are imported
init_redis_status()

app = dash.Dash(__name__, 
                external_stylesheets=[dbc.themes.FLATLY, dbc_css, dbc.icons.BOOTSTRAP], 
                suppress_callback_exceptions=True,
                pages_folder="laue_portal/pages",)


app.layout = dash.page_container

if __name__ == '__main__':
    ensure_database_exists()
    app.run(debug=config.DASH_CONFIG['debug'], port=config.DASH_CONFIG['port'], host=config.DASH_CONFIG['host'])
