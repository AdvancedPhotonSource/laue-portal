from funcx_endpoint.endpoint.utils.config import Config 
from funcx_endpoint.executors import HighThroughputExecutor
from parsl.providers import LocalProvider 
import json
import os

config = Config(
    executors=[
        HighThroughputExecutor(
            provider=LocalProvider(
                init_blocks=1,
                min_blocks=0,
                max_blocks=1,
            ),
        )
    ]
)

with open('../uids.json') as uuids_f:
    uuids = json.load(uuids_f)

# For now, visible_to must be a list of URNs for globus auth users or groups, e.g.: 
# urn:globus:auth:identity:{user_uuid} 
# urn:globus:groups:id:{group_uuid} 
meta = { 
    "name": "laue_launch", 
    "description": "", 
    "organization": "", 
    "department": "", 
    "public": False, 
    "visible_to": [uuids['mprince_uid']] 
} 