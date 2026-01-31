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

    const baseHeight = 24;
    const height = isExpanded ? baseHeight + details.length * 11 : baseHeight;
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

    links.enter().append('path')
        .attr('class', 'link')
        .merge(links)
        .transition().duration(400)
        .attr('d', d => {
            const s = d.sections[0];
            const start = s.startPoint;
            const end = s.endPoint;

            if (s.bendPoints && s.bendPoints.length > 0) {
                // Create path through all bend points with horizontal tangents
                const points = [start, ...s.bendPoints, end];
                let path = `M${points[0].x},${points[0].y}`;

                for (let i = 0; i < points.length - 1; i++) {
                    const curr = points[i];
                    const next = points[i + 1];

                    // Use horizontal tangents for tree-like flow
                    const dx = Math.abs(next.x - curr.x);
                    const cp1x = curr.x + dx * 0.4;
                    const cp1y = curr.y;
                    const cp2x = next.x - dx * 0.4;
                    const cp2y = next.y;

                    path += ` C${cp1x},${cp1y} ${cp2x},${cp2y} ${next.x},${next.y}`;
                }
                return path;
            } else {
                // Simple horizontal bezier curve
                const dx = Math.abs(end.x - start.x);
                const cp1x = start.x + dx * 0.4;
                const cp2x = end.x - dx * 0.4;
                return `M${start.x},${start.y} C${cp1x},${start.y} ${cp2x},${end.y} ${end.x},${end.y}`;
            }
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
            .attr('y', (text, i) => 38 + i * 11)
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