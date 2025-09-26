import folium
import requests

from langchain_core.tools import tool

@tool
def create_map(lon: float, lat: float) -> str:
    """Create a map centered at the given longitude and latitude and return it as an HTML string.

    Args:
        lon: center longitude
        lat: center latitude
    """
    
    return f"""

<p>Carte centrée sur (lon: {lon}, lat: {lat})</p>
<ol-map lon="{lon}" lat="{lat}" zoom="12" style="width: 100%; height: 400px;">
    <ol-layer-openstreetmap></ol-layer-openstreetmap>
    <ol-layer-vector>
        <ol-marker-icon src="https://openlayers.org/en/latest/examples/data/icon.png" lon="{lon}" lat="{lat}" />
    </ol-layer-vector>    
</ol-map>
    """


