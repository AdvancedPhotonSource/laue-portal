from gladier import GladierBaseTool


class SimplePublish(GladierBaseTool):
    flow_definition = {
        'Comment': 'Publish metadata to Globus Search, with data from the result.',
        'StartAt': 'SimplePublish',
        'States': {
            'SimplePublish': {
                'Comment': 'Ingest a Globus Search document',
                'Type': 'Action',
                'ActionUrl': 'https://actions.globus.org/search/ingest',
                'ExceptionOnActionFailure': True,
                'InputPath': '$.input',
                'ResultPath': '$.SimplePublish',
                'WaitTime': 300,
                'End': True
            }
        },
    }
    required_input = [
        'search_index',
        'content',
        'subject',
        'visible_to',
    ]
