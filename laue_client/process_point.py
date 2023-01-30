import argparse
from pprint import pprint
import json
import os

##Base Gladier imports
from gladier import GladierBaseClient, generate_flow_definition

##Import tools that will be used on the flow definition
from tools.uplink_transfer import UplinkTransfer

##Generate flow based on the collection of `gladier_tools` 
# In this case `SimpleTransfer` was defined and imported from tools.simple_transfer 
@generate_flow_definition
class Example_Client(GladierBaseClient):
    gladier_tools = [
        UplinkTransfer,
    ]

##  Arguments for the execution of this file as a stand-alone client
def arg_parse():
    parser = argparse.ArgumentParser()
    parser.add_argument('point_path', help='Unique point ID')
    return parser.parse_args()

## Main execution of this "file" as a Standalone client
if __name__ == '__main__':

    args = arg_parse()

    with open('laue_conf.json') as conf_f:
        conf = json.load(conf_f)

    ##The first step Client instance
    exampleClient = Example_Client()


    ## Flow inputs necessary for each tool on the flow definition.
    src_path = os.path.join(conf['voyager']['staging'], args.point_path)
    dest_path = os.path.join(conf['eagle']['staging'], args.point_path)
    flow_input = {
        'input': {
            #local server information
            'simple_transfer_source_endpoint_id': conf['voyager']['uuid'],
            'simple_transfer_source_path': src_path, 

            #remote server information
            'simple_transfer_destination_endpoint_id': conf['eagle']['uuid'],
            'simple_transfer_destination_path': dest_path,
        }
    }
    print('Created payload.')
    pprint(flow_input)
    print('')

    ##Label for the current run (This is the label that will be presented on the globus webApp)
    client_run_label = 'Laue Uplink'

    #Flow execution
    flow_run = exampleClient.run_flow(flow_input=flow_input, label=client_run_label)

    print('Run started with ID: ' + flow_run['action_id'])
    print('https://app.globus.org/runs/' + flow_run['action_id'])
    