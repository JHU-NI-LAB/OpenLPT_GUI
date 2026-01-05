# OpenLPT - Open-source Lagrangian Particle Tracking GUI

[![GitHub Stars](https://img.shields.io/github/stars/JHU-NI-LAB/OpenLPT_GUI?style=social)](https://github.com/JHU-NI-LAB/OpenLPT_GUI)
[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**OpenLPT** is a powerful, user-friendly open-source software for **3D Lagrangian Particle Tracking (LPT)**, designed for experimental fluid dynamics and flow visualization. Developed by the **Ni Research Lab at Johns Hopkins University (JHU)**, it provides a comprehensive GUI-based workflow for high-precision particle tracking and reconstruction.

---

### 🚀 Key Capabilities
*   **3D Particle Tracking**: Robust Lagrangian tracking (LPT) and Shake-the-Box (STB) methods.
*   **Multi-Camera Calibration**: Easy-to-use tools for wand and plate calibration (intrinsic & extrinsic parameters).
*   **Cross-Platform**: Full support for **Windows**, **macOS**, and **Linux**.
*   **Performance**: High-performance C++ core with Python Python bindings for flexibility and speed.

**Keywords**: *Lagrangian Particle Tracking (LPT), Shake-the-Box (STB), 3D Flow Visualization, PIV, Particle Reconstruction, Multi-camera Calibration, Experimental Fluid Dynamics, JHU Ni Research Lab.*

---

## Quick Start

> [!TIP]
> Ensure you have activated your environment before running these commands: `conda activate OpenLPT`
> (On **Windows**, we recommend using **Command Prompt (CMD)** as PowerShell may have execution policy restrictions).

### 1. Graphical User Interface (GUI)
```bash
# Launch the interactive GUI
openlpt-gui
```

### 2. Command Line Interface (CLI)
```bash 
# Run STB tracking directly with a config file
openlpt path/to/config.txt
```

### 3. Python API
```python
import openlpt as lpt

# Run tracking programmatically
lpt.run('path/to/config.txt')

# Or launch GUI from within a script
lpt.launch_gui()
```

---

## Demo

https://github.com/user-attachments/assets/60579007-4f24-4989-8b36-3de2224c9797

---

## Features
- User-friendly interface in python
- Lagrangian particle tracking for multiple objects (point-like particles, spherical particles, etc.)
- Support stereomatching with multiple cameras (at least 2)
- Include multiple test cases for users to test and understand the code
- Better structure for adding new functions


## Installation

### Method 1: One-Click Installation (Recommended for developers)

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
    -   **Linux**: 
        Run in terminal:
        ```bash
        bash install_linux.sh
        ```

3.  **Launch the GUI**:
    After installation, simply run:
    ```bash
    openlpt-gui
    ```

### Method 2: Direct Pip Installation (Easiest)

You can install OpenLPT directly from PyPI:

- **For GUI Support (Recommended)**:
  ```bash
  pip install "openlpt[gui]"
  ```
- **For CLI-only**:
  ```bash
  pip install "openlpt"
  ```

<details>
<summary><h3>Method 3: Manual Installation (Click to expand)</h3></summary>

If you prefer to set up the environment manually:

1.  **Prerequisites**:
    - [Miniforge](https://github.com/conda-forge/miniforge) or [Anaconda](https://www.anaconda.com/)
    - C++ Compiler (Visual Studio 2022 for Windows, Clang for macOS/Linux)

1.  **Create Environment and Install**:

    ```bash
    # Create environment
    conda create -n OpenLPT python=3.10
    conda activate OpenLPT

    # Build and install the package
    pip install .
    ```

#### Troubleshooting

| Problem | Solution |
| :--- | :--- |
| **Windows**: Build fails | Install VS Build Tools and Win11 SDK |
| **macOS**: `omp.h` not found | See **macOS OpenMP Fix** section below |
| **macOS**: Architecture | `python -c "import platform; print(platform.machine())"` |
| **Linux**: Permissions | Use `chmod +x` or `sudo` |
| **All**: Stale cache | Delete `build/` folder and retry |
| **Installation**: Build isolation | If compilation fails due to network, try `pip install . --no-build-isolation` |

#### macOS OpenMP Fix

If you get `fatal error: 'omp.h' file not found`:

```bash
export CC="$CONDA_PREFIX/bin/clang"
export CXX="$CONDA_PREFIX/bin/clang++"
export CPPFLAGS="-I$CONDA_PREFIX/include"
export LDFLAGS="-L$CONDA_PREFIX/lib -lomp"
pip install -e .
```

</details>

---

## Samples and Tests

Please see the sample format of configuration files, camera files and image files in `/test/test_STB` or `/test/test_STB_Bubble`.

To run the sample:
1. Open OpenLPT GUI.
2. Load the project configuration from the sample folders.
3. Click 'Run tracking'.

---

## Citation

If you use **OpenLPT** in your research, please cite our publications:

- Tan, S., Salibindla, A., Masuk, A.U.M. and Ni, R., 2020. **Introducing OpenLPT: new method of removing ghost particles and high-concentration particle shadow tracking**. *Experiments in Fluids*, 61(2), p.47.
- Tan, S., Zhong, S. and Ni, R., 2023. **3D Lagrangian tracking of polydispersed bubbles at high image densities**. *Experiments in Fluids*, 64(4), p.85.

## License

This repository contains a mix of original code and **MATLAB Coder-generated** files under a MathWorks **Academic License**.

### ⚠️ Restricted Paths (MATLAB Coder-generated)
The following paths contain code generated by MATLAB Coder and are **NOT** covered by the general MIT/Open-source license of this repository:

- `/src/srcObject/BubbleCenterAndSizeByCircle`
- `/src/srcObject/BubbleCenterAndSizeByCircle/CircleIdentifier.cpp`
- `/src/srcObject/BubbleResize`
- `/inc/libObject/BubbleCenterAndSizeByCircle`
- `/inc/libObject/CircleIdentifier.h`
- `/inc/libObject/BubbleResize`

### 📜 Terms and Conditions
For the paths listed above:
- **ACADEMIC INTERNAL OPERATIONS ONLY**: Usage is restricted to teaching, academic research, and course requirements. 
- **NO Commercial Use**: Government, commercial, or other organizational use is **NOT permitted**.
- **Header Preservation**: Do not modify or remove the "Academic License" header comments in these files.
- **No Sublicensing**: These files are not sublicensed under this repository's open-source license.
- **Redistribution**: If you redistribute this repository, you must keep the original Academic License headers in the generated files.
- **Modification**: If you need to modify the generated code, you must hold a valid MathWorks MATLAB Coder license.

All **other** files in this repository are original work and are distributed under the **MIT License** (see `LICENSE`).

---

## Contact & Contribution

- **Issues**: Please report bugs or request features via [GitHub Issues](https://github.com/JHU-NI-LAB/OpenLPT_GUI/issues).
- **Contact**: For questions, please contact szhong12@jhu.edu or tanshiyong84@gmail.com.
- **Organization**: Ni Research Lab, Johns Hopkins University.
- **Support**: If you find this tool helpful, please give us a ⭐ on GitHub!
