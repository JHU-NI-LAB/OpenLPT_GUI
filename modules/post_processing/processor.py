
"""
Results Processor - Handles data loading, kinematics calculation, and export.
"""

import os
import csv
import re
import numpy as np
from scipy.io import savemat
from scipy.ndimage import gaussian_filter1d
from scipy.signal import convolve
from PySide6.QtCore import QObject, Signal, QThread

class ResultsProcessor(QObject):
    """
    Handles heavy processing for the Results module:
    - Loading track data
    - Filtering
    - Computing velocity/acceleration
    - Exporting
    """
    # Signals
    data_loaded = Signal(object, object) # track_data (dict of arrays), metadata (dict)
    processing_finished = Signal(object) # processed_data (dict of arrays with v/a)
    export_finished = Signal(bool, str) # success, message
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.raw_data = {} # {id: np.array([[f, x, y, z, r3d...], ...])}
        self.processed_data = {} 
        self.metadata = {"obj_type": "Tracer"}

    def load_data(self, proj_dir):
        """Asynchronous wrapper to load data."""
        self.thread = QThread()
        self.worker = DataLoaderWorker(proj_dir)
        self.worker.moveToThread(self.thread)
        self.worker.finished.connect(self._on_load_finished)
        self.worker.error.connect(self._on_worker_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def _on_load_finished(self, raw_data, metadata):
        self.raw_data = raw_data
        self.metadata = metadata
        self.processed_data = raw_data.copy() # Initially same as raw
        self.data_loaded.emit(self.raw_data, self.metadata)

    def _on_worker_error(self, msg):
        self.error.emit(msg)

    def _find_knee_point(self, x_vals, y_vals):
        """
        Estimate knee/elbow point of a convex decreasing curve (L-curve).
        Uses simple 'distance to diagonal' method (Kneedle concept).
        Assumes x_vals is sorted and y_vals is generally decreasing.
        """
        try:
            if len(x_vals) < 3: return None
            
            x = np.array(x_vals)
            y = np.array(y_vals)
            
            # Normalize to [0, 1]
            x_norm = (x - x.min()) / (x.max() - x.min() + 1e-9)
            y_norm = (y - y.min()) / (y.max() - y.min() + 1e-9)
            
            # Vector from start to end (Diagonal line L)
            # P_start = (0, y_norm[0]) -> This normalization makes y_norm[end]=0 if strictly decreasing, but min is 0.
            # Start point: (x_norm[0], y_norm[0])
            # End point: (x_norm[-1], y_norm[-1])
            
            p1 = np.array([x_norm[0], y_norm[0]])
            p2 = np.array([x_norm[-1], y_norm[-1]])
            
            vec_line = p2 - p1
            
            # For each point P, distance to line implies finding height of triangle or perpendicular dist.
            # Simplified: Curve of (y_norm - line_y).
            # Line equation y = mx + c
            if (p2[0] - p1[0]) == 0: return None
            
            m = (p2[1] - p1[1]) / (p2[0] - p1[0])
            c = p1[1] - m * p1[0]
            
            y_line = m * x_norm + c
            
            # The 'knee' is where the curve is furthest *below* the line (convex)
            # or furthest *from* the line.
            # Since our curve drops sharply (concave up usually), we look for max distance below the chord P1-P2.
            dist_curve = y_line - y_norm
            
            idx_max = np.argmax(dist_curve)
            
            return x_vals[idx_max]

        except:
            return None

    def get_comparison_data(self, width, acc_width, fps):
        """
        Get Raw vs Filtered comparisons for Position, Velocity, and Acceleration.
        Returns data for the longest track.
        """
        if not self.raw_data: return {}
        
        # Get longest track
        track = max(self.raw_data.values(), key=len)
        track = track[np.argsort(track[:, 0])] # Sort by frame
        
        coords = track[:, 1:4]
        dt = 1.0 / max(1e-6, fps)
        
        # 1. Raw Kinematics (Finite Difference)
        vel_raw = np.gradient(coords, axis=0) / dt
        acc_raw = np.gradient(vel_raw, axis=0) / dt
        
        vel_raw_mag = np.linalg.norm(vel_raw, axis=1)
        acc_raw_mag = np.linalg.norm(acc_raw, axis=1)
        
        # 2. Filtered Kinematics
        # We need kernels for the specific requested widths
        # Helper to gen kernel (duplicated logic, should refactor but fine for now)
        def get_k(w, is_acc=False):
            if w <= 0: return None, 0
            fw = int(np.ceil(3 * w))
            if is_acc:
                rwsq = 1.0 / (w**2)
                coef = 2 * rwsq / (np.sqrt(np.pi) * w)
                fitl = np.arange(-fw, fw + 1)
                t1 = 2 * fitl**2 * rwsq - 1
                t2 = np.exp(fitl**2 * rwsq)
                sk = np.sum(coef * t1 / t2)
                sktsq = np.sum(fitl**2 * coef * t1 / t2)
                stsq = np.sum(fitl**2)
                A = 2 / (sktsq - sk * stsq / (2 * fw))
                B = -A * sk / (2 * fw + 1) # FIXED
                kern = A * coef * t1 / t2 + B
                return kern, fw
            else:
                # Vel
                vals = np.arange(-fw, fw + 1)
                pos = np.arange(1, fw + 1)
                ds = np.sum((pos**2) * np.exp(-pos**2 / w**2))
                Av = 1.0 / (2 * ds)
                kern = Av * vals * np.exp(-vals**2 / w**2)
                
                # Pos (Smoothing)
                fitl_p = np.arange(1, fw + 1)
                ds_p = 2 * np.sum(np.exp(-(fitl_p**2) / (w**2))) + 1
                Av_p = 1.0 / ds_p
                pkern = Av_p * np.exp(-(vals**2) / (w**2))
                
                return kern, pkern, fw

        # Vel/Pos Kernels
        vkern, pkern, fw_pv = get_k(width, is_acc=False)
        # Acc Kernel
        akern, fw_acc = get_k(acc_width, is_acc=True)
        
        # Apply
        # Valid region is max of both cuts
        max_fw = max(fw_pv, fw_acc)
        if len(coords) < 2*max_fw + 1: return {}
        
        pos_filt = np.zeros_like(coords)
        vel_filt = np.zeros_like(coords)
        acc_filt = np.zeros_like(coords)
        
        for d in range(3):
            # Pos
            pos_filt[:,d] = convolve(coords[:, d], pkern, mode='same')
            # Vel
            vel_filt[:,d] = -convolve(coords[:, d], vkern, mode='same') / dt
            # Acc
            acc_filt[:,d] = convolve(coords[:, d], akern, mode='same') / (dt**2)
            
        vel_filt_mag = np.linalg.norm(vel_filt, axis=1)
        acc_filt_mag = np.linalg.norm(acc_filt, axis=1)
        
        # Valid Slices
        sl = slice(max_fw, -max_fw)
        
        return {
            'frames': track[sl, 0],
            'pos_raw': coords[sl],
            'pos_filt': pos_filt[sl],
            'vel_raw': vel_raw_mag[sl],
            'vel_filt': vel_filt_mag[sl],
            'acc_raw': acc_raw_mag[sl],
            'acc_filt': acc_filt_mag[sl]
        }

    def calculate_optimization_curve(self, widths, fps=1.0):
        """
        Compute StdDev of Acc/Vel for a range of filter widths.
        Uses Normalized Averaging over top 20 tracks to be robust against signal differences.
        
        Args:
            widths (list/array): List of sigma values to test.
            fps (float): Frames per second.
            
        Returns:
            dict: {'vel': (widths, stds, optimal_w), 'acc': (widths, stds, optimal_w)}
        """
        # 1. Select Sample Tracks (Top 20 longest)
        if not self.raw_data:
            raise ValueError("No data loaded.")
            
        sorted_tracks = sorted(self.raw_data.values(), key=len, reverse=True)
        sample_tracks = sorted_tracks[:20]
        
        # Pre-sort by frame
        sample_tracks = [t[np.argsort(t[:, 0])] for t in sample_tracks]
        
        dt = 1.0 / max(1e-6, fps)
        
        # Store individual curves to average later
        # distinct tracks -> distinct curves
        all_vel_curves = []
        all_acc_curves = []
        
        # We need to process each track individually for the normalization strategy
        # But for efficiency, we can iterate widths outside, and accumulate sums?
        # Actually it's cleaner to iterate tracks outside if we want per-track curves.
        # But convolution is faster per track if we pre-gen kernels...
        # Let's keep distinct curves logic.
        
        # Initialize
        n_widths = len(widths)
        final_widths = []
        
        # Pre-calculate kernels for all widths to save overhead
        kernels = []
        for w in widths:
            if w <= 0.1: 
                kernels.append(None)
                continue
            
            final_widths.append(w)
            fw = int(np.ceil(3 * w))
            
            # Acc Kernel
            rwsq = 1.0 / (w**2)
            coef = 2 * rwsq / (np.sqrt(np.pi) * w)
            fitl_acc = np.arange(-fw, fw + 1)
            term1 = 2 * fitl_acc**2 * rwsq - 1
            term2 = np.exp(fitl_acc**2 * rwsq)
            sumtsq = np.sum(fitl_acc**2)
            sumk = np.sum(coef * term1 / term2)
            sumktsq = np.sum(fitl_acc**2 * coef * term1 / term2)
            A_val = 2 / (sumktsq - sumk * sumtsq / (2 * fw))
            B_val = -A_val * sumk / (2 * fw)
            akernel = A_val * coef * term1 / term2 + B_val
            
            # Vel Kernel
            fitl_vel = np.arange(-fw, fw + 1)
            fitl_pos = np.arange(1, fw + 1)
            denom_sum = np.sum((fitl_pos**2) * np.exp(-fitl_pos**2 / w**2))
            Av = 1.0 / (2 * denom_sum)
            vkernel = Av * fitl_vel * np.exp(-fitl_vel**2 / w**2)
            
            kernels.append((w, fw, vkernel, akernel))

        # Iterate over tracks
        for track in sample_tracks:
            coords = track[:, 1:4]
            track_vel_stds = []
            track_acc_stds = []
            
            valid_track = True
            
            for k_data in kernels:
                if k_data is None: continue
                w, fw, vkern, akern = k_data
                
                edge_cut = fw
                required_len = 2 * edge_cut + 1
                
                if len(track) < required_len:
                    # If this track is too short for *this* width, we can't compute this point.
                    # This breaks the "curve" shape. 
                    # Simpler strategy: Only use tracks that are long enough for the MAX width.
                    # But we selected top 20, they are likely very long.
                    track_vel_stds.append(np.nan)
                    track_acc_stds.append(np.nan)
                    continue
                
                curr_vels = []
                curr_accs = []
                
                for d in range(3):
                    col = coords[:, d]
                    # Vel
                    v = -convolve(col, vkern, mode='same') / dt
                    curr_vels.extend(v[edge_cut:-edge_cut])
                    # Acc
                    a = convolve(col, akern, mode='same') / (dt**2)
                    curr_accs.extend(a[edge_cut:-edge_cut])
                    
                track_vel_stds.append(np.std(curr_vels) if curr_vels else 0)
                track_acc_stds.append(np.std(curr_accs) if curr_accs else 0)
            
            if len(track_vel_stds) == len(final_widths):
                all_vel_curves.append(track_vel_stds)
                all_acc_curves.append(track_acc_stds)
        
        # Aggregate Curves (Normalized Averaging)
        def aggregate_normalized(curves):
            if not curves: return []
            arr = np.array(curves) # Shape (N_tracks, N_widths)
            
            # Check for NaNs (tracks that failed length check)
            # If a column has NaNs, ignore those tracks for that mean?
            # Or just use nanmean
            
            # Normalize each row by its maximum (or first element) to range [0, 1] relative scale
            # This removes "Magnitude" differences
            row_maxs = np.nanmax(arr, axis=1, keepdims=True)
            row_maxs[row_maxs == 0] = 1.0 # Avoid div/0
            
            norm_arr = arr / row_maxs
            
            # Average the normalized shapes
            mean_curve = np.nanmean(norm_arr, axis=0)
            return mean_curve

        final_vel_stds = aggregate_normalized(all_vel_curves)
        final_acc_stds = aggregate_normalized(all_acc_curves)
        
        # 3. Find Knee Points
        opt_vel = self._find_knee_point(final_widths, final_vel_stds)
        opt_acc = self._find_knee_point(final_widths, final_acc_stds)
        
        return {
            'vel': (final_widths, final_vel_stds, opt_vel), 
            'acc': (final_widths, final_acc_stds, opt_acc)
        }

    def compute_kinematics_and_filter(self, filter_width, acc_filter_width, fps=1.0):
        """
        Vectorized Kinematics Calculation (MATLAB Style).
        
        1. Concatenate all tracks into one large matrix.
        2. Apply Gaussian convolution (Pos/Vel using filter_width, Acc using acc_filter_width).
        3. Remove invalid edge rows (transition zones between tracks).
        4. Re-assemble into dictionary.
        """
        try:
            # --- 1. Constants & Kernels ---
            dt = 1.0 / max(1e-6, fps)
            
            # Widths
            w_pv = filter_width
            w_acc = acc_filter_width
            
            # Fit Widths (3 * sigma)
            # Ensure at least 1 to avoid zero-size arrays if sigma=0, though sigma=0 usually means no filter.
            # If sigma=0, we should probably skip smoothing, but for vectorized code it's easier to use a delta kernel.
            # Let's handle generic case:
            
            pv_fitwidth = int(np.ceil(3 * w_pv)) if w_pv > 0 else 0
            acc_fitwidth = int(np.ceil(3 * w_acc)) if w_acc > 0 else 0
            
            # Combined edge cut for validity (max of required margins)
            # We need to cut edges where the kernel overlaps with neighbor tracks.
            # Max kernel radius is the constraint.
            edge_cut = max(pv_fitwidth, acc_fitwidth)
            
            # Min length requirement: must have at least 1 point AFTER removing edges
            # i.e. Length > 2 * edge_cut
            required_len = 2 * edge_cut + 1
            
            # --- 2. Prepare Data (Concatenation) ---
            # Collect valid tracks (length check first)
            valid_tracks = []
            valid_ids = []
            
            # Helper to extract R3D if present
            has_r3d = False
            
            # Iterate safely
            sorted_ids = sorted(self.raw_data.keys())
            
            for tid in sorted_ids:
                track = self.raw_data[tid]
                
                # Check sufficient length for convolution
                if len(track) < required_len:
                    continue
                
                # Sort by frame
                track = track[np.argsort(track[:, 0])]
                valid_tracks.append(track)
                valid_ids.append(tid)
                
                if not has_r3d and track.shape[1] > 4:
                    has_r3d = True

            if not valid_tracks:
                # No tracks meet the filter length requirement
                self.processed_data = {}
                self.processing_finished.emit({})
                return

            # Concatenate
            # all_data shape: (Total_Points, D)
            all_data = np.vstack(valid_tracks)
            
            # Track ID column construction for reference (optional, but good for debugging)
            # We can rely on track lengths to reconstruct later.
            track_lengths = [len(t) for t in valid_tracks]
            total_points = len(all_data)
            
            coords = all_data[:, 1:4] # X, Y, Z
            
            # --- 3. Kernel Generation ---
            
            # Helper to get kernels
            def get_pv_kernels(sig):
                if sig <= 0:
                    # Delta function for pos, Gradient for vel (central diff 2-point)
                    # For simplicity, if sig=0, we skip conv or use minimal kernel.
                    # fallback to identity for pos, and simple gradient [0.5, 0, -0.5] for vel?
                    # Let's assume sig > 0 check is done before call, or return delta.
                    return np.array([1.0]), np.array([0.5, 0, -0.5]) # Very rough approx for 0 sigma
                
                fw = int(np.ceil(3 * sig))
                
                # Pos Kernel (Normalized Gaussian)
                fitl_p = np.arange(1, fw + 1)
                denom_sum_p = 2 * np.sum(np.exp(-(fitl_p**2) / (sig**2))) + 1
                Av_p = 1.0 / denom_sum_p
                rkernel_idx = np.arange(-fw, fw + 1)
                pkernel = Av_p * np.exp(-(rkernel_idx**2) / (sig**2))
                
                # Vel Kernel (1st Deriv)
                fitl_vel = np.arange(-fw, fw + 1)
                fitl_pos = np.arange(1, fw + 1)
                denom_sum = np.sum((fitl_pos**2) * np.exp(-fitl_pos**2 / sig**2))
                Av = 1.0 / (2 * denom_sum)
                vkernel = Av * fitl_vel * np.exp(-fitl_vel**2 / sig**2)
                
                return pkernel, vkernel

            def get_sf_kernels(sig):
                 # Acceleration Kernel (2nd Deriv)
                 if sig <= 0: return np.array([1, -2, 1]) # Finite diff
                 
                 fw = int(np.ceil(3 * sig))
                 rwsq = 1.0 / (sig**2)
                 coef = 2 * rwsq / (np.sqrt(np.pi) * sig)
                 fitl_acc = np.arange(-fw, fw + 1)
                 
                 term1 = 2 * fitl_acc**2 * rwsq - 1
                 term2 = np.exp(-fitl_acc**2 * rwsq)
                 
                 sumtsq = np.sum(fitl_acc**2)
                 sumk = np.sum(coef * term1 / term2)
                 sumktsq = np.sum(fitl_acc**2 * coef * term1 / term2)
                 
                 A_val = 2 / (sumktsq - sumk * sumtsq / (2 * fw))
                 B_val = -A_val * sumk / (2 * fw)
                 
                 akernel = A_val * coef * term1 / term2 + B_val
                 return akernel

            # Generate
            if w_pv > 0:
                p_kern, v_kern = get_pv_kernels(w_pv)
            else:
                p_kern, v_kern = None, None # Handle 0 case
                
            if w_acc > 0:
                a_kern = get_sf_kernels(w_acc)
            else:
                a_kern = None

            # --- 4. Convolution (Vectorized) ---
            # Pre-allocate
            pos_smooth = np.zeros_like(coords)
            vel = np.zeros_like(coords)
            acc = np.zeros_like(coords)
            
            for d in range(3):
                col = coords[:, d]
                
                # Pos
                if p_kern is not None:
                    pos_smooth[:, d] = convolve(col, p_kern, mode='same')
                else:
                    pos_smooth[:, d] = col
                
                # Vel
                if v_kern is not None:
                    # -conv / dt
                    vel[:, d] = -convolve(col, v_kern, mode='same') / dt
                else:
                    # Fallback Component-wise Gradient
                    vel[:, d] = np.gradient(pos_smooth[:, d]) / dt
                    
                # Acc
                if a_kern is not None:
                    # conv / dt^2
                    acc[:, d] = convolve(col, a_kern, mode='same') / (dt**2)
                else:
                    # Fallback Gradient of Vel
                    acc[:, d] = np.gradient(vel[:, d]) / dt

            # --- 5. Remove 'Transition' Edges ---
            # Logic: For each track, indices [start : start+edge_cut] and [end-edge_cut : end] are invalid.
            # We construct a boolean mask for the whole array.
            
            valid_mask = np.ones(total_points, dtype=bool)
            current_idx = 0
            
            for length in track_lengths:
                start = current_idx
                end = current_idx + length
                
                # Mask Start Edge
                valid_mask[start : start + edge_cut] = False
                # Mask End Edge
                valid_mask[end - edge_cut : end] = False
                
                current_idx += length
            
            # Apply Mask
            final_coords = pos_smooth[valid_mask]
            final_vel = vel[valid_mask]
            final_acc = acc[valid_mask]
            final_frames = all_data[valid_mask, 0:1] # Frame col
            
            final_r3d = None
            final_2d = None
            
            start_2d = 4 # Default after X,Y,Z
            
            if has_r3d:
                final_r3d = all_data[valid_mask, 4:5]
                start_2d = 5
            
            # Check for 2D data (Columns after start_2d)
            if all_data.shape[1] > start_2d:
                final_2d = all_data[valid_mask, start_2d:]
            
            # --- 6. Reconstruct Dictionary ---
            # We need to split the giant arrays back into track dicts.
            # The valid lengths have changed! length -> length - 2*edge_cut
            
            new_data = {}
            current_valid_idx = 0
            
            for i, tid in enumerate(valid_ids):
                orig_len = track_lengths[i]
                new_len = orig_len - 2 * edge_cut
                
                if new_len <= 0: continue # Should be caught by init check but safety first
                
                # Extract slices
                sl = slice(current_valid_idx, current_valid_idx + new_len)
                
                f_slice = final_frames[sl]
                p_slice = final_coords[sl]
                v_slice = final_vel[sl]
                a_slice = final_acc[sl]
                
                # Magnitudes
                v_mag = np.linalg.norm(v_slice, axis=1).reshape(-1, 1)
                a_mag = np.linalg.norm(a_slice, axis=1).reshape(-1, 1)
                
                # Assemble
                # [Frame, X, Y, Z, Vx, Vy, Vz, Vmag, Ax, Ay, Az, Amag, (R3D), (2D...)]
                comps = [f_slice, p_slice, v_slice, v_mag, a_slice, a_mag]
                
                if final_r3d is not None:
                     comps.append(final_r3d[sl])
                
                if final_2d is not None:
                     comps.append(final_2d[sl])
                
                new_data[tid] = np.hstack(comps)
                
                current_valid_idx += new_len

            self.processed_data = new_data
            self.processing_finished.emit(new_data)
            
        except Exception as e:
            self.error.emit(f"Processing failed: {e}")
            import traceback
            traceback.print_exc()

    def save_mat(self, filepath, options=None):
        """
        Export processed data to .mat file as a 2D matrix.
        Options dict keys: 'id', 'frame', 'pos', 'vel', 'acc', 'img2d'
        """
        try:
            if options is None:
                # Default all true
                options = {'id': True, 'frame': True, 'pos': True, 'vel': True, 'acc': True, 'img2d': True}
                
            # Determine Indices based on fixed structure:
            # [0:Frame, 1-3:Pos, 4-6:Vel, 7:Vmag, 8-10:Acc, 11:Amag, 12:R3D(opt), 13+:2D]
            # Standard columns count = 12
            
            # Check for R3D based on Object Type or Data Shape?
            # Data shape is reliable.
            # But we need to know if col 12 is R3D or 2D.
            # We can check metadata object type.
            is_bubble = (self.metadata.get("obj_type") == "Bubble")
            
            all_rows = []
            
            # Helper to generate ID column
            def get_id_col(tid, length):
                return np.full((length, 1), float(tid))

            for tid, data in self.processed_data.items():
                n_pts = len(data)
                cols_to_stack = []
                
                # 1. Track ID
                if options.get('id'):
                    cols_to_stack.append(get_id_col(tid, n_pts))
                
                # 2. Frame ID
                if options.get('frame'):
                    cols_to_stack.append(data[:, 0:1])
                
                # 3. Position (X, Y, Z, +R3D)
                if options.get('pos'):
                    cols_to_stack.append(data[:, 1:4])
                    # Check for R3D (Column 12 if exists and is bubble)
                    # If is_bubble is True, we assume R3D exists if cols > 12?
                    # Actually, let's look at col count.
                    # If columns > 12, col 12 is potentially R3D or 2D start.
                    # OpenLPT usually puts R3D before 2D.
                    if is_bubble and data.shape[1] > 12:
                        cols_to_stack.append(data[:, 12:13])
                
                # 4. Velocity (Vec3D)
                if options.get('vel'):
                    cols_to_stack.append(data[:, 4:7])
                
                # 5. Acceleration (Acc3D)
                if options.get('acc'):
                    cols_to_stack.append(data[:, 8:11])
                
                # 6. Image 2D (+r2D)
                if options.get('img2d'):
                    # Where does 2D start?
                    # Base = 12
                    # If Bubble and we have > 12 cols, 12 is R3D, so 2D starts at 13.
                    # If Tracer, 12 is 2D start.
                    
                    start_2d = 12
                    if is_bubble and data.shape[1] > 12:
                        start_2d = 13
                    
                    if data.shape[1] > start_2d:
                        cols_to_stack.append(data[:, start_2d:])
                
                if cols_to_stack:
                    track_block = np.hstack(cols_to_stack)
                    all_rows.append(track_block)
            
            if not all_rows:
                self.export_finished.emit(False, "No data to export.")
                return

            final_matrix = np.vstack(all_rows)
            
            # Save as 'data' variable
            savemat(filepath, {'data': final_matrix})
            self.export_finished.emit(True, f"Saved matrix to {filepath}")
            
        except Exception as e:
            self.export_finished.emit(False, str(e))


class DataLoaderWorker(QObject):
    """Worker to load CSVs."""
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, proj_dir):
        super().__init__()
        self.proj_dir = proj_dir

    def run(self):
        try:
            config_path = os.path.join(self.proj_dir, "config.txt")
            output_dir = os.path.join(self.proj_dir, "Results") # Default fallback
            obj_type = "Tracer"
            
            # 1. Parse config.txt for Output Path and Object Type
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    lines = f.readlines()
                    for i, line in enumerate(lines):
                        line = line.strip()
                        if "Output Folder Path" in line:
                            # Next line should be the path
                            if i + 1 < len(lines):
                                path_line = lines[i+1].strip()
                                if path_line:
                                    output_dir = path_line
                        elif "Object Types" in line:
                             if i + 1 < len(lines):
                                 type_line = lines[i+1].strip()
                                 if "Bubble" in type_line:
                                     obj_type = "Bubble"
            
            track_dir = os.path.join(output_dir, "ConvergeTrack")
            if not os.path.exists(track_dir):
                # Fallback: Maybe user didn't set output path correctly in config, try default project result
                fallback_dir = os.path.join(self.proj_dir, "Results", "ConvergeTrack")
                if os.path.exists(fallback_dir):
                     track_dir = fallback_dir
                else:
                    self.error.emit(f"ConvergeTrack directory not found at {track_dir} or default.")
                    return

            # Helper for sorting
            def natsort_key(s):
                return [int(text) if text.isdigit() else text.lower()
                        for text in re.split('([0-9]+)', s)]
            
            def get_sorted_csvs(prefix):
                 if not os.path.exists(track_dir): return []
                 files = [f for f in os.listdir(track_dir) if f.startswith(prefix) and f.endswith(".csv")]
                 return sorted(files, key=natsort_key)

            patterns = ["LongTrackActive", "LongTrackInactive", "ExitTrack"]
            raw_data = {}
            max_id_overall = -1

            for pattern in patterns:
                files = get_sorted_csvs(pattern)
                for filename in files:
                    file_path = os.path.join(track_dir, filename)
                    local_max = -1
                    
                    try:
                        file_data = [] # List of tuples (ID, row_data)
                        
                        with open(file_path, 'r', newline='') as f:
                             reader = csv.reader(f)
                             header = next(reader, None) # Skip header
                             if not header: continue
                             
                             for row in reader:
                                 if not row: continue
                                 
                                 try:
                                     orig_id = int(row[0])
                                     frame = int(row[1])
                                     x, y, z = float(row[2]), float(row[3]), float(row[4])
                                     
                                     row_vals = [frame, x, y, z]
                                     
                                     row_vals = [frame, x, y, z]
                                     
                                     # Bubble Radius or Extra Columns (2D projections)
                                     # Start index for extra data:
                                     # if Bubble: index 5 is Radius, 6+ is 2D
                                     # if Tracer: index 5+ is 2D
                                     
                                     start_idx = 5
                                     if obj_type == "Bubble" and len(row) > 5:
                                         row_vals.append(float(row[start_idx])) # Radius
                                         start_idx += 1
                                     
                                     # Append remaining columns (2D projections)
                                     for k in range(start_idx, len(row)):
                                         if row[k]: # Check not empty
                                            row_vals.append(float(row[k]))
                                     
                                     file_data.append((orig_id, row_vals))
                                     
                                     if orig_id > local_max:
                                         local_max = orig_id
                                 except ValueError: continue
                        
                        # Process file_data
                        offset = max_id_overall + 1
                        for orig_id, row_vals in file_data:
                            cum_id = orig_id + offset
                            if cum_id not in raw_data:
                                raw_data[cum_id] = []
                            raw_data[cum_id].append(row_vals)
                            
                        if local_max != -1:
                            max_id_overall += (local_max + 1)
                            
                    except Exception as e:
                        print(f"Skipping file {filename}: {e}")
                        continue

            # Convert lists to numpy arrays
            final_data = {}
            for tid, rows in raw_data.items():
                if not rows: continue
                arr = np.array(rows)
                # Sort by frame
                arr = arr[arr[:, 0].argsort()]
                final_data[tid] = arr

            self.finished.emit(final_data, {"obj_type": obj_type})

        except Exception as e:
            self.error.emit(str(e))
