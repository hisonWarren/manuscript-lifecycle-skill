#!/usr/bin/env python3
"""Run packaged mechanical regressions; behavioral tests are separate."""
from pathlib import Path
import unittest
import sys

if __name__ == '__main__':
    here=Path(__file__).resolve().parent
    suite=unittest.defaultTestLoader.discover(str(here),pattern='test_*.py')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
