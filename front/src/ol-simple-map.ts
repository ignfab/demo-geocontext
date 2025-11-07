import { Map, View } from 'ol';
import { fromLonLat } from 'ol/proj';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import GeoJSON from 'ol/format/GeoJSON';

import { getBackgroundLayer } from './helpers';

class OlSimpleMap extends HTMLElement {
  private map: Map | null = null;
  private mapContainer: HTMLDivElement | null = null;
  private vectorLayer: VectorLayer<VectorSource> | null = null;

  constructor() {
    super();
    // Pas de Shadow DOM pour permettre aux styles CSS globaux de fonctionner
  }

  static get observedAttributes() {
    return [
      'lon', 'lat', 'zoom', 'background', 'background-greyscale', 'data-url', 'fit-bounds',
      'width', 'height', 'min-width', 'min-height', 'max-width', 'max-height'
    ];
  }

  connectedCallback() {
    this.initializeMap();
  }

  disconnectedCallback() {
    if (this.map) {
      this.map.setTarget(undefined);
      this.map = null;
    }
  }

  attributeChangedCallback(name: string, oldValue: string, newValue: string) {
    if (oldValue !== newValue) {
      if (['lon', 'lat', 'zoom', 'background', 'background-greyscale'].includes(name) && this.map) {
        this.updateMapView();
      } else if (['data-url', 'fit-bounds'].includes(name) && this.map) {
        this.loadVectorLayer();
      } else if (['width', 'height', 'min-width', 'min-height', 'max-width', 'max-height'].includes(name)) {
        this.updateStyles();
      }
    }
  }

  private initializeMap() {
    // Créer le conteneur de la carte
    this.mapContainer = document.createElement('div');
    this.mapContainer.style.width = '100%';
    this.mapContainer.style.height = '100%';

    // Ajouter le conteneur au composant
    this.appendChild(this.mapContainer);

    // Appliquer les styles configurables
    this.updateStyles();

    // Initialiser la carte OpenLayers
    this.createMap();
  }

  private createMap() {
    if (!this.mapContainer) return;

    const lon = parseFloat(this.getAttribute('lon') || '0');
    const lat = parseFloat(this.getAttribute('lat') || '0');
    const zoom = parseInt(this.getAttribute('zoom') || '2');

    const backgroundLayerName = this.getAttribute('background') || 'osm';
    const greyscale = this.getAttribute('background-greyscale') === 'true';
    const backgroundLayer = getBackgroundLayer(backgroundLayerName, greyscale);

    const view = new View({
      center: fromLonLat([lon, lat]),
      zoom: zoom
    });

    this.map = new Map({
      target: this.mapContainer,
      layers: [backgroundLayer],
      view: view
    });

    // Charger la couche vectorielle si data-url est défini
    this.loadVectorLayer();
  }

  private updateMapView() {
    if (!this.map) return;

    const lon = parseFloat(this.getAttribute('lon') || '0');
    const lat = parseFloat(this.getAttribute('lat') || '0');
    const zoom = parseInt(this.getAttribute('zoom') || '2');

    const view = this.map.getView();
    view.setCenter(fromLonLat([lon, lat]));
    view.setZoom(zoom);

    // Mettre à jour la couche de fond si nécessaire
    const backgroundLayerName = this.getAttribute('background') || 'osm';
    const greyscale = this.getAttribute('background-greyscale') === 'true';
    const backgroundLayer = getBackgroundLayer(backgroundLayerName, greyscale);
    
    // Remplacer la première couche (fond de carte)
    const layers = this.map.getLayers();
    if (layers.getLength() > 0) {
      layers.setAt(0, backgroundLayer);
    }
  }

  private updateStyles() {
    // Styles par défaut
    this.style.display = 'block';
    
    // Appliquer les dimensions configurables
    const width = this.getAttribute('width') || '100%';
    const height = this.getAttribute('height') || '400px';
    const minWidth = this.getAttribute('min-width');
    const minHeight = this.getAttribute('min-height');
    const maxWidth = this.getAttribute('max-width');
    const maxHeight = this.getAttribute('max-height');

    this.style.width = width;
    this.style.height = height;

    if (minWidth) this.style.minWidth = minWidth;
    if (minHeight) this.style.minHeight = minHeight;
    if (maxWidth) this.style.maxWidth = maxWidth;
    if (maxHeight) this.style.maxHeight = maxHeight;

    // Forcer la mise à jour de la carte si elle existe
    if (this.map) {
      setTimeout(() => {
        this.map?.updateSize();
      }, 0);
    }
  }

  private loadVectorLayer() {
    const dataUrl = this.getAttribute('data-url');
    const fitBounds = this.hasAttribute('fit-bounds') && this.getAttribute('fit-bounds') !== 'false';
    
    if (!dataUrl || !this.map) return;

    // Supprimer l'ancienne couche vectorielle si elle existe
    if (this.vectorLayer) {
      this.map.removeLayer(this.vectorLayer);
      this.vectorLayer = null;
    }

    // Créer une nouvelle source vectorielle
    const vectorSource = new VectorSource({
      url: dataUrl,
      format: new GeoJSON()
    });

    // Créer une nouvelle couche vectorielle
    this.vectorLayer = new VectorLayer({
      source: vectorSource
    });

    // Si fit-bounds est activé, ajuster la vue quand les données sont chargées
    if (fitBounds) {
      vectorSource.once('change', () => {
        if (vectorSource.getState() === 'ready') {
          const extent = vectorSource.getExtent();
          if (extent && this.map) {
            this.map.getView().fit(extent, {
              padding: [20, 20, 20, 20],
              maxZoom: 16
            });
          }
        }
      });
    }

    // Ajouter la couche à la carte
    this.map.addLayer(this.vectorLayer);
  }

  // Méthodes publiques pour contrôler la carte depuis l'extérieur
  public getMap(): Map | null {
    return this.map;
  }

  public setCenter(lon: number, lat: number) {
    if (this.map) {
      this.map.getView().setCenter(fromLonLat([lon, lat]));
    }
  }

  public setZoom(zoom: number) {
    if (this.map) {
      this.map.getView().setZoom(zoom);
    }
  }

  public setSize(width: string, height: string) {
    this.setAttribute('width', width);
    this.setAttribute('height', height);
  }

  public setMinSize(minWidth?: string, minHeight?: string) {
    if (minWidth) this.setAttribute('min-width', minWidth);
    if (minHeight) this.setAttribute('min-height', minHeight);
  }

  public setMaxSize(maxWidth?: string, maxHeight?: string) {
    if (maxWidth) this.setAttribute('max-width', maxWidth);
    if (maxHeight) this.setAttribute('max-height', maxHeight);
  }
}

export default OlSimpleMap;
