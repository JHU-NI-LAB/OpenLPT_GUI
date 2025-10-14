#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "myMATH.h"

namespace py = pybind11;

void bind_MyMath(py::module_& m)
{
    auto myMath = m.def_submodule("myMATH");

    myMath.def("imgCrossCorrAtPt",
           &myMATH::imgCrossCorrAtPt,
           py::arg("img"), py::arg("ref_img"), py::arg("cx"), py::arg("cy"));

    myMath.def(
        "triangulation",
        [](const std::vector<Line3D>& line_of_sight_list) {
            Pt3D pt_world{};
            double error = 0.0;
            myMATH::triangulation(pt_world, error, line_of_sight_list);
            return py::make_tuple(pt_world, error);  // 返回 (Pt3D, error)
        },
        py::arg("line_of_sight_list")
    );
}
