// Simple D3 v7 tree viewer. Expects a JSON file `demo_tree.json` in the same directory.

const width = 960;
const dx = 20;
const dy = width / 6;
const margin = {top: 20, right: 120, bottom: 20, left: 120};

const svg = d3.select('#chart').append('svg')
    .attr('width', width)
    .attr('height', 600)
  .append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`);

function render(data) {
  const root = d3.hierarchy(data);
  const treeLayout = d3.tree().nodeSize([dx, dy]);
  treeLayout(root);

  const nodes = root.descendants();
  const links = root.links();

  const minX = d3.min(nodes, d => d.x);
  const maxX = d3.max(nodes, d => d.x);
  const height = maxX - minX + margin.top + margin.bottom;
  d3.select('svg').attr('height', height + 40);

  const link = svg.selectAll('.link').data(links).join('path')
    .attr('class', 'link')
    .attr('d', d3.linkHorizontal().x(d => d.y).y(d => d.x));

  const node = svg.selectAll('.node').data(nodes).join('g')
    .attr('class', 'node')
    .attr('transform', d => `translate(${d.y},${d.x})`);

  node.append('circle').attr('r', 6);

  node.append('text')
    .attr('dy', '0.31em')
    .attr('x', d => d.children ? -10 : 10)
    .attr('text-anchor', d => d.children ? 'end' : 'start')
    .text(d => d.data.name + (d.data.date_of_birth ? ` (${d.data.date_of_birth})` : ''));
}

// Load demo JSON
fetch('demo_tree.json').then(r => r.json()).then(render).catch(err => {
  d3.select('#chart').append('p').text('Failed to load demo_tree.json: ' + err.message);
});