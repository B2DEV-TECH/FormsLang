"""Sidecar entry point: the same CLI, frozen into a single exe."""
import sys

from formslang.cli import main

if __name__ == "__main__":
    sys.exit(main())
