# setup.py — build the CMake-based extension "openlpt" using pip-installed pybind11
import os, sys, platform, subprocess
from pathlib import Path
from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext

# 关键：作为“构建时依赖”，确保 pip 会在构建前装好 pybind11
# 更推荐在 pyproject.toml 里声明（见文末备忘）；这里只是运行时兜底 import。
try:
    import pybind11
    PYBIND11_DIR = pybind11.get_cmake_dir()
except Exception as e:
    print("ERROR: pybind11 is required. Install with: python -m pip install pybind11")
    raise

class CMakeExtension(Extension):
    def __init__(self, name, sourcedir=""):
        super().__init__(name, sources=[])
        self.sourcedir = str(Path(sourcedir).resolve())

class CMakeBuild(build_ext):
    def run(self):
        # [Windows] Robust Visual Studio Detection
        # CMake 3.x+ often fails to find "Build Tools" (vs_buildtools.exe) installations automatically.
        # We manually find the installation path using `vswhere` and set CMAKE_GENERATOR_INSTANCE.
        if platform.system() == "Windows" and "CMAKE_GENERATOR_INSTANCE" not in os.environ:
            try:
                # Default vswhere location
                vswhere = r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
                if os.path.exists(vswhere):
                    # Check for VCTools (Build Tools) or NativeDesktop (IDE)
                    cmd = [vswhere, "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Workload.VCTools", "-property", "installationPath"]
                    output = subprocess.check_output(cmd, encoding='utf-8').strip()
                    
                    if not output: # Try NativeDesktop if VCTools not found
                        cmd[5] = "Microsoft.VisualStudio.Workload.NativeDesktop"
                        output = subprocess.check_output(cmd, encoding='utf-8').strip()

                    if output:
                        print(f"[setup.py] Found Visual Studio at: {output}")
                        print(f"[setup.py] Force-setting CMAKE_GENERATOR_INSTANCE to help CMake.")
                        os.environ["CMAKE_GENERATOR_INSTANCE"] = output
                        os.environ["CMAKE_GENERATOR"] = "Visual Studio 17 2022"
                    else:
                        print("[setup.py] vswhere found no suitable Visual Studio installation.")
            except Exception as e:
                print(f"[setup.py] Failed to run vswhere: {e}")

        subprocess.check_call(["cmake", "--version"])
        for ext in self.extensions:
            self.build_extension(ext)

    def build_extension(self, ext):
        extdir = Path(self.get_ext_fullpath(ext.name)).parent.resolve()
        cfg = "Debug" if self.debug else "Release"

        cmake_args = [
            f"-DPYOPENLPT=ON",
            f"-DPython_EXECUTABLE={sys.executable}",
            f"-Dpybind11_DIR={PYBIND11_DIR}",
            f"-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={extdir}",
            "-DOPENLPT_PYBIND11_PROVIDER=pip",
        ]
        build_args = ["--config", cfg]

        if platform.system() == "Windows":
            cmake_args += [f"-DCMAKE_LIBRARY_OUTPUT_DIRECTORY_{cfg.upper()}={extdir}"]
            # Let CMake auto-detect the Visual Studio version (now aided by env vars)
            build_args += ["--", "/m"]
        else:
            cmake_args += [f"-DCMAKE_BUILD_TYPE={cfg}", "-DCMAKE_POSITION_INDEPENDENT_CODE=ON"]
            build_args += ["--", "-j"]

        build_temp = Path(self.build_temp).resolve()
        build_temp.mkdir(parents=True, exist_ok=True)

        subprocess.check_call(["cmake", ext.sourcedir] + cmake_args, cwd=build_temp)
        subprocess.check_call(["cmake", "--build", "."] + build_args, cwd=build_temp)

from _version import __version__

setup(
    name="openlpt",
    version=__version__,
    description="OpenLPT Python bindings",
    author="Shiyong Tan, Shijie Zhong",
    author_email="szhong12@jhu.edu",
    ext_modules=[CMakeExtension("pyopenlpt", sourcedir=".")],
    cmdclass={"build_ext": CMakeBuild},
    zip_safe=False,
    install_requires=[
        "numpy>=1.16.0",
        "pandas>=1.0.0",
        "pybind11>=2.10"  # 运行时/编译时都需要
    ],
    packages=[],
    include_package_data=True,
)
