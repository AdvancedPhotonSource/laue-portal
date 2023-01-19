from gladier import GladierBaseTool


class SimpleTransfer(GladierBaseTool):

    flow_definition = {
        'Comment': 'Transfer a file or directory in Globus',
        'StartAt': 'SimpleTransfer',
        'States': {
            'SimpleTransfer': {
                'Comment': 'Transfer a file or directory in Globus',
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
