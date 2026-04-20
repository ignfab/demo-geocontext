import TileLayer from "ol/layer/Tile";
import { ImageTile, OSM } from "ol/source";

/**
 * Create a TMS url from a layer name
 *
 * - GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2 : Plan IGN
 * - ORTHOIMAGERY.ORTHOPHOTOS : Photographies aériennes
 * - CADASTRALPARCELS.PARCELLAIRE_EXPRESS : Parcelles cadastrales
 * 
 * @see https://data.geopf.fr/wmts?SERVICE=WMTS&VERSION=1.0.0&REQUEST=GetCapabilities
 * 
 * @param layerName the layer name (ex : GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2)
 * @returns the TMS url of the geoplateforme
 */
function getGeoplateformeUrlTMS(layerName: string) {
    let url = "https://data.geopf.fr/wmts?SERVICE=WMTS&VERSION=1.0.0&REQUEST=GetTile";
    url += "&LAYER=" + layerName;
    url += "&STYLE=normal&FORMAT=image/png";
    url += "&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}";
    return url;
}

/**
 * Hack to fetch GeoJSON features from Geoplateforme WFS using POST
 * request with cql_filter to support large geometries (issue #57)
 *
 * @param url 
 */
export async function getFeaturesFromGeoplateformeWFS(url: string): Promise<any> {
    const queryParams = new URLSearchParams(url.split('?')[1]);
    const cqlFilter = queryParams.get('cql_filter') ?? queryParams.get('CQL_FILTER');
    if ( cqlFilter ) {
        // Use POST request with cql_filter in body to avoid too-long GET URLs (issue #57)
        queryParams.delete('cql_filter');
        queryParams.delete('CQL_FILTER');
        const baseUrl = url.split('?')[0] + '?' + queryParams.toString();
        const body = 'cql_filter=' + encodeURIComponent(cqlFilter);
        const response = await fetch(baseUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body
        });
        if (!response.ok) {
            throw new Error(`Failed to fetch features from ${url}: ${response.statusText}`);
        }
        return response.json();
    }
    // If no cql_filter, fallback to GET request
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Failed to fetch features from ${url}: ${response.statusText}`);
    }
    return response.json();
}

/**
 * Fetch GeoJSON features from a URL.
 * Prepared for issue #57: turn GET into POST for cql_filter support with large geometries.
 */
export async function getFeatureFromURL(url: string): Promise<any> {
    if ( url.startsWith('https://data.geopf.fr/wfs') ) {
        return getFeaturesFromGeoplateformeWFS(url);
    }

    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Failed to fetch features from ${url}: ${response.statusText}`);
    }
    return response.json();
}


/**
 * Create a background layer from a layer name
 * @param name the layer name (ex : gpf:GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2.L93)
 * @returns the background layer
 */
export function getBackgroundLayer(name: string, greyscale: boolean = false) : TileLayer {
    console.log('getBackgroundLayer', name, greyscale);
    if (name.startsWith('gpf:')) {
        // remove the gpf: prefix
        const layerName = name.replace('gpf:', '');
        return new TileLayer({
            className: greyscale ? 'background-greyscale' : 'background-standard',
            source: new ImageTile({
                url: getGeoplateformeUrlTMS(layerName),
            }),
        })
    }

    return new TileLayer({
        className: greyscale ? 'background-greyscale' : 'background-standard',
        source: new OSM()
    });
}

