from gladier import GladierBaseTool, generate_flow_definition

def will_it_rain(**data):
    """
    
    # Chicago
    url = 'https://api.weather.gov/points/41.8334,-88.0121'
    # Las Vegas
    url = 'https://api.weather.gov/points/36.1164746,-115.2556887'
    # New York
    url = 'https://api.weather.gov/points/40.6971494,-74.2598692'
    
    """
    lat, long = data['coordinates']
    url = f'https://api.weather.gov/points/{lat},{long}'

    import requests

    forecast = requests.get(url)
    forecast.raise_for_status()

    hourly_reports = requests.get(forecast.json()['properties']['forecastHourly'])
    hourly_reports.raise_for_status()

    short_forecasts = [p['shortForecast'] for p in hourly_reports.json()['properties']['periods']]
    combined_forecasts = ', '.join(short_forecasts)

    if 'Rain' in combined_forecasts:
        return "It's going to rain!"
    else:
        return "The weather looks clear"


@generate_flow_definition
class WillItRain(GladierBaseTool):
    funcx_functions = [will_it_rain]
    required_input = [
        'coordinates',
        'funcx_endpoint_compute'
        ]
    flow_input = {
        'coordinates': (41.8334,-88.0121)
    }