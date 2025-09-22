//
// Academic License - for use in teaching, academic research, and meeting
// course requirements at degree granting institutions only.  Not for
// government, commercial, or other organizational use.
//
// BubbleCenterAndSizeByCircle_data.cpp
//
// Code generation for function 'BubbleCenterAndSizeByCircle_data'
//

// Include files
#include <mutex>
#include <cstdlib>
#include <omp.h>

#include "BubbleCenterAndSizeByCircle_data.h"
#include "rt_nonfinite.h"

// Variable Definitions
omp_nest_lock_t emlrtNestLockGlobal;

static std::once_flag emlrtOnce;

void emlrtLockInitOnce() {
    std::call_once(emlrtOnce, []{
        omp_init_nest_lock(&emlrtNestLockGlobal);
        std::atexit([]{
            omp_destroy_nest_lock(&emlrtNestLockGlobal);  // 只销毁一次
        });
    });
}

// End of code generation (BubbleCenterAndSizeByCircle_data.cpp)
