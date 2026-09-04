const map = L.map('map');

const baseLayers = {
    'OpenStreetMap': L.tileLayer(
        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 19
        }
    ),
    'Topographic': L.tileLayer(
        'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
        {
            attribution: '&copy; OpenStreetMap contributors, SRTM | &copy; OpenTopoMap (CC-BY-SA)',
            maxZoom: 17
        }
    ),
    'Satellite': L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        {
            attribution: '&copy; Esri, Maxar, Earthstar Geographics',
            maxZoom: 19
        }
    )
};

// OpenStreetMap is the default; Topographic carries the contour lines.
baseLayers['OpenStreetMap'].addTo(map);
L.control.layers(baseLayers, null, { collapsed: false }).addTo(map);

// Fallback view, used until the photos load and whenever none have coordinates.
map.setView([68.349, 18.831], 13);

// Set once the photos load, so the reset button can return to that view.
let homeBounds = null;

// Layers beyond the photo markers that should also fit inside the home view.
// GPX tracks will be pushed here once tracks/ is implemented.
const extraLayers = [];

const HOME_FIT = { padding: [40, 40], maxZoom: 15 };

const ResetControl = L.Control.extend({
    options: { position: 'topleft' },

    onAdd: function () {
        const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
        const link = L.DomUtil.create('a', 'reset-zoom', container);
        link.href = '#';
        link.title = 'Reset zoom to all photos';
        link.innerHTML = '&#8634;';

        L.DomEvent
            .on(link, 'click', L.DomEvent.stop)
            .on(link, 'click', () => {
                if (homeBounds) {
                    map.fitBounds(homeBounds, HOME_FIT);
                }
            });

        L.DomEvent.disableClickPropagation(container);
        return container;
    }
});

map.addControl(new ResetControl());

const COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];

// Nearest of the 8 compass points; returns null when the bearing is unknown.
function compassPoint(bearing) {
    if (bearing === null || bearing === undefined) {
        return null;
    }
    const index = Math.round(((bearing % 360) + 360) % 360 / 45) % 8;
    return COMPASS[index];
}

// Rotated by the exact bearing, not the snapped one: the compass point is only
// for the popup wording, and snapping the arrow would throw away real precision
// (averaging ~11 degrees of error, up to 22).
function arrowIcon(bearing) {
    // Arrow drawn pointing north, then rotated to the recorded heading.
    const svg = `
        <svg viewBox="0 0 32 32" width="32" height="32"
             style="transform: rotate(${bearing}deg)">
            <circle cx="16" cy="16" r="14" fill="#fff" stroke="#c0392b" stroke-width="2"/>
            <path d="M16 5 L22 21 L16 17.5 L10 21 Z" fill="#c0392b"/>
        </svg>`;
    return L.divIcon({
        html: svg,
        className: 'photo-arrow',
        iconSize: [32, 32],
        iconAnchor: [16, 16],
        popupAnchor: [0, -16]
    });
}

// Photos with no bearing keep Leaflet's default pin.
function iconFor(bearing) {
    return bearing === null || bearing === undefined
        ? new L.Icon.Default()
        : arrowIcon(bearing);
}

function popupHtml(photo, point) {
    const when = new Date(photo.timestamp).toLocaleString();
    const parts = [
        `<img src="photos/${photo.file}" alt="" width="240">`,
        `<div>${when}</div>`
    ];
    if (point !== null) {
        parts.push(`<div>Facing ${point} (${Math.round(photo.bearing)}&deg;)</div>`);
    }
    if (photo.alt !== null) {
        parts.push(`<div>${Math.round(photo.alt)} m</div>`);
    }
    return parts.join('');
}

fetch('data/photos.json')
    .then(response => {
        if (!response.ok) {
            throw new Error(`photos.json: ${response.status}`);
        }
        return response.json();
    })
    .then(photos => {
        const located = photos.filter(p => p.lat !== null && p.lon !== null);
        if (located.length === 0) {
            return;
        }

        const markers = located.map(photo => {
            const point = compassPoint(photo.bearing);
            return L.marker([photo.lat, photo.lon], {
                icon: iconFor(photo.bearing),
                title: point === null ? photo.file : `Facing ${point}`
            })
                .addTo(map)
                .bindPopup(popupHtml(photo, point), { maxWidth: 260 });
        });

        // Union of every layer's box, so a GPX track wider than the photo
        // spread (or the reverse) still decides the zoom. Leaflet's extend()
        // does the union; a per-dimension max would be wrong, since one box
        // can be wider but shorter than the other.
        homeBounds = L.featureGroup(markers.concat(extraLayers)).getBounds();
        map.fitBounds(homeBounds, HOME_FIT);
    })
    .catch(error => console.error('Could not load photo markers:', error));
