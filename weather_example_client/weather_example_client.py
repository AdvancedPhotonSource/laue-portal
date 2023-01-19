import pprint
from gladier import GladierBaseClient, generate_flow_definition
from tools.will_it_rain import WillItRain


@generate_flow_definition
class WeatherClient(GladierBaseClient):
    gladier_tools = [
        WillItRain,
    ]


if __name__ == '__main__':
    """__main__ is a handy way to test the functionality of a flow. It's a bit more
    rigid since the ``flow_input`` below needs to be manually modified for each run,
    but it provides an easy way to test the tools defined above in ``gladier_tools``"""
    flow_input = {
        'input': {
            'coordinates' : (41.8334,-88.0121),
            # funcX tutorial endpoint
            'funcx_endpoint_compute': '4b116d3c-1703-4f8f-9f6f-39921e5864df',
        }
    }
    weather_client = WeatherClient()
    flow_run = weather_client.run_flow(flow_input=flow_input, label='test_run')
    weather_client.progress(flow_run['run_id'])
    pprint.pprint(weather_client.get_status(flow_run['run_id']))
