# demo-geocontext - Front

## Principe

The idea is to ease the integration of a map in Gradio as follow :

```html
<ol-simple-map 
    lon="2.294481"
    lat="48.858370" 
    zoom="7"
    background="gpf:GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2"
    data-url="https://france-geojson.gregoiredavid.fr/repo/departements.geojson"
>
</ol-simple-map>
```

## Usage

Note that `front/dist` is commited. The following command are useful to build or improve the front :

```bash
# install dependencies
npm install
# start demo (DEV mode)
npm run start
# rebuild front/dist
npm run build
```

## Alternatives

See also :

* [MapML](https://maps4html.org/web-map-doc/fr/docs/)
* [@openlayers-elements/maps](https://www.webcomponents.org/element/@openlayers-elements/maps)
