#!/bin/bash
# Demo script showing the tree visualizer in action

echo "=============================================================================="
echo "GENEALOGY TREE VISUALIZER - DEMO"
echo "=============================================================================="
echo ""
echo "This script demonstrates the tree visualizer tool."
echo ""

# Get the Python executable
PYTHON="${PYTHON:-python}"

echo "1. Showing ANCESTOR tree for sample person (ID 2):"
echo "   Command: python tree_visualizer.py 2"
echo ""
$PYTHON tree_visualizer.py 2 | head -30
echo "   ... (truncated for demo)"
echo ""

echo "=============================================================================="
echo ""
echo "2. Showing DESCENDANT tree for sample person (ID 64):"
echo "   Command: python tree_visualizer.py --descendants 64"
echo ""
$PYTHON tree_visualizer.py --descendants 64
echo ""

echo "=============================================================================="
echo ""
echo "Try it yourself:"
echo "  python tree_visualizer.py <name_or_id>              # Show ancestors"
echo "  python tree_visualizer.py --descendants <name_or_id> # Show descendants"
echo "  python tree_visualizer.py --help                     # See all options"
echo ""
