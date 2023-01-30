##Import tools that will be used on the flow definition
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
                    'source_endpoint_id.$': '$.input.uplink_source_endpoint_id',
                    'destination_endpoint_id.$': '$.input.uplink_destination_endpoint_id',
                    'transfer_items': [
                        {
                            'source_path.$': '$.input.uplink_source_path',
                            'destination_path.$': '$.input.uplink_destination_path',
                            'recursive.$': '$.input.uplink_recursive',
                        }
                    ]
                },
                'ResultPath': '$.UplinkTransfer',
                'WaitTime': 600,
                'End': True
            },
        }
    }

    flow_input = {
        'uplink_sync_level': 'checksum',
        'uplink_recursive': True,
    }
    required_input = [
        'uplink_source_path',
        'uplink_destination_path',
        'uplink_source_endpoint_id',
        'uplink_destination_endpoint_id',
    ]
