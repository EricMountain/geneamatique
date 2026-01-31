import unittest
import subprocess
import sys


class TestModuleExecution(unittest.TestCase):
    def test_tree_visualizer_module_runs_help(self):
        """Ensure running the module via -m works (no sys.path hacks needed)."""
        proc = subprocess.run(
            [sys.executable, '-m', 'import_tools.tree_visualizer', '--help'], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0,
                         f"Module failed to run: {proc.stderr}")
        self.assertIn('Visualize genealogy trees', proc.stdout)


if __name__ == '__main__':
    unittest.main()
