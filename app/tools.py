from langchain_core.tools import tool

@tool
def create_map(
    lon: float = None, lat: float = None, zoom: int = None,
    geojson_url: str = "", background: str = "osm"
) -> str:
    """Crée une carte et la renvoie sous forme d'un seul fragment HTML.

    La valeur de retour est une balise ``<ol-simple-map ...></ol-simple-map>`` à
    recopier **à l'identique** (mêmes attributs, même ordre) dans la prochaine
    réponse assistant en markdown, à l'endroit où la carte doit apparaître
    (par ex. après une phrase d'introduction, puis le texte explicatif peut
    suivre). Sans ce fragment dans cette réponse, la carte ne s'affiche pas
    dans le chat.

    Paramètres :
        lon : longitude du centre (optionnelle si `geojson_url` est fourni)
        lat : latitude du centre (optionnelle si `geojson_url` est fourni)
        zoom : niveau de zoom (optionnel, ajustement automatique si `geojson_url` est fourni et `zoom` n'est pas défini)
        geojson_url : URL d'un fichier GeoJSON à superposer sur la carte (optionnel)
        background : nom de la couche de fond (par défaut : "osm", peut aussi être "gpf:GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2" pour l'IGN France)

    Important :
    - Ne crée pas de carte si l'utilisateur ne le demande pas.
    - L'outil prend en charge une seule couche de données GeoJSON (n'essaie pas de passer plusieurs URL dans un seul appel).
    - Ne jamais construire l'URL `geojson_url` manuellement. Toujours utiliser `gpf_wfs_get_features` avec `result_type: "request"` au préalable pour obtenir les informations nécessaires.
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
