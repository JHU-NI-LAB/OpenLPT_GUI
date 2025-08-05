// ShakeDebug.hpp
#pragma once

#include "Shake.h"

class ShakeDebug {
public:
    ShakeDebug() {};
    ~ShakeDebug() {};

    // Tracers
    static void absResImg(Shake& s) { s.absResImg(); }
    static void shakeTracers(Shake& s, std::vector<Tracer3D>& list, const OTF& otf, const std::vector<Image>& imgs, bool tri_only = false) {
        s.shakeTracers(list, otf, imgs, tri_only);
    }
    static double shakeOneTracer(Shake& s, Tracer3D& tr, const OTF& otf, double delta, double score_old) {
        return s.shakeOneTracer(tr, otf, delta, score_old);
    }
    static double shakeOneTracerGrad(Shake& s, Tracer3D& tr, const OTF& otf, double delta, double score_old, double lr = 1e-4) {
        return s.shakeOneTracerGrad(tr, otf, delta, score_old, lr);
    }
    static void calResImgTracer(Shake& s, const std::vector<Tracer3D>& list, const OTF& otf, const std::vector<Image>& imgs) {
        s.calResImg(list, otf, imgs);
    }
    static ImgAugList calAugimgTracer(Shake& s, Tracer3D& tr, const OTF& otf) {
        return s.calAugimg(tr, otf);
    }
    static void findGhostTracer(Shake& s, std::vector<Tracer3D>& list) {
        s.findGhost(list);
    }
    static void checkRepeatedObjTracer(Shake& s, const std::vector<Tracer3D>& list, double tol) {
        s.checkRepeatedObj(list, tol);
    }

    // Bubbles
    static void shakeBubbles(Shake& s, std::vector<Bubble3D>& list, const std::vector<Image>& imgs, const BubbleRefImg& refs, bool tri_only = false) {
        s.shakeBubbles(list, imgs, refs, tri_only);
    }
    static double shakeOneBubble(Shake& s, Bubble3D& b, const BubbleRefImg& refs, const std::vector<Image>& imgs, double delta, double score_old) {
        return s.shakeOneBubble(b, refs, imgs, delta, score_old);
    }
    std::vector<Image> calResImgBubble(Shake& s, const std::vector<Bubble3D>& list, const BubbleRefImg& refs, const std::vector<Image>& imgs) {
        // Initialize lists
        s._imgRes_list.clear();
        s._is_ghost.resize(list.size(), 0);
        s._n_ghost = 0;

        // Initialize residue image
        int cam_id;
        for (int id = 0; id < s._n_cam_use; id ++)
        {
            cam_id = s._cam_list.useid_list[id];
            s._imgRes_list.push_back(imgs[cam_id]);
        }
        s.calResImg(list, refs, imgs);
        return s._imgRes_list;
    }
    static ImgAugList calAugimgBubble(Shake& s, Bubble3D& b, const BubbleRefImg& refs, const std::vector<Image>& imgs, std::vector<Image>& corr_map, std::vector<int>& mismatch) {
        return s.calAugimg(b, refs, imgs, corr_map, mismatch);
    }
    static void findGhostBubble(Shake& s, std::vector<Bubble3D>& list) {
        s.findGhost(list);
    }
    static void checkRepeatedObjBubble(Shake& s, const std::vector<Bubble3D>& list, double tol) {
        s.checkRepeatedObj(list, tol);
    }

    // Auxiliary
    static PixelRange findRegion(Shake& s, int id, double y, double x, double half) {
        return s.findRegion(id, y, x, half);
    }
    static double gaussIntensity(Shake& s, int x, int y, const Pt2D& pt, const std::vector<double>& otf) {
        return s.gaussIntensity(x, y, pt, otf);
    }
    static double calPointResidue(Shake& s, const Tracer3D& tr, const ImgAugList& list, const OTF& otf) {
        return s.calPointResidue(tr, list, otf);
    }
    static double updateTracer(Shake& s, Tracer3D& tr, ImgAugList& list, const OTF& otf, double delta) {
        return s.updateTracer(tr, list, otf, delta);
    }
    static double updateTracerGrad(Shake& s, Tracer3D& tr, ImgAugList& list, const OTF& otf, double delta, double lr) {
        return s.updateTracerGrad(tr, list, otf, delta, lr);
    }
    static void updateImgAugList(Shake& s, ImgAugList& list, const Tracer3D& tr) {
        s.updateImgAugList(list, tr);
    }
    static double calTracerScore(Shake& s, const Tracer3D& tr, const ImgAugList& list, const OTF& otf, double score) {
        return s.calTracerScore(tr, list, otf, score);
    }
    static bool isCamValidForShaking(Shake& s, int cam_id, const PixelRange& region, const BubbleRefImg& ref, const Image& img, const Bubble2D& bb2d) {
        return s.isCamValidForShaking(cam_id, region, ref, img, bb2d);
    }
    static double updateBubble(Shake& s, Bubble3D& b, std::vector<int>& mismatch, const BubbleRefImg& refs, ImgAugList& list, std::vector<Image>& corr_map, double delta) {
        return s.updateBubble(b, mismatch, refs, list, corr_map, delta);
    }
    static std::pair<double, std::vector<double>> calBubbleResidue(Shake& s, std::vector<Image>& corr_map, const Bubble3D& b, const std::vector<int>& mismatch, const ImgAugList& list, const BubbleRefImg& refs) {
        return s.calBubbleResidue(corr_map, b, mismatch, list, refs);
    }
    static double imgCrossCorr(Shake& s, const Image& aug, const PixelRange& region, const Image& ref, double max_int, double x, double y, double r) {
        return s.imgCrossCorr(aug, region, ref, max_int, x, y, r);
    }
    static double getCorrInterp(Shake& s, Image& corr_map, int x, int y, double r_px, const Image& aug, const PixelRange& region, const Image& ref, double max_int) {
        return s.getCorrInterp(corr_map, x, y, r_px, aug, region, ref, max_int);
    }
    static double calBubbleScore(Shake& s, const Bubble3D& b, const ImgAugList& list, const std::vector<int>& mismatch, double score) {
        return s.calBubbleScore(b, list, mismatch, score);
    }
};