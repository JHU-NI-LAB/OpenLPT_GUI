#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "STB.h"
#include "Config.h"
#include "ImageIO.h"
#include "Track.h"

namespace py = pybind11;

#ifdef OPENLPT_EXPOSE_PRIVATE
// 这个 struct 名字要和头文件里的 FRIEND_DEBUG(STB) 一致：DebugAccess_STB
struct DebugAccess_STB
{
    // ==== private 函数 ====
    static void runInitPhase(STB &self, int frame_id, std::vector<Image> &img_list) {
        self.runInitPhase(frame_id, img_list);
    }

    static void runConvPhase(STB &self, int frame_id, std::vector<Image> &img_list) {
        self.runConvPhase(frame_id, img_list);
    }

    static void buildTrackFromPredField(STB &self, int frame_id, const PredField *pf) {
        self.buildTrackFromPredField(frame_id, pf);
    }

    static std::unique_ptr<Object3D> predictNext(const STB &self, const Track &tr) {
        return self.predictNext(tr);
    }

    static int findNN(const STB &self,
                      const STB::KDTreeObj3d &tree_obj3d,
                      const Pt3D &pt3d_est,
                      double radius)
    {
        return self.findNN(tree_obj3d, pt3d_est, radius);
    }

    static std::vector<ObjFlag> checkRepeat(const STB &self,
                                            const std::vector<std::unique_ptr<Object3D>> &objs)
    {
        return self.checkRepeat(objs);
    }

    static int linkShortTrack(STB &self,
                              const Track &track,
                              int n_iter,
                              const STB::KDTreeObj3d &tree_obj3d,
                              const STB::KDTreeTrack &tree_track)
    {
        return self.linkShortTrack(track, n_iter, tree_obj3d, tree_track);
    }

    static bool checkLinearFit(STB &self, const Track &track) {
        return self.checkLinearFit(track);
    }

    // ==== private 成员 ====
    static BasicSetting & _basic_setting(STB &self) {
        return self._basic_setting;
    }

    static ObjectConfig * _obj_config(STB &self) {
        return self._obj_config.get();
    }

    // _ipr_candidate: vector<vector<unique_ptr<Object3D>>> 不能直接拷贝
    // 这里返回一个新的 2D 容器，里面是 Object3D*，只读调试用
    static std::vector<std::vector<Object3D*>> _ipr_candidate(STB &self) {
        std::vector<std::vector<Object3D*>> out;
        out.reserve(self._ipr_candidate.size());
        for (auto &row_uptr : self._ipr_candidate) {
            std::vector<Object3D*> row;
            row.reserve(row_uptr.size());
            for (auto &p : row_uptr) {
                row.push_back(p.get());
            }
            out.push_back(std::move(row));
        }
        return out;
    }
};
#endif  // OPENLPT_EXPOSE_PRIVATE

void bind_STB(py::module_& m)
{
    py::class_<STB>(m, "STB")
        // STB(BasicSetting const& setting, std::string const& type, std::string const& obj_cfg_path)
        .def(py::init<const BasicSetting&, const std::string&, const std::string&>(),
             py::arg("setting"), py::arg("obj_type"), py::arg("obj_cfg_path"))
        // 处理一帧（把图像作为 Image = Matrix<double> 的列表传进来）
        .def("process_frame",
         [](STB& self, int frame_id, std::vector<Image> img_list) {
             self.processFrame(frame_id, img_list);  
             return img_list;                         
         },
         py::arg("frame_id"), py::arg("img_list"),
         "Run STB on a frame; returns the modified residual images.")
        // 批量保存/加载（便于 Python 快速验证）
        .def("saveTracksAll", &STB::saveTracksAll, py::arg("folder"), py::arg("t"))
        .def("loadTracksAll", &STB::loadTracksAll, py::arg("folder"), py::arg("t"))

        .def_property_readonly("_short_track_active",
            [](STB &self) {
                py::list out;
                auto parent = py::cast(&self);  // 作为 reference_internal 的父对象
                for (auto &tr : self._short_track_active) {
                    out.append(py::cast(&tr,
                        py::return_value_policy::reference_internal,
                        parent));
                }
                return out;
            })

        .def_property_readonly("_long_track_active",
            [](STB &self) {
                py::list out;
                auto parent = py::cast(&self);
                for (auto &tr : self._long_track_active) {
                    out.append(py::cast(&tr,
                        py::return_value_policy::reference_internal,
                        parent));
                }
                return out;
            })

        .def_property_readonly("_long_track_inactive",
            [](STB &self) {
                py::list out;
                auto parent = py::cast(&self);
                for (auto &tr : self._long_track_inactive) {
                    out.append(py::cast(&tr,
                        py::return_value_policy::reference_internal,
                        parent));
                }
                return out;
            })

        .def_property_readonly("_exit_track",
            [](STB &self) {
                py::list out;
                auto parent = py::cast(&self);
                for (auto &tr : self._exit_track) {
                    out.append(py::cast(&tr,
                        py::return_value_policy::reference_internal,
                        parent));
                }
                return out;
            })
            #ifdef OPENLPT_EXPOSE_PRIVATE
        // ====== Private 函数，接口名和成员名一致 ======

        .def("runInitPhase",
             [](STB &self, int frame_id, std::vector<Image> &img_list) {
                 DebugAccess_STB::runInitPhase(self, frame_id, img_list);
             },
             py::arg("frame_id"),
             py::arg("img_list"))

        .def("runConvPhase",
             [](STB &self, int frame_id, std::vector<Image> &img_list) {
                 DebugAccess_STB::runConvPhase(self, frame_id, img_list);
             },
             py::arg("frame_id"),
             py::arg("img_list"))

        .def("buildTrackFromPredField",
             [](STB &self, int frame_id, const PredField *pf) {
                 DebugAccess_STB::buildTrackFromPredField(self, frame_id, pf);
             },
             py::arg("frame_id"),
             py::arg("pred_field"))

        .def("predictNext",
             [](STB &self, const Track &tr) {
                 // 返回 unique_ptr<Object3D>，交给 Python 接管
                 return DebugAccess_STB::predictNext(self, tr);
             },
             py::arg("track"))

        // .def("findNN",
        //      [](STB &self,
        //         const STB::KDTreeObj3d &tree_obj3d,
        //         const Pt3D &pt3d_est,
        //         double radius) {
        //          return DebugAccess_STB::findNN(self, tree_obj3d, pt3d_est, radius);
        //      },
        //      py::arg("tree_obj3d"),
        //      py::arg("pt3d_est"),
        //      py::arg("radius"))

        // .def("checkRepeat",
        //      [](STB &self,
        //         const std::vector<std::unique_ptr<Object3D>> &objs) {
        //          return DebugAccess_STB::checkRepeat(self, objs);
        //      },
        //      py::arg("objs"))

        // .def("linkShortTrack",
        //      [](STB &self,
        //         const Track &track,
        //         int n_iter,
        //         const STB::KDTreeObj3d &tree_obj3d,
        //         const STB::KDTreeTrack &tree_track) {
        //          return DebugAccess_STB::linkShortTrack(self, track, n_iter, tree_obj3d, tree_track);
        //      },
        //      py::arg("track"),
        //      py::arg("n_iter"),
        //      py::arg("tree_obj3d"),
        //      py::arg("tree_track"))

        .def("checkLinearFit",
             [](STB &self, const Track &track) {
                 return DebugAccess_STB::checkLinearFit(self, track);
             },
             py::arg("track"))

        // ====== Private 成员，接口名和成员名一致 ======

        .def_property_readonly("_basic_setting",
             [](STB &self) -> BasicSetting& {
                 return DebugAccess_STB::_basic_setting(self);
             },
             py::return_value_policy::reference_internal)

        .def_property_readonly("_obj_config",
             [](STB &self) -> ObjectConfig* {
                 return DebugAccess_STB::_obj_config(self);
             },
             py::return_value_policy::reference_internal)

        .def_property_readonly("_ipr_candidate",
             [](STB &self) {
                 // 返回 2D list[ list[Object3D] ]，元素是指针引用
                 auto vec2d = DebugAccess_STB::_ipr_candidate(self);
                 py::list outer;
                 for (auto &row : vec2d) {
                     py::list inner;
                     for (auto *p : row) {
                         inner.append(py::cast(p,
                             py::return_value_policy::reference_internal));
                     }
                     outer.append(inner);
                 }
                 return outer;
             })
#endif // OPENLPT_EXPOSE_PRIVATE
        ;
}
