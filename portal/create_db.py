import laue_portal.database.db_schema as db_schema
import sqlalchemy
import argparse
"""
Contains the functions to create a new database file. 
When run as a standalone file, creats a file with the name provided as an argument.
"""


def create_db(engine):
    db_schema.Base.metadata.create_all(engine)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create a new database')
    parser.add_argument('db_name', type=str, help='Name of the database to create')

    args = parser.parse_args()
    engine = sqlalchemy.create_engine(f'sqlite:///{args.db_name}')

    create_db(engine)
    

