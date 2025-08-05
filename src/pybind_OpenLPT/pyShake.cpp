
void init_Shake(py::module& m)
{
    py::class_<ImgAugList>(m, "ImgAugList")
        .def(py::init<>())
        .def_readwrite("img_list", &ImgAugList::img_list)
        .def_readwrite("region_list", &ImgAugList::region_list)
        .def("to_dict", [](ImgAugList const& self){
            return py::dict(
                "img_list"_a=self.img_list, "region_list"_a=self.region_list
            );
        })
        .doc() = "ImgAugList struct";

    py::class_<Shake>(m, "Shake")
        .def(py::init<CamList const&, double, double, double, int, int>(), py::arg("cam_list"), py::arg("shake_width"), py::arg("tol_3d"), py::arg("score_min")=0.1, py::arg("n_loop")=4, py::arg("n_thread")=0)
        .def("runShake", [](Shake& self, std::vector<Tracer3D>const& obj3d_list, OTF const& otf, std::vector<Image> const& imgOrig_list, bool tri_only){
            std::vector<Tracer3D> tr3d_list_shake(obj3d_list);
            self.runShake(tr3d_list_shake, otf, imgOrig_list, tri_only);
            return tr3d_list_shake;
        }, py::arg("obj3d_list"), py::arg("otf"), py::arg("imgOrig_list"), py::arg("tri_only")=false)
        .def("runShake", [](Shake& self, std::vector<Bubble3D>const& obj3d_list, std::vector<Image> const& imgOrig_list, BubbleRefImg const& imgRef_list, bool tri_only){
            std::vector<Bubble3D> bb3d_list_shake(obj3d_list);
            self.runShake(bb3d_list_shake, imgOrig_list, imgRef_list, tri_only);
            return bb3d_list_shake;
        }, py::arg("obj3d_list"), py::arg("imgOrig_list"), py::arg("imgRef_list"), py::arg("tri_only")=false)
        .def_readwrite("_imgRes_list", &Shake::_imgRes_list)
        .def_readwrite("_score_list", &Shake::_score_list)
        .def_readwrite("_is_ghost", &Shake::_is_ghost)
        .def_readwrite("_is_repeated", &Shake::_is_repeated)
        .def_readwrite("_n_ghost", &Shake::_n_ghost)
        .def_readwrite("_n_repeated", &Shake::_n_repeated)
        .def("to_dict", [](Shake const& self){
            return py::dict(
                "_imgRes_list"_a=self._imgRes_list, "_score_list"_a=self._score_list, "_is_ghost"_a=self._is_ghost, "_is_repeated"_a=self._is_repeated, "_n_ghost"_a=self._n_ghost, "_n_repeated"_a=self._n_repeated
            );
        })
        .doc() = "Shake class";
    
    
    // Debug-only binding begins here
    m.def("absResImg_debug", &ShakeDebug::absResImg);
    m.def("shakeTracers_debug", &ShakeDebug::shakeTracers);
    m.def("shakeOneTracer_debug", &ShakeDebug::shakeOneTracer);
    m.def("shakeOneTracerGrad_debug", &ShakeDebug::shakeOneTracerGrad);
    m.def("calResImgTracer_debug", &ShakeDebug::calResImgTracer);
    m.def("calAugimgTracer_debug", &ShakeDebug::calAugimgTracer);
    m.def("findGhostTracer_debug", &ShakeDebug::findGhostTracer);
    m.def("checkRepeatedObjTracer_debug", &ShakeDebug::checkRepeatedObjTracer);

    m.def("shakeBubbles_debug", &ShakeDebug::shakeBubbles);
    m.def("shakeOneBubble_debug", &ShakeDebug::shakeOneBubble);
    // m.def("calResImgBubble_debug", &ShakeDebug::calResImgBubble);
    m.def("calResImgBubble_debug", [](Shake& s, std::vector<Bubble3D> const& bb3d_list, BubbleRefImg const& imgRef_list, std::vector<Image> const& imgOrig_list) {
        ShakeDebug sb;
        return sb.calResImgBubble(s, bb3d_list, imgRef_list, imgOrig_list);
    });
    m.def("calAugimgBubble_debug", &ShakeDebug::calAugimgBubble);
    m.def("findGhostBubble_debug", &ShakeDebug::findGhostBubble);
    m.def("checkRepeatedObjBubble_debug", &ShakeDebug::checkRepeatedObjBubble);

    m.def("findRegion_debug", &ShakeDebug::findRegion);
    m.def("gaussIntensity_debug", &ShakeDebug::gaussIntensity);
    m.def("calPointResidue_debug", &ShakeDebug::calPointResidue);
    m.def("updateTracer_debug", &ShakeDebug::updateTracer);
    m.def("updateTracerGrad_debug", &ShakeDebug::updateTracerGrad);
    m.def("updateImgAugList_debug", &ShakeDebug::updateImgAugList);
    m.def("calTracerScore_debug", &ShakeDebug::calTracerScore);
    m.def("isCamValidForShaking_debug", &ShakeDebug::isCamValidForShaking);
    m.def("updateBubble_debug", &ShakeDebug::updateBubble);
    m.def("calBubbleResidue_debug", &ShakeDebug::calBubbleResidue);
    m.def("imgCrossCorr_debug", &ShakeDebug::imgCrossCorr);
    m.def("getCorrInterp_debug", &ShakeDebug::getCorrInterp);
    m.def("calBubbleScore_debug", &ShakeDebug::calBubbleScore);
}
