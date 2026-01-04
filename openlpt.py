"""
OpenLPT - Open-source Lagrangian Particle Tracking
Unified entry point for API, CLI, and GUI.
"""

import sys
import argparse
import os
from pathlib import Path

# --- Package Version ---
try:
    from _version import __version__
except ImportError:
    __version__ = "0.1.0"

# --- C++ Extension Import ---
try:
    import pyopenlpt
    # Expose core C++ functionality to the openlpt namespace
    from pyopenlpt import *
except ImportError:
    # This might happen if the C++ extension hasn't been compiled yet
    pyopenlpt = None

def launch_gui():
    """
    Launches the OpenLPT Graphical User Interface.
    """
    # Use absolute path to the gui folder relative to this file
    pkg_root = Path(__file__).parent.resolve()
    gui_path = pkg_root / "gui"
    
    # Add gui folder to sys.path so that internal relative imports work
    if str(gui_path) not in sys.path:
        sys.path.insert(0, str(gui_path))
    
    # Also ensure the package root is in path for 'gui.xxx' imports
    if str(pkg_root) not in sys.path:
        sys.path.insert(0, str(pkg_root))

    try:
        from gui.app import main as gui_main
        print("Launching OpenLPT GUI...")
        gui_main()
    except ImportError as e:
        print(f"Error: Could not launch GUI. {e}")
        print("Make sure all dependencies (PySide6, QtAwesome) are installed.")
        sys.exit(1)

def run_stb(config_file_path):
    """
    Runs the STB tracking core using a configuration file.
    """
    if pyopenlpt is None:
        print("Error: OpenLPT C++ core (pyopenlpt) is not installed or compiled.")
        sys.exit(1)
        
    config_path = Path(config_file_path).resolve()
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)
        
    print(f"Starting OpenLPT STB with configuration: {config_path}")
    try:
        pyopenlpt.run(str(config_path))
    except Exception as e:
        print(f"OpenLPT Execution Error: {e}")
        sys.exit(1)

def main():
    """
    Main CLI entry point for 'openlpt' command.
    """
    parser = argparse.ArgumentParser(
        description="OpenLPT: Open-source Lagrangian Particle Tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  openlpt --gui             # Launch the GUI (default)
  openlpt config.txt        # Run STB tracking using the specified config
  openlpt-gui               # Alternative command for GUI
"""
    )
    
    parser.add_argument("config", nargs="?", help="Path to the configuration file to run STB.")
    parser.add_argument("--gui", action="store_true", help="Launch the GUI.")
    parser.add_argument("-v", "--version", action="store_true", help="Show OpenLPT version.")

    args = parser.parse_args()

    if args.version:
        print(f"OpenLPT version {__version__}")
        return

    # If a config is provided, run the STB core
    if args.config:
        run_stb(args.config)
    # Default behavior: launch GUI
    else:
        launch_gui()

if __name__ == "__main__":
    main()
