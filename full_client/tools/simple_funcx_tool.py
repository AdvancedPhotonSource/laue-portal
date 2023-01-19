from gladier import GladierBaseTool, generate_flow_definition

def simple_function(wfile = None, text = None, **data):
    import os

    if '~' in wfile:
        wfile = os.path.expanduser(wfile)

    with open(wfile,"w+") as file1:
        file1.writelines(text)

    return wfile

@generate_flow_definition
class SimpleTool(GladierBaseTool):
    funcx_functions = [simple_function]
    required_input = [
        'wfile',
        'name', 
        'funcx_endpoint_compute'
        ]
