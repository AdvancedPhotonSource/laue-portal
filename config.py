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

MOTOR_GROUPS = {
    "sample":
        [
            "34ide:focusTHK:F",
            "34ide:focusTHK:H",
        ],
    "energy":
        [
            "34ide:monoE:keV",
        ],
    "depth": #wire or coded aperture
        [
            "34ide:focusAlio:H",
            "34ide:aero:c0:m1",
            "34ide:mxv:c0:m1",
            "34ide:mxv:c0:m3",
        ],
    "other":
        [
            "34ide:m58:c0:m6",
            "34ide:m58:c0:m8",
            "34ide:m58:c1:m1",
            "34ide:m58:c1:m2",
            "34ide:m58:c1:m3",
            "34ide:m58:c1:m5",
            "34ide:m58:c1:m7",

            "34ide:t80:c0:m1",
            "34ide:t80:c0:m2",
            "34ide:t80:c0:m3",

            "34ide:540:c0:out2",
            "34ide:540:c0:out3",
            "34ide:float6",
        ],
}