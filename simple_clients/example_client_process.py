#!/usr/bin/env python

##Basic Python import's
import argparse
from pprint import pprint

##Base Gladier imports
from gladier import GladierBaseClient, generate_flow_definition

##Import tools that will be used on the flow definition
from tools.simple_funcx_tool import SimpleTool

##Generate flow based on the collection of `gladier_tools` 
# In this case `SimpleTool` was defined and imported from tools.simple_funcx_tool 
@generate_flow_definition
class Example_Client(GladierBaseClient):
    gladier_tools = [
        SimpleTool,
    ]


##  Arguments for the execution of this file as a stand-alone client
def arg_parse():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', help='User Name', default='Bob')
    return parser.parse_args()

## Main execution of this "file" as a Standalone client
if __name__ == '__main__':

    args = arg_parse()


   ##The first step Client instance
    exampleClient = Example_Client()
    print('Flow created with ID: ' + exampleClient.get_flow_id())
    print('https://app.globus.org/flows/' + exampleClient.get_flow_id())
    print('')

    ## Flow inputs necessary for each tool on the flow definition.
    flow_input = {
        'input': {
            'name': args.name, 
            'wfile' : '/test/test.txt',

            # funcX tutorial endpoint
            'funcx_endpoint_compute': '4b116d3c-1703-4f8f-9f6f-39921e5864df',
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
    
