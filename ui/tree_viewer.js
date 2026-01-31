// D3 v7 tree viewer with pan/zoom support.
// Expects a JSON file `demo_tree.json` in the same directory.

const margin = { top: 40, right: 40, bottom: 40, left: 40 };
let width = window.innerWidth - margin.left - margin.right;
let height = window.innerHeight - margin.top - margin.bottom;

const dx = 20;
let dy = Math.max(width / 8, 200); // dynamic dy based on viewport

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

// Calculate approximate text width (rough estimate in pixels)
function estimateTextWidth(text, fontSize = 12) {
    const charWidth = fontSize * 0.5; // Rough estimate: char width ~ half font size
    return text.length * charWidth + 16; // Add padding
}

// Calculate node dimensions based on content
function calculateNodeDimensions(d) {
    const details = formatDetails(d);
    const name = d.name || '';
    let maxWidth = estimateTextWidth(name, 13);
    details.forEach(detail => {
        maxWidth = Math.max(maxWidth, estimateTextWidth(detail, 10));
    });
    const height = 24 + details.length * 11;
    return { width: Math.max(80, maxWidth), height, detailCount: details.length };
}

function render(data) {
    const root = d3.hierarchy(data);

    // Pre-calculate all node dimensions
    const nodeDimensions = new Map();
    root.descendants().forEach(node => {
        nodeDimensions.set(node.data.db_id, calculateNodeDimensions(node.data));
    });

    // Calculate max width to determine horizontal spacing
    let maxNodeWidth = 80;
    nodeDimensions.forEach(dims => {
        maxNodeWidth = Math.max(maxNodeWidth, dims.width);
    });

    // Adjust dy to provide enough space for wide nodes (prevent horizontal overlaps)
    dy = Math.max(width / 8, 200, maxNodeWidth + 60);

    const treeLayout = d3.tree().nodeSize([dx, dy]);
    treeLayout(root);

    const nodes = root.descendants();
    const links = root.links();

    // Draw links first (behind nodes)
    g.selectAll('.link').data(links).join('path')
        .attr('class', 'link')
        .attr('d', d3.linkHorizontal().x(d => d.y).y(d => d.x));

    // Draw nodes as expandable rectangles
    const nodeGroups = g.selectAll('.node').data(nodes, d => d.data.db_id).join('g')
        .attr('class', 'node')
        .attr('transform', d => `translate(${d.y},${d.x})`);

    // Add background rectangle with calculated dimensions
    nodeGroups.append('rect')
        .attr('width', d => {
            const dims = nodeDimensions.get(d.data.db_id);
            return dims ? dims.width : 80;
        })
        .attr('height', 24)
        .attr('x', d => {
            const dims = nodeDimensions.get(d.data.db_id);
            return dims ? -dims.width / 2 : -40;
        })
        .attr('y', -12);

    // Add name label (always visible)
    nodeGroups.append('text')
        .attr('class', 'name')
        .attr('text-anchor', 'middle')
        .attr('dy', '0.35em')
        .text(d => d.data.name);

    // Add detail lines (collapsed by default)
    const detailData = (d) => {
        const details = formatDetails(d.data);
        return details.map((text, i) => ({ text, index: i }));
    };

    nodeGroups.selectAll('.detail-text').remove(); // Clear old details

    nodeGroups.selectAll('.detail-text')
        .data(d => detailData(d), d => d.index)
        .join('text')
        .attr('class', 'details')
        .attr('text-anchor', 'middle')
        .attr('font-size', '9px')
        .attr('y', (d, i) => 12 + i * 11)
        .text(d => d.text);

    // Add hover interaction
    nodeGroups.on('mouseenter', function () {
        d3.select(this).classed('expanded', true);
        const node = d3.select(this).datum();
        const dims = nodeDimensions.get(node.data.db_id);
        const details = formatDetails(node.data);
        const newHeight = Math.max(24, 24 + details.length * 11);

        d3.select(this).select('rect')
            .transition().duration(200)
            .attr('height', newHeight)
            .attr('y', -newHeight / 2);
    })
        .on('mouseleave', function () {
            d3.select(this).classed('expanded', false);
            d3.select(this).select('rect')
                .transition().duration(200)
                .attr('height', 24)
                .attr('y', -12);
        });
}

// Handle window resize
window.addEventListener('resize', () => {
    width = window.innerWidth - margin.left - margin.right;
    height = window.innerHeight - margin.top - margin.bottom;
    svg.attr('width', width + margin.left + margin.right)
        .attr('height', height + margin.top + margin.bottom);
});

// Load and render demo JSON
fetch('demo_tree.json')
    .then(r => r.json())
    .then(render)
    .catch(err => {
        d3.select('#chart').append('p')
            .style('color', 'red')
            .style('padding', '20px')
            .text('Failed to load demo_tree.json: ' + err.message);
    });