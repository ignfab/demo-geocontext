from langchain_core.tools import tool

@tool
def create_map(
    lon: float = None, lat: float = None, zoom: int = None,
    geojson_url: str = "", background: str = "osm"
) -> str:
    """Create a map and return it as an HTML string.

    Args:
        lon: center longitude (optional if geojson_url is provided)
        lat: center latitude (optional if geojson_url is provided)
        zoom: zoom level (optional, will auto-fit if geojson_url is provided and zoom is not specified)
        geojson_url: URL to a GeoJSON file to overlay on the map (optional)
        background: background layer name (default: "osm", can also use "gpf:GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2" for IGN France)

    Important: Don't create a map unless the user asks for it.
    """
    # Construire les attributs optionnels
    lon_attr = f'lon="{lon}"' if lon is not None else ""
    lat_attr = f'lat="{lat}"' if lat is not None else ""
    zoom_attr = f'zoom="{zoom}"' if zoom is not None else ""
    data_url_attr = f'data-url="{geojson_url}"' if geojson_url else ""
    width_attr="width=500px"
    height_attr="height=500px"

    # Utiliser fit-bounds si lon, lat ou zoom ne sont pas définis et qu'il y a des données
    fit_bounds_attr = ""
    if geojson_url and (lon is None or lat is None or zoom is None):
        fit_bounds_attr = 'fit-bounds="true"'
    
    # Fond gris en présence de données
    if geojson_url:
        background_greyscale_attr = f'background-greyscale=true'
    else:
        background_greyscale_attr = f'background-greyscale=false'
    
    # Construire la liste des attributs non vides
    attributes = [attr for attr in [lon_attr, lat_attr, zoom_attr, width_attr, height_attr, f'background="{background}"', data_url_attr, fit_bounds_attr, background_greyscale_attr] if attr]
    attributes_str = " ".join(attributes)

    return f"<ol-simple-map {attributes_str}></ol-simple-map>"


