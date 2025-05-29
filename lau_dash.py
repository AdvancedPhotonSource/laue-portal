import dash
import dash_bootstrap_components as dbc

# Assume images are numpy arrays
dbc_css = "https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates/dbc.min.css"
# Create a Dash application
app = dash.Dash(__name__, 
                external_stylesheets=[dbc.themes.FLATLY, dbc_css], 
                suppress_callback_exceptions=True,
                pages_folder="laue_portal/pages",)


app.layout = dash.page_container

# Run the application
if __name__ == '__main__':
    app.run(debug=True, port=2052, host='0.0.0.0')
    # try:
    #     app.run(debug=True, port=2052, host='0.0.0.0')
    # except:
    #     app.run_server(debug=True, port=2052, host='0.0.0.0')