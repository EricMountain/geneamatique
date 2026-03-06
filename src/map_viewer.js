// Map viewer for genealogy events using Leaflet and OpenStreetMap
// Displays birth, death, and marriage events as separate markers with clustering

let map = null;
let markersLayer = null;

/**
 * Initialize the Leaflet map
 * @param {string} containerId - ID of the map container div
 */
export function initMap(containerId = 'map') {
    if (map) return map; // Already initialized

    map = L.map(containerId, {
        center: [48.8566, 2.3522], // Default to Paris
        zoom: 6,
        zoomControl: true,
        scrollWheelZoom: true
    });

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
        minZoom: 2
    }).addTo(map);

    return map;
}

/**
 * Create a custom icon for event markers
 * @param {string} type - Event type: 'birth', 'death', or 'marriage'
 * @returns {L.DivIcon}
 */
function createEventIcon(type) {
    const iconConfig = {
        birth: { symbol: '🔵', color: '#4A90E2', text: 'Birth' },
        death: { symbol: '⚰️', color: '#666', text: 'Death' },
        marriage: { symbol: '⭕', color: '#E24A90', text: 'Marriage' }
    };

    const config = iconConfig[type] || iconConfig.birth;

    return L.divIcon({
        html: `<div style="font-size: 20px; text-align: center; line-height: 1;">${config.symbol}</div>`,
        className: `event-marker event-marker-${type}`,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
        popupAnchor: [0, -12]
    });
}

/**
 * Flatten tree structure into array of individuals
 * @param {object} tree - Tree root node
 * @returns {array} - Array of all individuals in tree
 */
function flattenTree(tree) {
    if (!tree) return [];
    
    const individuals = [tree];
    const queue = [tree];
    const seen = new Set([tree.db_id]);

    while (queue.length > 0) {
        const node = queue.shift();
        if (node.children && Array.isArray(node.children)) {
            for (const child of node.children) {
                if (child && child.db_id && !seen.has(child.db_id)) {
                    seen.add(child.db_id);
                    individuals.push(child);
                    queue.push(child);
                }
            }
        }
    }

    return individuals;
}

/**
 * Extract events with valid coordinates from individuals
 * @param {array} individuals - Array of individual objects
 * @returns {array} - Array of event objects with {type, lat, lon, individual, location, date}
 */
function extractEvents(individuals) {
    const events = [];

    for (const individual of individuals) {
        // Birth event
        if (individual.birth_lat != null && individual.birth_lon != null) {
            events.push({
                type: 'birth',
                lat: individual.birth_lat,
                lon: individual.birth_lon,
                individual: individual,
                location: individual.birth_location,
                date: individual.date_of_birth
            });
        }

        // Death event
        if (individual.death_lat != null && individual.death_lon != null) {
            events.push({
                type: 'death',
                lat: individual.death_lat,
                lon: individual.death_lon,
                individual: individual,
                location: individual.death_location,
                date: individual.date_of_death
            });
        }

        // Marriage event
        if (individual.marriage_lat != null && individual.marriage_lon != null) {
            events.push({
                type: 'marriage',
                lat: individual.marriage_lat,
                lon: individual.marriage_lon,
                individual: individual,
                location: individual.marriage_location,
                date: individual.marriage_date
            });
        }
    }

    return events;
}

/**
 * Calculate bounding box from events with padding
 * @param {array} events - Array of event objects
 * @returns {object} - {minLat, maxLat, minLon, maxLon} or null if no events
 */
function calculateBounds(events) {
    if (events.length === 0) return null;

    let minLat = events[0].lat;
    let maxLat = events[0].lat;
    let minLon = events[0].lon;
    let maxLon = events[0].lon;

    for (const event of events) {
        minLat = Math.min(minLat, event.lat);
        maxLat = Math.max(maxLat, event.lat);
        minLon = Math.min(minLon, event.lon);
        maxLon = Math.max(maxLon, event.lon);
    }

    // Add 10% padding
    const latPadding = (maxLat - minLat) * 0.1 || 0.1;
    const lonPadding = (maxLon - minLon) * 0.1 || 0.1;

    return {
        minLat: minLat - latPadding,
        maxLat: maxLat + latPadding,
        minLon: minLon - lonPadding,
        maxLon: maxLon + lonPadding
    };
}

/**
 * Create popup content for an event
 * @param {object} event - Event object
 * @returns {string} - HTML string for popup
 */
function createPopupContent(event) {
    const ind = event.individual;
    const typeEmoji = { birth: '🍼', death: '🪦', marriage: '💍' };
    const typeLabel = { birth: 'Born', death: 'Died', marriage: 'Married' };

    let content = `<strong>${ind.name || 'Unknown'}</strong>`;
    
    if (ind.name_comment) {
        content += `<div style="font-style:italic;font-size:12px;color:var(--muted);">${ind.name_comment}</div>`;
    }

    content += `<div style="margin-top:8px;"><strong>${typeEmoji[event.type]} ${typeLabel[event.type]}</strong></div>`;
    
    if (event.date) {
        content += `<div>📅 ${event.date}</div>`;
    }
    
    if (event.location) {
        content += `<div>📍 ${event.location}</div>`;
    }

    // Add other life events for context
    if (event.type !== 'birth' && ind.date_of_birth) {
        content += `<div style="margin-top:6px;color:var(--muted);font-size:12px;">🍼 Born ${ind.date_of_birth}${ind.birth_location ? ' in ' + ind.birth_location : ''}</div>`;
    }
    if (event.type !== 'death' && ind.date_of_death) {
        content += `<div style="color:var(--muted);font-size:12px;">🪦 Died ${ind.date_of_death}${ind.death_location ? ' in ' + ind.death_location : ''}</div>`;
    }

    return content;
}

/**
 * Custom icon create function for clusters showing event breakdown
 * @param {object} cluster - MarkerCluster cluster object
 * @returns {L.DivIcon}
 */
function createClusterIcon(cluster) {
    const markers = cluster.getAllChildMarkers();
    
    // Count events by type
    const counts = { birth: 0, death: 0, marriage: 0 };
    for (const marker of markers) {
        const eventType = marker.options.eventType;
        if (eventType && counts.hasOwnProperty(eventType)) {
            counts[eventType]++;
        }
    }

    const total = markers.length;
    
    // Build breakdown text
    const parts = [];
    if (counts.birth > 0) parts.push(`${counts.birth} birth${counts.birth > 1 ? 's' : ''}`);
    if (counts.death > 0) parts.push(`${counts.death} death${counts.death > 1 ? 's' : ''}`);
    if (counts.marriage > 0) parts.push(`${counts.marriage} marriage${counts.marriage > 1 ? 's' : ''}`);
    
    const title = parts.join(', ') || `${total} events`;

    // Determine dominant color based on event mix
    let dominantColor = '#4A90E2'; // Default blue (birth)
    if (counts.death > counts.birth && counts.death > counts.marriage) {
        dominantColor = '#666'; // Gray (death)
    } else if (counts.marriage > counts.birth && counts.marriage > counts.death) {
        dominantColor = '#E24A90'; // Pink (marriage)
    }

    return L.divIcon({
        html: `<div style="
            background: ${dominantColor};
            color: white;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 14px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            border: 3px solid white;
        " title="${title}">${total}</div>`,
        className: 'custom-cluster-icon',
        iconSize: [40, 40]
    });
}

/**
 * Display events on the map with clustering
 * @param {object} treeData - Tree data from API
 */
export function showEventsOnMap(treeData) {
    if (!map) {
        console.error('Map not initialized. Call initMap() first.');
        return;
    }

    // Clear existing markers
    if (markersLayer) {
        map.removeLayer(markersLayer);
    }

    // Flatten tree and extract events
    const individuals = flattenTree(treeData);
    const events = extractEvents(individuals);

    if (events.length === 0) {
        console.warn('No events with valid coordinates found in tree data');
        // Show message on map
        L.popup()
            .setLatLng(map.getCenter())
            .setContent('<strong>No location data available</strong><br>None of the individuals in this tree have geocoded locations.')
            .openOn(map);
        return;
    }

    // Create marker cluster group with custom icon function
    markersLayer = L.markerClusterGroup({
        maxClusterRadius: 60,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true,
        iconCreateFunction: createClusterIcon
    });

    // Add markers for each event
    for (const event of events) {
        const marker = L.marker([event.lat, event.lon], {
            icon: createEventIcon(event.type),
            eventType: event.type, // Store for cluster counting
            title: `${event.individual.name} - ${event.type}`
        });

        marker.bindPopup(createPopupContent(event), {
            maxWidth: 300,
            className: 'event-popup'
        });

        markersLayer.addLayer(marker);
    }

    map.addLayer(markersLayer);

    // Fit map to bounds
    const bounds = calculateBounds(events);
    if (bounds) {
        map.fitBounds([
            [bounds.minLat, bounds.minLon],
            [bounds.maxLat, bounds.maxLon]
        ], {
            padding: [50, 50],
            maxZoom: 13 // Don't zoom in too close for single locations
        });
    }

    console.log(`Displayed ${events.length} events from ${individuals.length} individuals on map`);
}

/**
 * Refresh map size (call after showing/hiding container)
 */
export function refreshMap() {
    if (map) {
        map.invalidateSize();
    }
}

/**
 * Destroy map instance
 */
export function destroyMap() {
    if (map) {
        map.remove();
        map = null;
        markersLayer = null;
    }
}
