import OlSimpleMap from './ol-simple-map';
import { getBackgroundLayer } from './helpers';
import 'ol/ol.css';
import './demo-geocontext.css'

// Enregistrer automatiquement le web component
customElements.define('ol-simple-map', OlSimpleMap);

// Exporter pour usage programmatique si nécessaire
if (typeof window !== 'undefined') {
  (window as any).OlSimpleMap = OlSimpleMap;
  (window as any).getBackgroundLayer = getBackgroundLayer;
}

// Message de confirmation dans la console
console.log('🗺️ Composant ol-simple-map enregistré avec succès !');
