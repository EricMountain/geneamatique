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
let rootData = null;

// Helper to format details for display
function formatDetails(d) {
    const lines = [];
    if (d.date_of_birth) lines.push(`b: ${d.date_of_birth}`);
    if (d.date_of_death) lines.push(`d: ${d.date_of_death}`);
    if (d.marriage_date) lines.push(`m: ${d.marriage_date}`);
    if (d.birth_comment) lines.push(`(${d.birth_comment})`);
    if (d.death_comment) lines.push(`(${d.death_comment})`);
    if (d.marriage_comment) lines.push(`(${d.marriage_comment})`);
    return lines;
}

// Calculate approximate text width
function estimateTextWidth(text, fontSize = 12) {
    const charWidth = fontSize * 0.55;
    return text.length * charWidth + 20;
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
    return { width: Math.max(100, maxWidth), height };
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
            'elk.algorithm': 'layered',
            'elk.direction': 'RIGHT',
            'elk.layered.spacing.nodeNodeLayered': '40',
            'elk.spacing.nodeNode': '20',
            'elk.layered.nodePlacement.strategy': 'NETWORK_SIMPLEX'
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
        .attr('transform', d => `translate(${d.x},${d.y})`);

    nodeEnter.append('rect')
        .attr('rx', 4)
        .attr('ry', 4);

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
        .attr('height', d => d.height);

    nodeUpdate.select('.name')
        .transition().duration(400)
        .attr('x', d => d.width / 2)
        .text(d => d.data.name);

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
    nodeUpdate.on('mouseenter', function (event, d) {
        if (!expandedNodes.has(d.data.db_id)) {
            expandedNodes.add(d.data.db_id);
            render(); // Re-layout
        }
    })
        .on('mouseleave', function (event, d) {
            if (expandedNodes.has(d.data.db_id)) {
                expandedNodes.delete(d.data.db_id);
                render(); // Re-layout
            }
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

// Load and render
fetch('demo_tree.json')
    .then(r => r.json())
    .then(data => {
        rootData = data;
        render();
    })
    .catch(err => {
        d3.select('#chart').append('p')
            .style('color', 'red')
            .style('padding', '20px')
            .text('Failed to load demo_tree.json: ' + err.message);
    });