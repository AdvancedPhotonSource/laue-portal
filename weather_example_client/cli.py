"""
The cli.py is a simple example of turning the Client defined in example_client.py
into a usable command line application. It allows for fungible input and also
adds a more user-friendly layer to anyone starting flows.

The example below allows for running the weather client with a set of custom
built-in cities, or alternatively custom coordinates.
"""

import argparse
from example_client import WeatherClient


cities = {
    'chicago': (41.8334,-88.0121),
    'las_vegas': (36.1164746,-115.2556887),
    'new_york': (40.6971494,-74.2598692),
}

def arg_parse():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lat', help='Custom Latitude', default=None)
    parser.add_argument('--long', help='Custom Longitude', default=None)
    parser.add_argument('--city', help='Check built-in City', default='chicago')
    return parser.parse_args()


if __name__ == '__main__':
    args = arg_parse()
    if args.lat or args.long:
        print('Using Custom latitude and longitude')
        coordinates = (args.latitude, args.longitude)
    else:
        if args.city not in cities.keys():
            raise ValueError(f'Available cities are {cities.keys()}')
        coordinates = cities[args.city]

    flow_input = {
        'input': {
            'coordinates': coordinates,
            # funcX tutorial endpoint
            'funcx_endpoint_compute': '4b116d3c-1703-4f8f-9f6f-39921e5864df',
        }
    }

    exampleClient = WeatherClient()
    flow_run = exampleClient.run_flow(flow_input=flow_input, label=f'Run with Coordinates: {coordinates}')
    run_id = flow_run['run_id']
    print(f'Starting: https://app.globus.org/runs/{run_id}/')