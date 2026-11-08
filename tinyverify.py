#!/usr/bin/env python3
"""Back-compat shim: the package now lives in tinyverify/.

Usage is unchanged: python3 tinyverify.py --name "Tesco" --jurisdiction BOTH --monitor
"""

import sys

from tinyverify.cli import main

if __name__ == "__main__":
    sys.exit(main())
