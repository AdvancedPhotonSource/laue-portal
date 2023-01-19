#!/usr/bin/env python

##Basic Python import's
import argparse
from pprint import pprint
import os

##Base Gladier imports
from gladier import GladierBaseClient, generate_flow_definition

##Import tools that will be used on the flow definition
from tools.simple_transfer import SimpleTransfer

##Generate flow based on the collection of `gladier_tools` 
# In this case `SimpleTransfer` was defined and imported from tools.simple_transfer 
@generate_flow_definition
class Example_Client(GladierBaseClient):
    gladier_tools = [
        SimpleTransfer,
    ]

##  Arguments for the execution of this file as a stand-alone client
def arg_parse():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', help='Local Transfer Folder', default='~/demo')
    parser.add_argument('--file', help='Filename for awesome text', default='awesome.txt')
    return parser.parse_args()

## Main execution of this "file" as a Standalone client
if __name__ == '__main__':

    args = arg_parse()

    ##EDIT HERE
    # Local endpoint UUID (refer to README for more information)
    # https://www.globus.org/globus-connect-personal    
    localdir = os.path.expanduser(args.dir)
    local_endpoint_id = 'cde22510-5de7-11ec-9b5c-f9dfb1abb183' 
    ##

    if not os.path.exists(localdir):
        os.mkdir(localdir)

    ##creating a file to test the transfer
    with open(os.path.join(localdir,args.file),"w+") as file1:
        file1.writelines('Awesome Text!')



    ## A full link for both local and remote endpoints can be found below. 
    # The link should work otherwise it gives the user a manner of debugging permission to the endpoints/path
    # A transfer that cannot be done through the webApp will not be available to be done manually
    print('###')
    print('Monitor the data being transfered:')
    print('https://app.globus.org/file-manager?destination_id='+local_endpoint_id+'&destination_path=%2F~%2F&origin_id=ef4203ca-6510-466c-9bff-a5d2cc316673&origin_path=%2Fdemo%2Fanimals%2F')
    print('###')
    print('')

    ##The first step Client instance
    exampleClient = Example_Client()
    print('Flow created with ID: ' + exampleClient.get_flow_id())
    print('https://app.globus.org/flows/' + exampleClient.get_flow_id())
    print('')

    


    ## Flow inputs necessary for each tool on the flow definition.
    flow_input = {
        'input': {
            #local server information
            'simple_transfer_source_endpoint_id': local_endpoint_id,
            'simple_transfer_source_path': os.path.expanduser(args.dir),

            #remote server information
            'simple_transfer_destination_endpoint_id':'ef4203ca-6510-466c-9bff-a5d2cc316673',
            'simple_transfer_destination_path':'/demo/animals/',
        }
    }
    print('Created payload.')
    pprint(flow_input)
    print('')

    ##Label for the current run (This is the label that will be presented on the globus webApp)
    client_run_label = 'Gladier TransferFlow Example'

    #Flow execution
    flow_run = exampleClient.run_flow(flow_input=flow_input, label=client_run_label)

    print('Run started with ID: ' + flow_run['action_id'])
    print('https://app.globus.org/runs/' + flow_run['action_id'])
    

