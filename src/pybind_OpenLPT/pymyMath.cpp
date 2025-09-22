#include <pybind11/pybind11.h>
#include "myMATH.h"

namespace py = pybind11;

void bind_MyMath(py::module_& m)
{
    auto myMath = m.def_submodule("myMATH");

    myMath.def("imgCrossCorrAtPt",
           &myMATH::imgCrossCorrAtPt,
           py::arg("img"), py::arg("ref_img"), py::arg("cx"), py::arg("cy"));
}
