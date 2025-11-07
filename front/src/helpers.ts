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

