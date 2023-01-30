import argparse
from pprint import pprint
import json
import os

##Base Gladier imports
from gladier import GladierBaseClient, generate_flow_definition

##Import tools that will be used on the flow definition
from tools.uplink_transfer import UplinkTransfer
from tools.run_laue import QSubLaunch
from tools.downlink_transfer import DownlinkTransfer

##Generate flow based on the collection of `gladier_tools` 
# In this case `SimpleTransfer` was defined and imported from tools.uplink 
@generate_flow_definition
class LaueClient(GladierBaseClient):
    gladier_tools = [
        UplinkTransfer,
        QSubLaunch,
        DownlinkTransfer
    ]

##  Arguments for the execution of this file as a stand-alone client
def arg_parse():
    parser = argparse.ArgumentParser()
    parser.add_argument('point_path', help='Unique point ID')
    parser.add_argument('im_num', help='Temp image number to process')
    return parser.parse_args()

## Main execution of this "file" as a Standalone client
if __name__ == '__main__':

    args = arg_parse()

    with open('laue_conf.json') as conf_f:
        conf = json.load(conf_f)

    with open('uids.json') as uids_f:
        uids = json.load(uids_f)

    ##The first step Client instance
    exampleClient = LaueClient()


    ## Flow inputs necessary for each tool on the flow definition.
    up_src_path = os.path.join(conf['voyager']['staging'], args.point_path)
    up_dest_path = os.path.join(conf['eagle']['staging'], args.point_path)
    down_fp = f'im_{args.im_num}_r0.hdf5' # TEMP
    down_src_path = os.path.join('results', args.point_path)
    down_dest_path = os.path.join(conf['voyager']['staging'], 'results', args.point_path) 
    flow_input = {
        'input': {
            # To Eagle
            'uplink_source_endpoint_id': conf['voyager']['uuid'],
            'uplink_source_path': up_src_path, 
            'uplink_destination_endpoint_id': conf['eagle']['uuid'],
            'uplink_destination_path': up_dest_path,

            # QSub Launch
            'im_dir': os.path.join('/eagle', up_dest_path[1:]),
            'out_dir': os.path.join('/eagle', down_src_path),
            'im_num': args.im_num,
            'funcx_endpoint_compute': uids['endpoint'], 

            # From Eagle
            'downlink_source_endpoint_id': conf['eagle']['uuid'],
            'downlink_source_path': down_src_path,
            'downlink_destination_endpoint_id': conf['voyager']['uuid'],
            'downlink_destination_path': down_dest_path,
        }
    }
    print('Created payload.')
    pprint(flow_input)
    print('')

    ##Label for the current run (This is the label that will be presented on the globus webApp)
    client_run_label = 'Laue Cold Processing'

    #Flow execution
    flow_run = exampleClient.run_flow(flow_input=flow_input, label=client_run_label)

    print('Run started with ID: ' + flow_run['action_id'])
    print('https://app.globus.org/runs/' + flow_run['action_id'])
    