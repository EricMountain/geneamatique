// ELKjs tree viewer with D3 rendering and pan/zoom support.
const elk = new ELK();

const margin = { top: 40, right: 40, bottom: 40, left: 40 };
let width = window.innerWidth - margin.left - margin.right;
let height = window.innerHeight - margin.top - margin.bottom;

const svg = d3.select('#chart').append('svg')
    .attr('width', width + margin.left + margin.right)
    .attr('height', height + margin.top + margin.bottom);

const g = svg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`);

// Gender colours (match import_tools/tree_visualizer.py: cyan for men, yellow for women)
// Accent colours for text/stroke; fill are pale tints for node backgrounds.
const GENDER_COLORS = {
    male: { accent: '#00bcd4', fill: '#e0f7fa', text: '#006064' },
    female: { accent: '#f0c330', fill: '#fff8e1', text: '#8a6d00' },
    unknown: { accent: '#999999', fill: '#f5f5f5', text: '#333333' }
};

function genderForData(d) {
    const sosa = d && d.sosa;
    const oldId = d && d.old_id;
    if (typeof sosa === 'number') {
        return (sosa % 2 === 0) ? 'male' : 'female';
    }
    if (typeof oldId === 'number') {
        return (oldId % 2 === 0) ? 'male' : 'female';
    }
    return 'unknown';
}

// Theme detection: check forced data-theme first, fall back to prefers-color-scheme
function isDarkTheme() {
    const forced = document.documentElement.getAttribute('data-theme');
    if (forced === 'dark' || forced === 'light') return forced === 'dark';
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
}

// Return colours, but invert foreground/background in dark mode
function genderColor(d) {
    const base = GENDER_COLORS[genderForData(d)];
    if (isDarkTheme()) {
        return { accent: base.accent, fill: base.text, text: base.fill };
    }
    return base;
}

// Re-render when theme changes: watch attribute changes on root and matchMedia changes
const themeObserver = new MutationObserver(mutations => {
    for (const m of mutations) {
        if (m.type === 'attributes' && m.attributeName === 'data-theme') {
            render();
            return;
        }
    }
});

themeObserver.observe(document.documentElement, { attributes: true });

if (window.matchMedia) {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    if (mq.addEventListener) mq.addEventListener('change', () => render()); else mq.addListener(() => render());
}

// Add zoom behavior
const zoom = d3.zoom()
    .on('zoom', (event) => {
        g.attr('transform', event.transform);
    });

svg.call(zoom);

// Visual feedback for grab/grabbing
svg.on('mousedown', () => svg.classed('grabbing', true));
svg.on('mouseup', () => svg.classed('grabbing', false));
svg.on('mouseleave', () => svg.classed('grabbing', false));

// State to track expanded nodes
const expandedNodes = new Set();
const hoverTimers = new Map(); // db_id -> timeout id for delayed hover expand
let rootData = null;

// Helper to format details for display
function formatDetails(d) {
    // Use same emoji markers as import_tools/tree_visualizer.py for consistency
    const BIRTH_SYMBOL = '🍼';
    const DEATH_SYMBOL = '🪦';
    const MARRIAGE_SYMBOL = '💍';
    const lines = [];

    // Name comment (shown near the name in the CLI tool; show on hover here)
    if (d.name_comment) lines.push(`(${d.name_comment})`);

    // Birth: show marker + date/location/comment on one line; show marker even if date missing
    if (d.date_of_birth || d.birth_location || d.birth_comment) {
        let parts = [];
        if (d.date_of_birth) parts.push(d.date_of_birth);
        if (d.birth_location) parts.push(`à ${d.birth_location}`);
        let s = `${BIRTH_SYMBOL} ${parts.join(' ')}`;
        if (d.birth_comment) s += ` (${d.birth_comment})`;
        lines.push(s);
    }

    // Death: show marker + date/location/comment on one line; show marker even if date missing
    if (d.date_of_death || d.death_location || d.death_comment) {
        let parts = [];
        if (d.date_of_death) parts.push(d.date_of_death);
        if (d.death_location) parts.push(`à ${d.death_location}`);
        let s = `${DEATH_SYMBOL} ${parts.join(' ')}`;
        if (d.death_comment) s += ` (${d.death_comment})`;
        lines.push(s);
    }

    // Marriage: show marker + date/location/comment on one line; show marker even if date missing
    if (d.marriage_date || d.marriage_location || d.marriage_comment) {
        let parts = [];
        if (d.marriage_date) parts.push(d.marriage_date);
        if (d.marriage_location) parts.push(`à ${d.marriage_location}`);
        let s = `${MARRIAGE_SYMBOL} ${parts.join(' ')}`;
        if (d.marriage_comment) s += ` (${d.marriage_comment})`;
        lines.push(s);
    }

    // Database id and SOSA number for reference
    if (d.db_id !== undefined && d.db_id !== null) {
        const sosaPart = (d.sosa !== undefined && d.sosa !== null) ? `SOSA: ${d.sosa}` : 'SOSA: ?';
        lines.push(`${sosaPart}, DBId: ${d.db_id}`);
    }

    return lines;
}

// Calculate approximate text width (use canvas.measureText for accuracy)
const _textMeasurer = (() => {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    return (text, fontSize = 12, fontFamily = 'sans-serif', fontWeight = 'normal') => {
        ctx.font = `${fontWeight} ${fontSize}px ${fontFamily}`;
        return ctx.measureText(text).width;
    };
})();

function estimateTextWidth(text, fontSize = 12) {
    if (!text) return 0;
    // Use the canvas-based measurer for a more accurate width (handles emojis and wide glyphs better)
    const measured = _textMeasurer(text, fontSize);
    // Add horizontal padding so text doesn't sit too close to the rectangle edge
    const horizontalPadding = 28;
    return measured + horizontalPadding;
}

// Calculate node dimensions
function calculateNodeDimensions(d) {
    const isExpanded = expandedNodes.has(d.db_id);
    const details = formatDetails(d);
    const name = d.name || '';
    let maxWidth = estimateTextWidth(name, 13);

    if (isExpanded) {
        details.forEach(detail => {
            maxWidth = Math.max(maxWidth, estimateTextWidth(detail, 10));
        });
    }

    const nameHeight = 24;
    const detailLineHeight = 11;
    const detailsTopPadding = 14; // gap between name and first detail line
    const height = isExpanded ? nameHeight + detailsTopPadding + details.length * detailLineHeight : nameHeight;
    // Increase minimum width to give long names a little more breathing room
    return { width: Math.max(160, maxWidth), height };
}

async function render() {
    if (!rootData) return;

    // Build ELK graph structure
    const elkNodes = [];
    const elkEdges = [];

    function traverse(node) {
        const dims = calculateNodeDimensions(node);
        elkNodes.push({
            id: String(node.db_id),
            width: dims.width,
            height: dims.height,
            data: node
        });

        if (node.children) {
            node.children.forEach(child => {
                elkEdges.push({
                    id: `e${node.db_id}-${child.db_id}`,
                    sources: [String(node.db_id)],
                    targets: [String(child.db_id)]
                });
                traverse(child);
            });
        }
    }

    traverse(rootData);

    const graph = {
        id: "root",
        layoutOptions: {
            'elk.algorithm': 'elk.mrtree',
            'elk.direction': 'RIGHT',
            'elk.spacing.nodeNode': '20'
        },
        children: elkNodes,
        edges: elkEdges
    };

    const layout = await elk.layout(graph);

    // Update Links
    const linkData = layout.edges || [];
    const links = g.selectAll('.link').data(linkData, d => d.id);

    links.exit().remove();

    // Helper: convert Catmull-Rom points to smooth cubic Bezier segments
    // Use D3's monotone-X curve generator to produce smooth, x-monotonic cubic Bézier paths
    const monotoneLine = d3.line()
        .x(p => p.x)
        .y(p => p.y)
        .curve(d3.curveMonotoneX);

    // Create a rounded polyline by replacing sharp corners with small quadratic curves
    function roundedPolyline(points, r = 10) {
        if (!points || points.length === 0) return '';
        if (points.length === 1) return `M${points[0].x},${points[0].y}`;
        if (points.length === 2) {
            // simple cubic bezier between two points
            const p0 = points[0];
            const p1 = points[1];
            const dx = Math.abs(p1.x - p0.x);
            const cp1x = p0.x + dx * 0.4;
            const cp2x = p1.x - dx * 0.4;
            return `M${p0.x},${p0.y} C${cp1x},${p0.y} ${cp2x},${p1.y} ${p1.x},${p1.y}`;
        }

        let path = `M${points[0].x},${points[0].y}`;
        for (let i = 1; i < points.length - 1; i++) {
            const prev = points[i - 1];
            const curr = points[i];
            const next = points[i + 1];

            const v1x = curr.x - prev.x;
            const v1y = curr.y - prev.y;
            const v2x = next.x - curr.x;
            const v2y = next.y - curr.y;

            const len1 = Math.hypot(v1x, v1y) || 1;
            const len2 = Math.hypot(v2x, v2y) || 1;

            const r1 = Math.min(r, len1 / 2);
            const r2 = Math.min(r, len2 / 2);

            // point where we start the corner (on the segment prev->curr)
            const startX = curr.x - (v1x / len1) * r1;
            const startY = curr.y - (v1y / len1) * r1;
            // point where we end the corner (on the segment curr->next)
            const endX = curr.x + (v2x / len2) * r2;
            const endY = curr.y + (v2y / len2) * r2;

            // line to the start of the rounded corner
            path += ` L${startX},${startY}`;
            // quadratic curve around the corner with control point at the corner (curr)
            path += ` Q${curr.x},${curr.y} ${endX},${endY}`;
        }
        // line to the final point
        const last = points[points.length - 1];
        path += ` L${last.x},${last.y}`;
        return path;
    }

    links.enter().append('path')
        .attr('class', 'link')
        .merge(links)
        .transition().duration(400)
        .attr('d', d => {
            // Collect points from all sections (ELK can split edges into multiple sections)
            if (!d.sections || d.sections.length === 0) return '';
            const points = [];
            d.sections.forEach((sec, idx) => {
                if (idx === 0) points.push(sec.startPoint);
                if (sec.bendPoints && sec.bendPoints.length) sec.bendPoints.forEach(bp => points.push(bp));
                points.push(sec.endPoint);
            });

            // Remove consecutive duplicate points
            const uniq = points.filter((p, i) => i === 0 || p.x !== points[i - 1].x || p.y !== points[i - 1].y);
            if (uniq.length < 2) return '';

            // If only start and end points exist, generate an explicit cubic bezier so we get a curve
            if (uniq.length === 2) {
                const p0 = uniq[0];
                const p1 = uniq[1];
                const dx = Math.abs(p1.x - p0.x);
                const cp1x = p0.x + dx * 0.4;
                const cp2x = p1.x - dx * 0.4;
                return `M${p0.x},${p0.y} C${cp1x},${p0.y} ${cp2x},${p1.y} ${p1.x},${p1.y}`;
            }

            // For routed edges with multiple points, use rounded polyline smoothing
            return roundedPolyline(uniq);
        });

    // Update Nodes
    const nodes = g.selectAll('.node').data(layout.children, d => d.id);

    const nodeEnter = nodes.enter().append('g')
        .attr('class', 'node')
        .attr('transform', d => `translate(${d.x},${d.y})`)
        .style('cursor', 'pointer');

    nodeEnter.append('rect')
        .attr('rx', 4)
        .attr('ry', 4)
        .attr('width', d => d.width)
        .attr('height', d => d.height)
        .style('fill', d => genderColor(d.data).fill)
        .style('stroke', d => genderColor(d.data).accent)
        .style('stroke-width', '1.5px');

    nodeEnter.append('text')
        .attr('class', 'name')
        .attr('text-anchor', 'middle')
        .attr('dy', '16px');

    const nodeUpdate = nodeEnter.merge(nodes);

    nodeUpdate.classed('expanded', d => expandedNodes.has(d.data.db_id));

    nodeUpdate.transition().duration(400)
        .attr('transform', d => `translate(${d.x},${d.y})`);

    nodeUpdate.select('rect')
        .transition().duration(400)
        .attr('width', d => d.width)
        .attr('height', d => d.height)
        .style('fill', d => genderColor(d.data).fill)
        .style('stroke', d => genderColor(d.data).accent)
        .style('stroke-width', '1.5px');

    nodeUpdate.select('.name')
        .transition().duration(400)
        .attr('x', d => d.width / 2)
        .text(d => d.data.name)
        .style('fill', d => genderColor(d.data).text);

    // Details
    nodeUpdate.each(function (d) {
        const nodeGroup = d3.select(this);
        const isExpanded = expandedNodes.has(d.data.db_id);
        const details = isExpanded ? formatDetails(d.data) : [];

        const detailTexts = nodeGroup.selectAll('.details').data(details, (text, i) => i);

        detailTexts.exit().remove();

        detailTexts.enter().append('text')
            .attr('class', 'details')
            .attr('text-anchor', 'middle')
            .attr('font-size', '10px')
            .merge(detailTexts)
            .attr('x', d.width / 2)
            .attr('y', (text, i) => {
                const nameHeight = 24;
                const detailLineHeight = 11;
                const detailsTopPadding = 14;
                return nameHeight + detailsTopPadding + i * detailLineHeight;
            })
            .text(text => text);
    });

    // Interaction
    // Expand on hover after a short delay; do NOT collapse on mouseleave so transient layout shifts won't close the bubble.
    // Collapse/toggle when the user explicitly clicks the node.
    nodeUpdate.on('mouseenter', function (event, d) {
        const id = d.data.db_id;
        // If already expanded, nothing to do
        if (expandedNodes.has(id)) return;
        // Clear any previous timer for this node
        if (hoverTimers.has(id)) {
            clearTimeout(hoverTimers.get(id));
            hoverTimers.delete(id);
        }
        // Schedule delayed expand (150ms) to ignore brief skims
        const t = setTimeout(() => {
            expandedNodes.add(id);
            hoverTimers.delete(id);
            render(); // Re-layout
        }, 150);
        hoverTimers.set(id, t);
    })
        .on('mouseleave', function (event, d) {
            // Cancel pending hover expand if the user moved away quickly
            const id = d.data.db_id;
            if (hoverTimers.has(id)) {
                clearTimeout(hoverTimers.get(id));
                hoverTimers.delete(id);
            }
        })
        .on('click', function (event, d) {
            const id = d.data.db_id;
            // Cancel any pending hover expand to avoid races
            if (hoverTimers.has(id)) {
                clearTimeout(hoverTimers.get(id));
                hoverTimers.delete(id);
            }
            // Toggle expanded state on click
            if (expandedNodes.has(id)) {
                expandedNodes.delete(id);
            } else {
                expandedNodes.add(id);
            }
            render(); // Re-layout
        });

    nodes.exit().remove();
}

// Handle window resize
window.addEventListener('resize', () => {
    width = window.innerWidth - margin.left - margin.right;
    height = window.innerHeight - margin.top - margin.bottom;
    svg.attr('width', width + margin.left + margin.right)
        .attr('height', height + margin.top + margin.bottom);
});

// Provide API for external code to set the tree root and to show errors
window.setTreeRoot = function (data) {
    rootData = data;
    render();
};

window.showTreeError = function (msg) {
    d3.select('#chart').selectAll('*').remove();
    d3.select('#chart').append('p')
        .style('color', 'red')
        .style('padding', '20px')
        .text(msg);
};

// Note: The PWA should call `fetch('/api/tree?...')` to get a generated tree JSON
// and then call `setTreeRoot(data)` to render it.