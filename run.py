import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mash.cli import run  # noqa: E402

run()
