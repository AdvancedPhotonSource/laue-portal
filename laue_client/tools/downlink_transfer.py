##Import tools that will be used on the flow definition
from gladier import GladierBaseTool


class DownlinkTransfer(GladierBaseTool):
    flow_definition = {
        'Comment': 'Transfer laue result data to APS systems',
        'StartAt': 'DownlinkTransfer',
        'States': {
            'DownlinkTransfer': {
                'Comment': 'Transfer laue data to ALCF systems',
                'Type': 'Action',
                'ActionUrl': 'https://actions.automate.globus.org/transfer/transfer',
                'Parameters': {
                    'source_endpoint_id.$': '$.input.downlink_source_endpoint_id',
                    'destination_endpoint_id.$': '$.input.downlink_destination_endpoint_id',
                    'transfer_items': [
                        {
                            'source_path.$': '$.input.downlink_source_path',
                            'destination_path.$': '$.input.downlink_destination_path',
                            'recursive.$': '$.input.downlink_recursive',
                        }
                    ]
                },
                'ResultPath': '$.downlinkTransfer',
                'WaitTime': 600,
                'End': True
            },
        }
    }

    flow_input = {
        'downlink_sync_level': 'checksum',
        'downlink_recursive': True,
    }
    required_input = [
        'downlink_source_path',
        'downlink_destination_path',
        'downlink_source_endpoint_id',
        'downlink_destination_endpoint_id',
    ]
