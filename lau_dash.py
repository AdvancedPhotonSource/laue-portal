import dash
import dash_bootstrap_components as dbc
import laue_portal.database.db_schema as db_schema
import sqlalchemy
import os
import config
import logging

dbc_css = "https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates/dbc.min.css"


def ensure_database_exists():
    """
    Ensure the database file exists and create it if it doesn't.
    """
    db_path = config.db_file
    
    # Check if database file exists
    if not os.path.exists(db_path):
        logging.info(f"Database file '{db_path}' not found. Creating new database...")
        
        engine = sqlalchemy.create_engine(f'sqlite:///{db_path}')
        db_schema.Base.metadata.create_all(engine)
        
        logging.info(f"Database '{db_path}' created successfully with all tables.")
    else:
        logging.info(f"Database file '{db_path}' already exists. Running on existing database.")


app = dash.Dash(__name__, 
                external_stylesheets=[dbc.themes.FLATLY, dbc_css], 
                suppress_callback_exceptions=True,
                pages_folder="laue_portal/pages",)


app.layout = dash.page_container

if __name__ == '__main__':
    ensure_database_exists()
    app.run(debug=True, port=2052, host='0.0.0.0')