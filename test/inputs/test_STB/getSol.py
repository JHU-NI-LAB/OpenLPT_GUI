#%%
import numpy as np
import cv2
from scipy.io import loadmat
import matplotlib.pyplot as plt
import getTiffImg
import os

# %%
ncam = 4

camcalibErrList = []
posecalibErrList = []
imgSizeList = []
camMatList = []
distCoeffList = []
rotVecList = []
rotMatList = []
rotMatInvList = []
transVecList = []
transVecInvList = []

# Load camera parameters
folder = 'camFile/'
for i in range(ncam):
    file = folder + 'cam' + str(i+1) + '.txt'
    with open(file, 'r') as f:
        line_id = 0
        
        lines = f.readlines()[2:]
        
        line_id += 1
        if 'None' in lines[line_id] or 'none' in lines[line_id]:
            camcalibErrList.append(None)
        else:
            camcalibErrList.append(float(lines[line_id]))
        line_id += 2
        if 'None' in lines[line_id] or 'none' in lines[line_id]:
            posecalibErrList.append(None)
        else:
            posecalibErrList.append(float(lines[line_id]))
        
        line_id += 2
        imgSize = np.array(lines[line_id].split(',')).astype(np.int32)
        imgSizeList.append(imgSize)
        
        line_id += 2
        camMat = np.zeros((3,3))
        camMat[0,:] = np.array(lines[line_id].split(',')).astype(np.double)
        camMat[1,:] = np.array(lines[line_id+1].split(',')).astype(np.double)
        camMat[2,:] = np.array(lines[line_id+2].split(',')).astype(np.double)
        camMatList.append(camMat)
        
        line_id += 4
        distCoeff = np.array([lines[line_id].split(',')]).astype(np.double)
        distCoeffList.append(distCoeff)
        
        line_id += 2
        rotVec = np.zeros((3,1))
        rotVec[:,0] = np.array(lines[line_id].split(',')).astype(np.double)
        rotVecList.append(rotVec)
        
        line_id += 2
        rotMat = np.zeros((3,3))
        rotMat[0,:] = np.array(lines[line_id].split(',')).astype(np.double)
        rotMat[1,:] = np.array(lines[line_id+1].split(',')).astype(np.double)
        rotMat[2,:] = np.array(lines[line_id+2].split(',')).astype(np.double)
        rotMatList.append(rotMat)
        
        # rotMatInv
        line_id += 4
        rotMatInv = np.zeros((3,3))
        rotMatInv[0,:] = np.array(lines[line_id].split(',')).astype(np.double)
        rotMatInv[1,:] = np.array(lines[line_id+1].split(',')).astype(np.double)
        rotMatInv[2,:] = np.array(lines[line_id+2].split(',')).astype(np.double)
        rotMatInvList.append(rotMatInv)
        
        line_id += 4
        transVec = np.zeros((3,1))
        transVec[:,0] = np.array(lines[line_id].split(',')).astype(np.double)
        transVecList.append(transVec)
        
        # transVecInv
        line_id += 2
        transVecInv = np.zeros((3,1))
        transVecInv[:,0] = np.array(lines[line_id].split(',')).astype(np.double)
        transVecInvList.append(transVecInv)
   
# %%
# load tracks 
tracks = loadmat("D:\\0.Code\\Test\\SD0075\\particles_75k_100f.mat")['tracks']

print([np.min(tracks[:,3]),np.max(tracks[:,3])])
print([np.min(tracks[:,4]),np.max(tracks[:,4])])

# %%
# check the number of cameras that can be seen for each point 
pts = tracks[:,0:3]
npts = pts.shape[0]
npts_cam = np.zeros(npts, dtype=np.int32)

for i in range(ncam):
    pts_proj = cv2.projectPoints(pts.reshape(npts,1,3), rotVecList[i], transVecList[i], camMatList[i], distCoeffList[i])[0].reshape(npts, 2)

    judge = np.all((pts_proj[:,0] >= 1, pts_proj[:,0] < imgSizeList[i][1]-1, pts_proj[:,1] >= 1, pts_proj[:,1] < imgSizeList[i][0]-1), axis=0)
    
    npts_cam[judge] += 1
    
#%%

    
# %%
ncam = 4
# generate folders
folder = 'D:/0.Code/Test/SD0075/imgFile/'

for i in range(ncam):
    dir = folder+'cam'+str(i+1)+'/'
    if not os.path.exists(dir):
        os.makedirs(dir)

# frame range 
frame_range = [0, 149]

# generate image file names
format_str = 'D:/0.Code/Test/SD0075/imgFile/cam{:d}/img{:05d}.tif\n'
# format_str_python = '../../test/inputs/test_STB/imgFile/cam{:d}/img{:05d}.tif\n'

for i in range(ncam):
    file = folder + 'cam' + str(i+1) + 'ImageNames.txt'
    # file = folder + 'cam' + str(i+1) + 'ImageNames_python.txt'
    
    with open(file, 'w') as f:
        for j in range(frame_range[0], frame_range[1]+1):
            f.write(format_str.format(i+1, j))
            # f.write(format_str_python.format(i+1, j))
        

# generate tiff images
for i in range(frame_range[0], frame_range[1]+1):    
    for j in range(ncam):
        img = getTiffImg.getTiffImg(tracks[tracks[:,3]==i+1,0:3], rotVecList[j], transVecList[j], camMatList[j], distCoeffList[j], imgSizeList[j])

        file = folder + 'cam' + str(j+1) + '/img' + '{:05d}'.format(i) + '.tif'
        cv2.imwrite(file, img)
# %% remove particles that are not visible in all cameras
import os
import numpy as np
import cv2

ncam = 4
folder = 'D:/0.Code/Test/SD0075/imgFile2/'

# 生成文件夹
for i in range(ncam):
    dir_i = os.path.join(folder, f'cam{i+1}')
    os.makedirs(dir_i, exist_ok=True)

# 帧范围
frame_range = [0, 149]

# 生成 image name 列表
format_str = 'D:/0.Code/Test/SD0075/imgFile2/cam{:d}/img{:05d}.tif\n'
for i in range(ncam):
    file = os.path.join(folder, f'cam{i+1}ImageNames.txt')
    with open(file, 'w') as f:
        for j in range(frame_range[0], frame_range[1] + 1):
            f.write(format_str.format(i+1, j))

# ---------------- 可见性过滤函数 ----------------
def filter_visible_in_all_cams(XYZ, rotVecList, transVecList, camMatList, distCoeffList, imgSizeList, border=0):
    """
    仅保留在“所有相机”里都可见(投影在图像范围内，且Zc>0)的3D点。
    XYZ: (N, 3) float, 世界坐标
    imgSizeList[j]: (width, height)
    border: 可选边界留白像素
    """
    if XYZ.size == 0:
        return XYZ

    XYZ = np.asarray(XYZ, dtype=np.float32).reshape(-1, 3)

    # 先把所有点设为可见
    visible_mask = np.ones(len(XYZ), dtype=bool)

    # 逐相机检查
    for j in range(len(rotVecList)):
        rvec = np.asarray(rotVecList[j], dtype=np.float32).reshape(3, 1)
        tvec = np.asarray(transVecList[j], dtype=np.float32).reshape(3, 1)
        K    = np.asarray(camMatList[j],  dtype=np.float32).reshape(3, 3)
        dist = np.asarray(distCoeffList[j], dtype=np.float32).reshape(-1, 1) if distCoeffList[j] is not None else None

        # 1) Zc>0 检查（点需在相机前方）
        R, _ = cv2.Rodrigues(rvec)
        Xc = (R @ XYZ.T) + tvec  # (3, N)
        Zc = Xc[2, :]
        front = Zc > 0

        # 2) 投影并检查是否在图像范围内
        #   OpenCV 的 projectPoints 支持畸变系数，为保持与成像一致性，直接用它
        imgpts, _ = cv2.projectPoints(XYZ, rvec, tvec, K, dist)
        uv = imgpts.reshape(-1, 2)  # (N, 2)
        w, h = imgSizeList[j]  # 注意：这里假设 imgSize=(width, height)

        inside = (
            (uv[:, 0] >= border) & (uv[:, 0] < (w - border)) &
            (uv[:, 1] >= border) & (uv[:, 1] < (h - border))
        )

        # 3) 合并条件
        visible_mask &= (front & inside)

        # 短路：若已经没有点可见，直接返回空
        if not np.any(visible_mask):
            return XYZ[:0]

    return XYZ[visible_mask]

# ---------------- 生成合成图 ----------------
for i in range(frame_range[0], frame_range[1] + 1):
    # 这里保持你原有的“tracks[:,3] 是 1-based 帧号”的用法：i+1
    pts_frame = tracks[tracks[:, 3] == (i + 1), 0:3]  # shape: (N, 3)

    # 过滤出在所有相机都可见的点
    pts_visible = filter_visible_in_all_cams(
        pts_frame, rotVecList, transVecList, camMatList, distCoeffList, imgSizeList, border=0
    )

    # 若无点可见，也照常生成空图（由 getTiffImg 负责返回全黑或你定义的背景）
    for j in range(ncam):
        img = getTiffImg.getTiffImg(
            pts_visible,                 # 只喂可见点
            rotVecList[j],
            transVecList[j],
            camMatList[j],
            distCoeffList[j],
            imgSizeList[j]
        )
        file = os.path.join(folder, f'cam{j+1}', f'img{i:05d}.tif')
        cv2.imwrite(file, img)
