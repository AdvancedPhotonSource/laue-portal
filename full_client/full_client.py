#!/usr/bin/env python

##Basic Python import's
import argparse
from pprint import pprint

##Base Gladier imports
from gladier import GladierBaseClient, generate_flow_definition

##Import tools that will be used on the flow definition
from tools.simple_funcx_tool import SimpleTool
from tools.gather_metadata import GatherMetadata

from gladier_tools.globus.transfer import Transfer
from gladier_tools.publish import Publish

##Generate flow based on the collection of `gladier_tools` 
@generate_flow_definition(
    modifiers={
        "publish_gather_metadata": {
            "WaitTime": 240,
            "payload": "$.GatherMetadata.details.result[0].pilot",
        },
    }
)
class Example_Client(GladierBaseClient):
    gladier_tools = [
        Transfer,
        SimpleTool,
        GatherMetadata,
        Publish
    ]


## Main client
def run_flow(event):
   ##The first step Client instance
    exampleClient = Example_Client()
    print('Flow created with ID: ' + exampleClient.get_flow_id())
    print('https://app.globus.org/flows/' + exampleClient.get_flow_id())
    print('')

    ## Flow inputs necessary for each tool on the flow definition.
    flow_input = {
        'input': {            
            #Transfer variables
            'transfer_source_endpoint_id':'',
            'transfer_source_path':'',
            'transfer_destination_endpoint_id':'',
            'transfer_destination_path':'',
            'transfer_recursive':True,

            #Proccess variables
            'name': args.name, 
            'wfile' : '/test/test.txt',

            # funcX tutorial endpoint
            'funcx_endpoint_compute': '4b116d3c-1703-4f8f-9f6f-39921e5864df',
            'funcx_endpoint_non_compute': '4b116d3c-1703-4f8f-9f6f-39921e5864df',

            'pilot':{}
        }
    }
    print('Created payload.')
    pprint(flow_input)
    print('')

    ##Label for the current run (This is the label that will be presented on the globus webApp)
    client_run_label = 'Gladier SingleTool Example'

    ##Flow execution
    flow_run = exampleClient.run_flow(flow_input=flow_input, label=client_run_label)

    print('Run started with ID: ' + flow_run['action_id'])
    print('https://app.globus.org/runs/' + flow_run['action_id'])

##  Arguments for the execution of this file as a stand-alone client
def arg_parse():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', help='User Name', default='Bob')
    return parser.parse_args()

## Main execution of this "file" as a Standalone client
if __name__ == '__main__':

    args = arg_parse()
    run_flow(args.name)
    
