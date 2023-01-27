#!/usr/bin/env python

##Basic Python import's
import argparse
from pprint import pprint
import os

##Base Gladier imports
from gladier import GladierBaseClient, generate_flow_definition

##Import tools that will be used on the flow definition
from tools.simple_transfer import SimpleTransfer
from gladier import GladierBaseTool


class UplinkTransfer(GladierBaseTool):

    flow_definition = {
        'Comment': 'Transfer laue data to ALCF systems',
        'StartAt': 'UplinkTransfer',
        'States': {
            'UplinkTransfer': {
                'Comment': 'Transfer laue data to ALCF systems',
                'Type': 'Action',
                'ActionUrl': 'https://actions.automate.globus.org/transfer/transfer',
                'Parameters': {
                    'source_endpoint_id.$': '$.input.simple_transfer_source_endpoint_id',
                    'destination_endpoint_id.$': '$.input.simple_transfer_destination_endpoint_id',
                    'transfer_items': [
                        {
                            'source_path.$': '$.input.simple_transfer_source_path',
                            'destination_path.$': '$.input.simple_transfer_destination_path',
                            'recursive.$': '$.input.simple_transfer_recursive',
                        }
                    ]
                },
                'ResultPath': '$.SimpleTransfer',
                'WaitTime': 600,
                'End': True
            },
        }
    }

    flow_input = {
        'simple_transfer_sync_level': 'checksum',
        'simple_transfer_recursive': True,
    }
    required_input = [
        'simple_transfer_source_path',
        'simple_transfer_destination_path',
        'simple_transfer_source_endpoint_id',
        'simple_transfer_destination_endpoint_id',
    ]
