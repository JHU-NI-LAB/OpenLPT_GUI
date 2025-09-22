// pyBubbleResize.cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "BubbleResize.h"
#include "Matrix.h"          // 你项目里 Image 的头（与 pybind 的 Image 绑定一致）
#include <memory>

namespace py = pybind11;

void bind_BubbleResize(py::module_& m) {
    py::class_<BubbleResize>(m, "BubbleResize")
        .def(py::init<>(), "Create a BubbleResize processor.")
        .def(
            "ResizeBubble",
            [](BubbleResize& self,
               const Image& b_img,
               int d_b,
               double b_img_max) {
                py::gil_scoped_release release;
                Image out_ref = self.ResizeBubble(b_img, d_b, b_img_max);
                return Image(out_ref);
            },
            py::arg("b_img"),
            py::arg("d_b"),
            py::arg("b_img_max") = 255.0
            );
}
