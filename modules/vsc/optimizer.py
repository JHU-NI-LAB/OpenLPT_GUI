"""
VSC Optimizer using wand_calibration Phase 3 approach.
Uses triangulation error (point-to-ray distance) as cost function.
Single scipy optimization with re-triangulation inside residual function.
Convergence is controlled by scipy's ftol/xtol.
"""
import numpy as np
import cv2
from typing import List, Tuple, Callable, Optional, Dict
from scipy.optimize import least_squares


class VSCOptimizer:
    """
    VSC Optimizer using scipy's TRF method with Huber loss.
    
    Like wand_calibration Phase 3:
    - Single scipy optimization call
    - Re-triangulation happens inside residual function (every function evaluation)
    - Convergence controlled by scipy's ftol/xtol
    
    Parameters per camera:
    - rvec (3), tvec (3) = 6 extrinsic params (always)
    - f (1), cx (1), cy (1) = 3 intrinsic params (always)
    - k1, k2 = 0-2 distortion params (adaptive based on original camera)
    """
    
    def __init__(self, 
                 max_nfev: int = 500,
                 ftol: float = 1e-7,
                 xtol: float = 1e-7,
                 f_scale: float = 1.0):
        """
        Args:
            max_nfev: Maximum number of function evaluations
            ftol: Tolerance for termination by change of cost function
            xtol: Tolerance for termination by change of independent variables
            f_scale: Soft margin for inlier/outlier threshold in Huber loss
        """
        self.max_nfev = max_nfev
        self.ftol = ftol
        self.xtol = xtol
        self.f_scale = f_scale
        self.log_callback: Optional[Callable[[str], None]] = None
        self.n_cam_params = 11  # Max params per camera
    
    def set_log_callback(self, callback: Callable[[str], None]):
        """Set callback for logging messages."""
        self.log_callback = callback
    
    def _log(self, msg: str):
        """Log a message and keep GUI responsive."""
        if self.log_callback:
            self.log_callback(msg)
            # Keep GUI responsive
            try:
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()
            except:
                pass
        else:
            print(msg)
    
    def _count_distortion_params(self, cameras: Dict[int, dict]) -> int:
        """Count non-zero distortion params across all cameras."""
        max_dist = 0
        for cam_params in cameras.values():
            dist = cam_params.get('dist', np.zeros(5))
            if len(dist) > 0 and abs(dist[0]) > 1e-10:
                max_dist = max(max_dist, 1)
            if len(dist) > 1 and abs(dist[1]) > 1e-10:
                max_dist = max(max_dist, 2)
        return max_dist
    
    def optimize_all_cameras(self, 
                             cameras: Dict[int, dict],
                             correspondences: List[dict],
                             img_size: Tuple[int, int]) -> Tuple[Dict[int, dict], dict]:
        """
        Optimize all camera parameters using single scipy call.
        Re-triangulation happens inside residual function.
        
        Args:
            cameras: Dict {cam_idx: cam_params} with K, R, tvec, dist
            correspondences: List of {'pt3d': (x,y,z), '2d_per_cam': {cam_idx: (x,y)}}
            img_size: (height, width) tuple
            
        Returns:
            optimized_cameras: Updated camera parameters dict
            info: dict with optimization info
        """
        n_cams = len(cameras)
        n_pts = len(correspondences)
        cam_indices = sorted(cameras.keys())
        cam_id_map = {ext: i for i, ext in enumerate(cam_indices)}
        
        if n_pts < 10:
            return cameras.copy(), {
                'rmse_before': 0, 'rmse_after': 0, 
                'n_points': n_pts, 'converged': False
            }
        
        # Determine number of distortion params
        self.n_dist = self._count_distortion_params(cameras)
        self._log(f"  Using {self.n_dist} distortion parameter(s)")
        
        # Store data
        self._cam_id_map = cam_id_map
        self._cam_indices = cam_indices
        self._n_cams = n_cams
        self._img_size = img_size
        
        # Build 2D observations: {cam_idx: np.array([x, y])} for each point
        self._observations = [corr['2d_per_cam'] for corr in correspondences]
        
        # [VECTORIZATION] Pre-compute camera-wise observation arrays
        # _cam_obs_map: { internal_cam_idx: (point_indices_array, uv_array) }
        self._cam_obs_map = {}
        
        for i, cam_idx in enumerate(cam_indices):
            indices = []
            uvs = []
            for pt_idx, obs in enumerate(self._observations):
                if cam_idx in obs:
                    indices.append(pt_idx)
                    uvs.append(obs[cam_idx])
            
            if indices:
                self._cam_obs_map[i] = (np.array(indices, dtype=int), np.array(uvs))
        
        # Iterative Re-centering Optimization (Sliding Window)
        # We run the optimization multiple times (e.g. 3 iterations)
        # In each iteration, we re-center the bounds around the CURRENT partial solution.
        # This allows the optimizer to "walk" arbitrarily far from the initial guess,
        # while keeping tight local constraints at each step to maintain stability.
        
        # Initialize parameters from cameras
        x0 = self._cameras_to_params(cameras)
        
        # Single scipy optimization call (Initialization for counter)
        self._nfev_count = 0
        
        # Calculate initial stats
        stats_before = self._compute_both_errors(x0)
        self._log(f"  Initial: TriangErr={stats_before['triang_rmse']:.4f}mm, ProjErr={stats_before['proj_rmse']:.4f}px")
        
        n_outer_iters = 3
        current_x = x0
        
        self._log(f"  Starting Iterative Optimization ({n_outer_iters} stages, 'Relative Constraints')...")
        
        final_result = None
        
        for k in range(n_outer_iters):
             # 1. Update Bounds centered on current_x
             # We need to temporarily construct a 'cameras' dict from current_x to use _build_bounds logic
             # Or modify _build_bounds to accept x. Let's use the helper.
             current_cameras = self._params_to_cameras(current_x, cameras) # cameras structure needed
             lb, ub = self._build_bounds(current_cameras)
             
             self._log(f"  [Iter {k+1}/{n_outer_iters}] Re-centered bounds. Running TRF...")
             
             # 2. Run Optimization Step
             # Re-triangulation happens inside _residuals_with_triangulation
             result = least_squares(
                 self._residuals_with_triangulation,
                 current_x,
                 method='trf',
                 loss='huber',
                 f_scale=self.f_scale,
                 bounds=(lb, ub),
                 max_nfev=self.max_nfev,
                 ftol=self.ftol,
                 xtol=self.xtol,
                 x_scale='jac',
                 verbose=0
             )
             
             current_x = result.x
             final_result = result
             
             # Compute intermediate errors
             stats_intermediate = self._compute_both_errors(current_x)
             self._log(f"  [Iter {k+1}] Result: TriangErr={stats_intermediate['triang_rmse']:.4f}mm, ProjErr={stats_intermediate['proj_rmse']:.4f}px")
             
             # Early stopping if converged (small step?)
             # If update is very small, stop.
             # if result.cost ... (optional)
        
        x_opt = current_x
        result = final_result
        
        # Compute final errors
        stats_after = self._compute_both_errors(x_opt)
        self._log(f"  Final: TriangErr={stats_after['triang_rmse']:.4f}mm, ProjErr={stats_after['proj_rmse']:.4f}px")
        self._log(f"  Converged: {result.success}, nfev={result.nfev}, message={result.message}")
        
        # Build optimized cameras
        optimized = self._params_to_cameras(x_opt, cameras)
        
        return optimized, {
            'triang_before': stats_before['triang_rmse'],
            'triang_after': stats_after['triang_rmse'],
            'proj_before': stats_before['proj_rmse'],
            'proj_after': stats_after['proj_rmse'],
            'n_points': n_pts,
            'converged': result.success,
            'n_cams': n_cams,
            'nfev': result.nfev,
            'full_stats': stats_after 
        }
    
    def _cameras_to_params(self, cameras: Dict[int, dict]) -> np.ndarray:
        """Convert camera dict to flat parameter vector."""
        x = []
        for cam_idx in self._cam_indices:
            cam = cameras[cam_idx]
            K = cam['K']
            R = cam['R']
            tvec = cam['tvec']
            dist = cam.get('dist', np.zeros(5))
            
            rvec, _ = cv2.Rodrigues(R)
            rvec = rvec.flatten()
            
            f = K[0, 0]
            cx, cy = K[0, 2], K[1, 2]
            k1 = dist[0] if len(dist) > 0 else 0.0
            k2 = dist[1] if len(dist) > 1 else 0.0
            
            x.extend([rvec[0], rvec[1], rvec[2], 
                     tvec[0], tvec[1], tvec[2],
                     f, cx, cy, k1, k2])
        return np.array(x)
    
    def _params_to_cameras(self, x: np.ndarray, cameras: Dict[int, dict]) -> Dict[int, dict]:
        """Convert flat parameter vector back to camera dict."""
        result = {}
        for i, cam_idx in enumerate(self._cam_indices):
            base = i * self.n_cam_params
            cp = x[base:base + self.n_cam_params]
            
            rvec = cp[0:3]
            tvec = cp[3:6]
            f, cx, cy = cp[6], cp[7], cp[8]
            k1, k2 = cp[9], cp[10]
            
            R, _ = cv2.Rodrigues(rvec)
            K = np.array([[f, 0, cx], [0, f, cy], [0, 0, 1]], dtype=np.float64)
            dist = np.array([k1, k2, 0, 0, 0], dtype=np.float64)
            
            result[cam_idx] = cameras[cam_idx].copy()
            result[cam_idx]['K'] = K
            result[cam_idx]['R'] = R
            result[cam_idx]['R_inv'] = R.T
            result[cam_idx]['tvec'] = tvec
            result[cam_idx]['tvec_inv'] = (-R.T @ tvec.reshape(3, 1)).flatten()
            result[cam_idx]['rvec'] = rvec
            result[cam_idx]['dist'] = dist
        return result
    
    def _build_bounds(self, cameras: Dict[int, dict]) -> Tuple[np.ndarray, np.ndarray]:
        """Build lower and upper bounds for optimization."""
        lb = []
        ub = []
        
        for cam_idx in self._cam_indices:
            cam = cameras[cam_idx]
            K = cam['K']
            R = cam['R']
            tvec = cam['tvec']
            dist = cam.get('dist', np.zeros(5))
            
            rvec, _ = cv2.Rodrigues(R)
            rvec = rvec.flatten()
            
            f = K[0, 0]
            cx, cy = K[0, 2], K[1, 2]
            k1 = dist[0] if len(dist) > 0 else 0.0
            k2 = dist[1] if len(dist) > 1 else 0.0
            
            # Tighter bounds for VSC Refinement (as requested)
            # Regularization prevents parameters from drifting too far from initial calibration
            
            lb.extend([
                rvec[0] - 0.1, rvec[1] - 0.1, rvec[2] - 0.1,
                tvec[0] - 50.0, tvec[1] - 50.0, tvec[2] - 50.0,
                f * 0.95, cx - 50.0, cy - 50.0,
                k1 - max(0.1, abs(k1) * 0.5) if self.n_dist >= 1 else k1 - 1e-10,
                k2 - max(0.1, abs(k2) * 0.5) if self.n_dist >= 2 else k2 - 1e-10
            ])
            ub.extend([
                rvec[0] + 0.1, rvec[1] + 0.1, rvec[2] + 0.1,
                tvec[0] + 50.0, tvec[1] + 50.0, tvec[2] + 50.0,
                f * 1.05, cx + 50.0, cy + 50.0,
                k1 + max(0.1, abs(k1) * 0.5) if self.n_dist >= 1 else k1 + 1e-10,
                k2 + max(0.1, abs(k2) * 0.5) if self.n_dist >= 2 else k2 + 1e-10
            ])
        
        return np.array(lb), np.array(ub)
    
    def _residuals_with_triangulation(self, x: np.ndarray) -> np.ndarray:
        """
        Compute triangulation error residuals.
        Re-triangulates 3D points from current camera params each call.
        
        Optimized: batch triangulate all points first, then per-camera vectorized.
        """
        self._nfev_count += 1
        
        # Parse camera params
        cam_params_list = self._parse_camera_params(x)
        
        # STEP 1: Batch Triangulation (Vectorized)
        # Instead of looping over points (slow), we build A^T A by looping over cameras (fast)
        # Solve A_i X = 0 for each point i using min eigenvector of Sum(A_ij^T A_ij)
        
        n_pts = len(self._observations)
        ATA = np.zeros((n_pts, 4, 4), dtype=np.float64)
        valid_mask = np.zeros(n_pts, dtype=bool)
        
        for i, cp in enumerate(cam_params_list):
            if i not in self._cam_obs_map:
                continue
            
            # P matrix (3x4)
            P = cp['K'] @ np.hstack([cp['R'], cp['tvec'].reshape(3, 1)])
            
            # Get observations for this camera
            pt_indices, uvs = self._cam_obs_map[i]
            n_obs = len(pt_indices)
            
            # Mark these points as seen
            # valid_mask[pt_indices] = True # Wait, need at least 2 cams
            # Implementation hint: Just accumulate. 
            
            # uP3 - P1, vP3 - P2
            # Rows r1, r2 size (N, 4)
            u = uvs[:, 0:1]
            v = uvs[:, 1:2]
            
            r1 = u * P[2:3, :] - P[0:1, :]
            r2 = v * P[2:3, :] - P[1:2, :]
            
            # Add r1^T r1 + r2^T r2 to ATA
            # (N, 4, 1) @ (N, 1, 4) -> (N, 4, 4)
            ATA[pt_indices] += (r1[:, :, None] @ r1[:, None, :]) + (r2[:, :, None] @ r2[:, None, :])

        # Solve eigen system for all points at once
        # Select valid points (seen by >= 2 cameras)
        # To check this efficiently, we could count obs during accumulation or assume input is filtered.
        # Assuming correspondences are valid (>=2 cams).
        
        # Batch Eigendecomposition on 4x4 matrices
        # np.linalg.eigh supports stacked matrices
        w, v = np.linalg.eigh(ATA)
        
        # Min eigenvector (corresponding to smallest eigenvalue) is the last column (sorted ascending)
        # But wait, eigh returns eigenvalues in ascending order.
        # So v[:, :, 0] is min eigenvector? Yes.
        X = v[:, :, 0] 
        
        # De-homogenize
        pts_3d = X[:, :3] / X[:, 3:4]
        
        # STEP 2: Calculate Residuals (Vectorized)
        residuals_list = []
        
        for i, cp in enumerate(cam_params_list):
            if i not in self._cam_obs_map:
                continue
                
            pt_indices, pts_2d = self._cam_obs_map[i]
            
            # Select 3D points
            pts_3d_cam = pts_3d[pt_indices]
            
            # --- Triangulation Residuals (Point-to-Ray) ---
            # Undistort
            pts_2d_undist = cv2.undistortPoints(
                pts_2d.reshape(-1, 1, 2), cp['K'], cp['dist']
            ).reshape(-1, 2)
            
            # Rays in camera frame
            rays_cam = np.column_stack([
                pts_2d_undist, np.ones(len(pts_2d_undist))
            ])
            rays_cam /= np.linalg.norm(rays_cam, axis=1, keepdims=True)
            
            # Rays in world frame
            rays_world = (cp['R_inv'] @ rays_cam.T).T
            
            # Vector v (point to cam center)
            v_vec = pts_3d_cam - cp['C']
            
            # Project v onto ray: |proj| = v . ray
            proj_len = np.sum(v_vec * rays_world, axis=1, keepdims=True)
            perp_vec = v_vec - proj_len * rays_world
            dist_sq = np.sum(perp_vec**2, axis=1) # Squared distance
            
            residuals_list.append(np.sqrt(dist_sq))
            
            # --- Reprojection Residuals (Pixel Distance) ---
            projected, _ = cv2.projectPoints(
                pts_3d_cam.reshape(-1, 1, 3), 
                cp['rvec'], cp['tvec'], 
                cp['K'], cp['dist']
            )
            projected = projected.reshape(-1, 2)
            
            reproj_diffs = (projected - pts_2d).ravel()
            residuals_list.append(reproj_diffs)

        # Concatenate
        if residuals_list:
            residuals = np.concatenate(residuals_list)
        else:
            residuals = np.array([])
        
        # Log progress every 20 function evaluations
        if self._nfev_count % 20 == 0 and len(residuals) > 0:
            # Note: residuals now contain both types, so simple mean is mixed metric
            # Just calculating separate metrics for display
            triang_rmse = np.sqrt(np.mean(np.array(dists)**2)) if 'dists' in locals() else 0.0 # Approximate
            # Use proper helper for display
            stats = self._compute_both_errors(x) # Call helper for accurate stats
            self._log(f"    nfev={self._nfev_count}: TriangErr={stats['triang_rmse']:.4f}mm, ProjErr={stats['proj_rmse']:.4f}px")
        
        return residuals
    
    def _parse_camera_params(self, x: np.ndarray) -> List[dict]:
        """Parse flat param vector into list of camera param dicts."""
        cam_params_list = []
        for i in range(self._n_cams):
            base = i * self.n_cam_params
            cp = x[base:base + self.n_cam_params]
            
            rvec = cp[0:3]
            tvec = cp[3:6]
            f, cx, cy = cp[6], cp[7], cp[8]
            k1 = cp[9] if self.n_dist >= 1 else 0.0
            k2 = cp[10] if self.n_dist >= 2 else 0.0
            
            K = np.array([[f, 0, cx], [0, f, cy], [0, 0, 1]], dtype=np.float64)
            dist = np.array([k1, k2, 0, 0, 0], dtype=np.float64)
            R, _ = cv2.Rodrigues(rvec)
            R_inv = R.T
            C = (-R_inv @ tvec.reshape(3, 1)).flatten()
            
            cam_params_list.append({
                'K': K, 'dist': dist, 'R': R, 'R_inv': R_inv, 
                'tvec': tvec, 'rvec': rvec, 'C': C
            })
        return cam_params_list
    
    def _compute_both_errors(self, x: np.ndarray) -> Tuple[float, float]:
        """Compute both triangulation and reprojection RMSE using vectorized logic."""
        # Use residuals function which calculates all individual errors
        # Note: residuals array contains [triang_errors..., reproj_errors_x..., reproj_errors_y...]
        # But extracting them is tricky because lengths vary per camera.
        # So we just re-implement the vectorized logic for separation.
        
        cam_params_list = self._parse_camera_params(x)
        n_pts = len(self._observations)
        ATA = np.zeros((n_pts, 4, 4), dtype=np.float64)
        
        # Batch Triangulation
        for i, cp in enumerate(cam_params_list):
            if i not in self._cam_obs_map: continue
            
            P = cp['K'] @ np.hstack([cp['R'], cp['tvec'].reshape(3, 1)])
            pt_indices, uvs = self._cam_obs_map[i]
            
            u, v = uvs[:, 0:1], uvs[:, 1:2]
            r1 = u * P[2:3, :] - P[0:1, :]
            r2 = v * P[2:3, :] - P[1:2, :]
            ATA[pt_indices] += (r1[:, :, None] @ r1[:, None, :]) + (r2[:, :, None] @ r2[:, None, :])

        w, v = np.linalg.eigh(ATA)
        X = v[:, :, 0]
        pts_3d = X[:, :3] / X[:, 3:4] # (N, 3)
        
        triang_errors_sq = []
        proj_errors_sq = []
        
        for i, cp in enumerate(cam_params_list):
            if i not in self._cam_obs_map: continue
            pt_indices, pts_2d = self._cam_obs_map[i]
            pts_3d_cam = pts_3d[pt_indices]
            
            # Triangulation Error
            pts_2d_undist = cv2.undistortPoints(
                pts_2d.reshape(-1, 1, 2), cp['K'], cp['dist']
            ).reshape(-1, 2)
            rays_cam = np.column_stack([pts_2d_undist, np.ones(len(pts_2d_undist))])
            rays_cam /= np.linalg.norm(rays_cam, axis=1, keepdims=True)
            rays_world = (cp['R_inv'] @ rays_cam.T).T
            
            v_vec = pts_3d_cam - cp['C']
            proj_len = np.sum(v_vec * rays_world, axis=1, keepdims=True)
            perp_vec = v_vec - proj_len * rays_world
            dist_sq = np.sum(perp_vec**2, axis=1)
            triang_errors_sq.append(dist_sq)
            
            # Reprojection Error
            projected, _ = cv2.projectPoints(
                pts_3d_cam.reshape(-1, 1, 3), cp['rvec'], cp['tvec'], cp['K'], cp['dist']
            )
            projected = projected.reshape(-1, 2)
            diffs = projected - pts_2d
            proj_errors_sq.append(np.sum(diffs**2, axis=1))

        # Flatten
        t_err = np.concatenate(triang_errors_sq) if triang_errors_sq else np.array([])
        p_err = np.concatenate(proj_errors_sq) if proj_errors_sq else np.array([])
        
        # Calculate stats
        stats = {}
        
        # Triangulation (units: mm^2 -> sqrt -> mm)
        if len(t_err) > 0:
            dists = np.sqrt(t_err)
            stats['triang_rmse'] = np.sqrt(np.mean(t_err))
            stats['triang_mean'] = np.mean(dists)
            stats['triang_std'] = np.std(dists)
            stats['triang_max'] = np.max(dists)
            stats['triang_tol'] = stats['triang_mean'] + 3 * stats['triang_std']
        else:
            stats.update({'triang_rmse': 0.0, 'triang_mean': 0.0, 'triang_std': 0.0, 'triang_tol': 0.0})

        # Reprojection (units: px^2 -> sqrt -> px)
        if len(p_err) > 0:
            dists = np.sqrt(p_err)
            stats['proj_rmse'] = np.sqrt(np.mean(p_err))
            stats['proj_mean'] = np.mean(dists)
            stats['proj_std'] = np.std(dists)
            stats['proj_max'] = np.max(dists)
            stats['proj_tol'] = stats['proj_mean'] + 3 * stats['proj_std']
        else:
            stats.update({'proj_rmse': 0.0, 'proj_mean': 0.0, 'proj_std': 0.0, 'proj_tol': 0.0})
            
        return stats

    # Helper method removed
    def _compute_reprojection_rmse_fast(self, cam_params_list, triangulated_pts):
         return 0.0
    
    # Legacy method for backward compatibility
    def optimize_camera(self, 
                        cam_params: dict,
                        points_3d: np.ndarray,
                        points_2d: np.ndarray) -> Tuple[dict, dict]:
        """Legacy single camera optimization (kept for backward compatibility)."""
        n_pts = len(points_3d)
        if n_pts < 10:
            return cam_params.copy(), {
                'rmse_before': 0, 'rmse_after': 0, 
                'n_points': n_pts, 'converged': False
            }
        
        self._log("  Using legacy single-camera optimization")
        return cam_params.copy(), {
            'rmse_before': 0, 'rmse_after': 0, 
            'n_points': n_pts, 'converged': False
        }
