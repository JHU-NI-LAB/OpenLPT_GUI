void init_BubbleRefImg(py::module &m) 
{
    py::class_<BubbleResize>(m, "BubbleResize")
        .def(py::init<>())
        .def("ResizeBubble", [](BubbleResize& self, Image const& b_img, int d_b, double b_img_max) {
            Image o_img(d_b, d_b, 0);
            self.ResizeBubble(o_img, b_img, d_b, b_img_max);
            return o_img;
        }, py::arg("b_img"), py::arg("d_b"), py::arg("b_img_max")=255)
        .doc() = "BubbleResize class";

    py::class_<BubbleRefImg>(m, "BubbleRefImg")
        .def(py::init<CamList const&>())
        .def("GetBubbleRefImg", [](BubbleRefImg& self, std::vector<Bubble3D> const& bb3d_list, std::vector<std::vector<Bubble2D>> const& bb2d_list_all, std::vector<Image> const& img_input, double r_thres, int n_bb_thres) {
            std::vector<Image> img_out;
            bool is_valid = self.GetBubbleRefImg(img_out, bb3d_list, bb2d_list_all, img_input, r_thres, n_bb_thres);
            return std::make_pair(is_valid, img_out);
        }, py::arg("bb3d_list"), py::arg("bb2d_list_all"), py::arg("img_input"), py::arg("r_thres")=6, py::arg("n_bb_thres")=5)
        .doc() = "BubbleRefImg class";
}