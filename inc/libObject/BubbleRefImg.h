#ifndef BUBBLEREFIMG_H
#define BUBBLEREFIMG_H

#include <vector>
#include <typeinfo>

#include "BubbleResize.h"
#include "ObjectInfo.h"
#include "Matrix.h"
#include "STBCommons.h"
#include "myMATH.h"


class BubbleRefImg {
public:
    // user needs to make sure cam_list.useid_list is well defined
    BubbleRefImg(CamList const& cam_list) : _cam_list(cam_list){};

    ~BubbleRefImg() {};

    bool GetBubbleRefImg(std::vector<Bubble3D> const& bb3d_list, std::vector<std::vector<Bubble2D>> const& bb2d_list_all, std::vector<Image> const& img_input, double r_thres = 6, int n_bb_thres = 5);

    const Image& operator[](int camID) const{
        return img_Ref_list[camID];
    };

    double getIntRef(int camID) const {
        return intRef_list[camID];
    };

private:
    CamList const& _cam_list;
    std::vector<Image> img_Ref_list; // reference images for each camera
    std::vector<double> intRef_list;  // average intensity of reference images for each camera
};


#endif // BUBBLEREFIMG_H