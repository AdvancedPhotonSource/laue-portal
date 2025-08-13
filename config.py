db_file = 'Laue_Records.db'

DEFAULT_VARIABLES = {
    "author": "",
    "notes": "",
    "root_path": "/net/s34data/export/s34data1/LauePortal/portal_workspace/",
    "num_threads": 35,
    "memory_limit_mb": 50000,
    "verbose": 1,
}

REDIS_CONFIG = {
    "host": "localhost",
    #"port": 6379,
    "port": 6379,
}

DASH_CONFIG = {
    "host": "localhost",
    "port": 2052,
    "debug": True,
}