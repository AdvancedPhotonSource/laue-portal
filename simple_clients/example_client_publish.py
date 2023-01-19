#!/usr/bin/env python

## Basic Python import's
import argparse
from pprint import pprint

##
from datetime import datetime

## Base Gladier imports
from gladier import GladierBaseClient, generate_flow_definition

## Import tools that will be used on the flow definition
from tools.simple_publish import SimplePublish

##Generate flow based on the collection of `gladier_tools` 
# In this case `SimplePublish` was defined and imported from tools.simple_publish
@generate_flow_definition
class Example_Client(GladierBaseClient):
    gladier_tools = [
        SimplePublish,
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

    ## This is the search index that will be used
    search_index = '563c3d98-6fa8-4ef5-83e2-0f378efe0a5f'
    print('Example portal for search index: ' + search_index)
    print('https://acdc.alcf.anl.gov/globus-tutorial/' + search_index)
    print('')

    ## Flow inputs necessary for each tool on the flow definition.
    ## The search service needs the variables search_index, content, subject and visible_to

    metadata = {
        'title': 'Example Publish',
        'contributors': [args.name, 'Frank', 'Zapper'],
        'date': str(datetime.now()),
        'keywords': ['FCD#3', 'Blanket', 'Panic', ],
        'files': []
        }
        
    flow_input = {
        'input': {
            'search_index': search_index,
            'content': metadata,
            'subject': 'gladier_example_publish',
            'visible_to': ['public'],
        }
    }
    print('Created payload.')
    pprint(flow_input)
    print('')

    ##Label for the current run (This is the label that will be presented on the globus webApp)
    client_run_label = 'Gladier Publish Example'

    ##Flow execution
    flow_run = exampleClient.run_flow(flow_input=flow_input, label=client_run_label)

    print('Run started with ID: ' + flow_run['action_id'])
    print('https://app.globus.org/runs/' + flow_run['action_id'])
    print('')


    
