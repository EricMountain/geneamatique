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
        birth: { symbol: '🍼', color: '#4A90E2', bg: 'rgba(113, 166, 226, 0.9)', text: 'Birth' },
        death: { symbol: '🪦', color: '#a8a8a8', bg: 'rgba(188, 188, 188, 0.9)', text: 'Death' },
        marriage: { symbol: '💍', color: '#b74ae2', bg: 'rgba(216, 194, 244, 0.9)', text: 'Marriage' }
    };

    const config = iconConfig[type] || iconConfig.birth;

    return L.divIcon({
        html: `<div style="
            width: 30px;
            height: 30px;
            border-radius: 50%;
            background: ${config.bg};
            border: 2px solid ${config.color};
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            line-height: 1;
        " title="${config.text}">${config.symbol}</div>`,
        className: `event-marker event-marker-${type}`,
        iconSize: [30, 30],
        iconAnchor: [15, 15],
        popupAnchor: [0, -15]
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
 * Infer likely female from genealogy parity convention
 * (odd IDs/SOSA are typically female, even are typically male).
 * @param {object} individual
 * @returns {boolean}
 */
function isLikelyFemale(individual) {
    const paritySource = (typeof individual?.sosa === 'number')
        ? individual.sosa
        : ((typeof individual?.db_id === 'number') ? individual.db_id : null);
    return paritySource != null && (paritySource % 2 === 1);
}

/**
 * Sort union participants with women first, then by name for stability.
 * @param {array} individuals
 * @returns {array}
 */
function sortUnionParticipants(individuals) {
    return [...individuals].sort((a, b) => {
        const aFemale = isLikelyFemale(a);
        const bFemale = isLikelyFemale(b);
        if (aFemale !== bFemale) return aFemale ? -1 : 1;

        const aName = (a?.name || '').toLowerCase();
        const bName = (b?.name || '').toLowerCase();
        return aName.localeCompare(bName);
    });
}

/**
 * Extract events with valid coordinates from individuals
 * @param {array} individuals - Array of individual objects
 * @returns {array} - Array of event objects with {type, lat, lon, individual, location, date}
 */
function extractEvents(individuals, tree = null) {
    const events = [];
    const marriageGroups = new Map();
    const pairedParticipantIds = new Set();

    // Prefer deriving union events from co-parents in the tree so both individuals appear together.
    if (tree) {
        const queue = [tree];
        const seen = new Set();

        while (queue.length > 0) {
            const node = queue.shift();
            if (!node || seen.has(node.db_id)) continue;
            seen.add(node.db_id);

            if (Array.isArray(node.children) && node.children.length > 0) {
                for (const child of node.children) queue.push(child);

                const sortedParents = sortUnionParticipants(node.children);
                const woman = sortedParents.find(isLikelyFemale) || sortedParents[0] || null;
                const man = sortedParents.find((p) => !isLikelyFemale(p)) || sortedParents[1] || null;

                if (woman && man) {
                    const hasMarriageData =
                        (woman.marriage_lat != null && woman.marriage_lon != null) ||
                        (man.marriage_lat != null && man.marriage_lon != null);

                    if (hasMarriageData) {
                        const primary = (woman.marriage_lat != null && woman.marriage_lon != null) ? woman : man;
                        const secondary = primary === woman ? man : woman;

                        const unionKey = [
                            Math.min(woman.db_id, man.db_id),
                            Math.max(woman.db_id, man.db_id),
                            primary.marriage_date || secondary.marriage_date || '',
                            primary.marriage_location || secondary.marriage_location || ''
                        ].join('|');

                        if (!marriageGroups.has(unionKey)) {
                            marriageGroups.set(unionKey, {
                                type: 'marriage',
                                lat: primary.marriage_lat,
                                lon: primary.marriage_lon,
                                location: primary.marriage_location || secondary.marriage_location || null,
                                date: primary.marriage_date || secondary.marriage_date || null,
                                participants: sortUnionParticipants([woman, man])
                            });
                        }

                        pairedParticipantIds.add(woman.db_id);
                        pairedParticipantIds.add(man.db_id);
                    }
                }
            }
        }
    }

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
            // If this individual already participates in a paired union event, skip single-person duplicate.
            if (pairedParticipantIds.has(individual.db_id)) {
                continue;
            }

            const marriageKey = [
                Math.round(individual.marriage_lat * 10000) / 10000,
                Math.round(individual.marriage_lon * 10000) / 10000,
                individual.marriage_date || '',
                individual.marriage_location || ''
            ].join('|');

            if (!marriageGroups.has(marriageKey)) {
                marriageGroups.set(marriageKey, {
                    type: 'marriage',
                    lat: individual.marriage_lat,
                    lon: individual.marriage_lon,
                    location: individual.marriage_location,
                    date: individual.marriage_date,
                    participants: []
                });
            }

            marriageGroups.get(marriageKey).participants.push(individual);
        }
    }

    for (const group of marriageGroups.values()) {
        group.participants = sortUnionParticipants(group.participants);
        group.individual = group.participants[0] || null;
        events.push(group);
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

    if (event.type === 'marriage') {
        const participants = Array.isArray(event.participants) ? event.participants : (ind ? [ind] : []);
        const participantHtml = participants.length > 0
            ? participants.map((p) => {
                const comment = p.name_comment
                    ? `<div style="font-style:italic;font-size:12px;color:var(--muted);">(${p.name_comment})</div>`
                    : '';
                return `<div style="margin-top:6px;"><strong>${p.name || 'Unknown'}</strong>${comment}</div>`;
            }).join('')
            : '<div style="margin-top:6px;color:var(--muted);">Unknown individuals</div>';

        let content = `<div><strong>${typeEmoji[event.type]} Union</strong></div>`;
        content += participantHtml;

        if (event.date) {
            content += `<div style="margin-top:8px;">📅 ${event.date}</div>`;
        }

        if (event.location) {
            content += `<div>📍 ${event.location}</div>`;
        }

        return content;
    }

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
 * Display events on the map with optional clustering
 * @param {object} treeData - Tree data from API
 * @param {object} [options] - Display options
 * @param {boolean} [options.cluster=true] - Whether to group nearby markers into clusters
 * @param {boolean} [options.preserveView=false] - Whether to keep the current map view instead of fitting bounds
 */
export function showEventsOnMap(treeData, options = {}) {
    const { cluster = true, preserveView = false } = options;

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
    const events = extractEvents(individuals, treeData);

    if (events.length === 0) {
        console.warn('No events with valid coordinates found in tree data');
        // Show message on map
        L.popup()
            .setLatLng(map.getCenter())
            .setContent('<strong>No location data available</strong><br>None of the individuals in this tree have geocoded locations.')
            .openOn(map);
        return;
    }

    // Create layer: clustered or plain
    markersLayer = cluster
        ? L.markerClusterGroup({
            maxClusterRadius: 60,
            spiderfyOnMaxZoom: true,
            showCoverageOnHover: false,
            zoomToBoundsOnClick: true,
            iconCreateFunction: createClusterIcon
        })
        : L.layerGroup();

    // Add markers for each event
    for (const event of events) {
        const markerTitle = event.type === 'marriage'
            ? `${(event.participants || []).map(p => p.name).filter(Boolean).join(' + ')} - ${event.type}`
            : `${event.individual.name} - ${event.type}`;

        const marker = L.marker([event.lat, event.lon], {
            icon: createEventIcon(event.type),
            eventType: event.type, // Store for cluster counting
            title: markerTitle
        });

        marker.bindPopup(createPopupContent(event), {
            maxWidth: 300,
            className: 'event-popup'
        });

        markersLayer.addLayer(marker);
    }

    map.addLayer(markersLayer);

    // Fit map to bounds only if not preserving the current view
    if (!preserveView) {
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
