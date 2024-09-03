import laue_portal.database.db_utils as du
import yaml
import laue_portal.database.db_schema as db_schema
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import datetime

if __name__ == '__main__':
    with open('laue_portal/tests/configs/config-calibrate3x1800-1.yml', 'r') as f:
        recon_object = yaml.safe_load(f)

    engine = create_engine('sqlite:///CA_params.db')

    metadata = db_schema.Base.metadata

    recon_row = du.import_recon_row(recon_object)
    recon_row.date = datetime.datetime.now()
    recon_row.commit_id = 'TEST'
    recon_row.calib_id = 'TEST'
    recon_row.runtime = 'TEST'
    recon_row.computer_name = 'TEST'
    recon_row.dataset_id = 0
    recon_row.notes = 'TEST'


    with Session(engine) as session:
        metadata.create_all(engine)
        session.add(recon_row)
        session.commit()
