// D3 v7 tree viewer with pan/zoom support.
// Expects a JSON file `demo_tree.json` in the same directory.

const margin = { top: 40, right: 40, bottom: 40, left: 40 };
let width = window.innerWidth - margin.left - margin.right;
let height = window.innerHeight - margin.top - margin.bottom;

const dx = 20;
const dy = Math.max(width / 8, 200); // dynamic dy based on viewport

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

function render(data) {
    const root = d3.hierarchy(data);
    const treeLayout = d3.tree().nodeSize([dx, dy]);
    treeLayout(root);

    const nodes = root.descendants();
    const links = root.links();

    // Calculate bounds for auto-zoom (optional: can be used to fit tree)
    const minX = d3.min(nodes, d => d.x);
    const maxX = d3.max(nodes, d => d.x);
    const minY = d3.min(nodes, d => d.y);
    const maxY = d3.max(nodes, d => d.y);

    // Draw links first (behind nodes)
    g.selectAll('.link').data(links).join('path')
        .attr('class', 'link')
        .attr('d', d3.linkHorizontal().x(d => d.y).y(d => d.x));

    // Draw nodes
    const node = g.selectAll('.node').data(nodes).join('g')
        .attr('class', 'node')
        .attr('transform', d => `translate(${d.y},${d.x})`);

    node.append('circle').attr('r', 6);

    node.append('text')
        .attr('dy', '0.31em')
        .attr('x', d => d.children ? -10 : 10)
        .attr('text-anchor', d => d.children ? 'end' : 'start')
        .text(d => d.data.name + (d.data.date_of_birth ? ` (${d.data.date_of_birth})` : ''));
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