#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
"""Compatibility entry point for existing sink-switching shortcuts."""
import sys
from pathlib import Path

# This entry point is symlinked from ~/Bin to ~/Opt/Codex.
sys.path.insert(0, str(Path.home() / 'Bin'))
from SoundSinkSwitcher import main

if __name__ == '__main__':
    sys.exit(main())
