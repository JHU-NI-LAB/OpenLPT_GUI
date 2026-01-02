# OpenLPT - Open-source Lagrangian Particle Tracking GUI

[![GitHub Stars](https://img.shields.io/github/stars/JHU-NI-LAB/OpenLPT_GUI?style=social)](https://github.com/JHU-NI-LAB/OpenLPT_GUI)
[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**OpenLPT** is a powerful, user-friendly open-source software for **3D Lagrangian Particle Tracking (LPT)**, designed for experimental fluid dynamics and flow visualization. Developed by the **Neural Interfaces Lab at Johns Hopkins University (JHU)**, it provides a comprehensive GUI-based workflow for high-precision particle tracking and reconstruction.

---

### 🚀 Key Capabilities
*   **3D Particle Tracking**: Robust Lagrangian tracking (LPT) and Shake-the-Box (STB) methods.
*   **Multi-Camera Calibration**: Easy-to-use tools for wand and plate calibration (intrinsic & extrinsic parameters).
*   **Cross-Platform**: Full support for **Windows**, **macOS**, and **Linux**.
*   **Performance**: High-performance C++ core with Python Python bindings for flexibility and speed.

**Keywords**: *Lagrangian Particle Tracking (LPT), Shake-the-Box (STB), 3D Flow Visualization, PIV, Particle Reconstruction, Multi-camera Calibration, Experimental Fluid Dynamics, JHU Neural Interfaces Lab.*

---

## Quick Start (Pre-compiled)

Look how easy it is to use:

```python
# Use in python
import pyopenlpt as lpt

# redirect std::cout to python 
redirector = lpt.PythonStreamRedirector() 

config_file = '${path_to_config_file}'
lpt.run(config_file)
```

## Features
- User-friendly interface in python
- Lagrangian particle tracking for multiple objects (point-like particles, spherical particles, etc.)
- Support stereomatching with multiple cameras (at least 2)
- Include multiple test cases for users to test and understand the code
- Better structure for adding new functions


## Installation

### Method 1: One-Click Installation (Recommended)

We provide automated scripts that set up everything for you (including Conda, environment, and dependencies).

1.  **Download the code**:
    ```bash
    git clone https://github.com/JHU-NI-LAB/OpenLPT_GUI.git
    cd OpenLPT_GUI
    ```

2.  **Run the Installer**:

    -   **Windows**: 
        Double-click `install_windows.bat`
        *(Or run in terminal: `install_windows.bat`)*

    -   **macOS**: 
        Run in terminal:
        ```bash
        bash install_mac.command
        ```

3.  **Run the GUI**:
    After installation, simply run:
    ```bash
    python GUI.py
    ```

### Method 2: Manual Installation

If you prefer to set up the environment manually:

1.  **Prerequisites**:
    - [Miniforge](https://github.com/conda-forge/miniforge) or [Anaconda](https://www.anaconda.com/)
    - C++ Compiler (Visual Studio 2022 for Windows, Clang for macOS/Linux)

2.  **Create Environment and Install**:

    ```bash
    # Create environment
    conda create -n OpenLPT python=3.10
    conda activate OpenLPT

    # Install dependencies
    mamba install -c conda-forge --file requirements.txt

    # Build and install the package
    pip install . --no-build-isolation
    ```

#### Troubleshooting

| Problem | Solution |
| :--- | :--- |
| **Windows**: Build fails | Install VS Build Tools and Win11 SDK |
| **macOS**: `omp.h` not found | See **macOS OpenMP Fix** section below |
| **macOS**: Architecture | `python -c "import platform; print(platform.machine())"` |
| **Linux**: Permissions | Use `chmod +x` or `sudo` |
| **All**: Stale cache | Delete `build/` folder and retry |
| **Windows**: Unicode Path | `install_windows.bat` handles this automatically |

#### macOS OpenMP Fix

If you get `fatal error: 'omp.h' file not found`:

```bash
export CC="$CONDA_PREFIX/bin/clang"
export CXX="$CONDA_PREFIX/bin/clang++"
export CPPFLAGS="-I$CONDA_PREFIX/include"
export LDFLAGS="-L$CONDA_PREFIX/lib -lomp"
pip install . --no-build-isolation
```

---

## Samples and Tests

Please see the sample format of configuration files, camera files and image files in `/test/test_STB` or `/test/test_STB_Bubble`.

To run the sample:
1. Open OpenLPT GUI.
2. Load the project configuration from the sample folders.
3. Click 'Run tracking'.

---

## Citation

If you use **OpenLPT** in your research, please cite our work:

```bibtex
@software{OpenLPT_GUI,
  author = {JHU Neural Interfaces Lab},
  title = {OpenLPT: Open-source Lagrangian Particle Tracking GUI},
  url = {https://github.com/JHU-NI-LAB/OpenLPT_GUI},
  year = {2026},
}
```

---

## Contact & Contribution

- **Issues**: Please report bugs or request features via [GitHub Issues](https://github.com/JHU-NI-LAB/OpenLPT_GUI/issues).
- **Organization**: Neural Interfaces Lab, Johns Hopkins University.
- **Support**: If you find this tool helpful, please give us a ⭐ on GitHub!
