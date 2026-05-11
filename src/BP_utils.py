# Copyright 2026 David Vázquez-Padín
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
====================================================================
Apple's Synthetic Defocus Noise Pattern (BP Utils)
====================================================================

Author:
    David Vázquez-Padín
    atlanTTic, Universidade de Vigo

Contact:
    dvazquez@gts.uvigo.es

Description:
    Python implementation of the Apple Base Pattern (BP) detection
    and analysis methods presented in the paper:

    D. Vázquez-Padín, F. Pérez-González and P. Pérez-Miguélez,
    "Apple’s Synthetic Defocus Noise Pattern: Characterization and
    Forensic Applications," in IEEE Transactions on Information
    Forensics and Security, vol. 21, pp. 1096-1111, 2026,
    doi: 10.1109/TIFS.2026.3653213.

====================================================================
"""
import numpy as np
import cv2
from skimage.util import view_as_blocks
from scipy.io import loadmat
from pathlib import Path
from typing import Dict, List
from PIL import Image
import pillow_heif
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable

# enable HEIC support in PIL
pillow_heif.register_heif_opener()

def block_corrcoef(arr, block_size=(21, 21)):

    # Extract image dimensions and number of channels
    h, w, _ = arr.shape

    # Block height and width
    bh, bw = block_size

    # Block height and width
    H, W = h // bh, w // bw

    # Split image into non-overlapping blocks
    # Each block contains 2 channels (pattern and reference)
    blocks = np.squeeze(view_as_blocks(arr, block_shape=(bh, bw, 2)))  # shape: (H, W, bh, bw, 2)

    # Initialize correlation map
    cc = np.zeros((H, W), dtype=float)

    # Loop over blocks
    for i in range(H):
        for j in range(W):
            block = blocks[i, j, :, :, :]  # shape (bh, bw, 2)
            ch1 = block[:, :, 0].ravel()
            ch2 = block[:, :, 1].ravel()

            # Compute Pearson correlation coefficient
            r = np.corrcoef(ch1, ch2)[0, 1]

            cc[i, j] = r

    return cc

def correlation_with_rows(W, P_mat):
    # Flatten W into a vector and convert to float64
    w = W.ravel().astype(np.float64)

    # Convert pattern matrix to float64
    P = P_mat.astype(np.float64)

    # Remove mean from W
    w -= w.mean()
    # Remove mean from each row of P_mat
    P -= P.mean(axis=1, keepdims=True)

    # Normalize W
    w /= np.linalg.norm(w)

    # Normalize each row of P_mat
    P /= np.linalg.norm(P, axis=1, keepdims=True)

    # Compute correlation between W and every row of P_mat
    return P @ w

def build_P_mat_from_mat_folder(path):

    # Convert path to Path object
    path = Path(path)

    # If path is a file, use only that file
    if not path.is_dir():
        files = [path]
    else: # Otherwise list all .mat files in the folder
        files = sorted(list(path.glob('*.mat')))

    # List that will contain vectorized patterns
    rows: List[np.ndarray] = []
    # Metadata describing each row in P_mat
    meta: List[Dict[str, object]] = []

    for fp in files:

        # Load BP from MATLAB file
        data = loadmat(fp)
        BP = data["BP"]

        # Generate the four rotated versions of the BP
        for k in (0, 1, 2, 3):

            # Rotate BP by k*90 degrees
            rot = np.rot90(BP, k=k)

            # Flatten pattern and store as a row
            rows.append(rot.ravel(order="C").astype(np.float32, copy=False))

            # Store metadata
            meta.append(
                {
                    "BP_ref": fp.name,
                    "rotation_k": int(k),
                }
            )

    # Stack all rows into a matrix
    P_mat = np.stack(rows, axis=0)

    return P_mat, meta

def load_image(path):

    # Convert to Path object
    path = Path(path)

    # Extract extension
    ext = path.suffix.lower()

    # Supported image formats
    supported = {".jpg", ".jpeg", ".png", ".heic"}

    # Check if extension is supported
    if ext not in supported:
        raise ValueError(f"Unsupported image format: {ext}")

    # Open image using PIL
    img = Image.open(path)

    # Convert image to grayscale
    img = img.convert("L")

    # Convert to NumPy array
    img_np = np.asarray(img)

    return img_np

def BP_driven_NCC_map(BP, I, block_size=(21, 21), alpha=0.07, b_BP=False):

    # Kernel used for getting residue and smoothing
    kernel_size = 5
    kernel = np.ones((kernel_size, kernel_size), np.float32) / (kernel_size * kernel_size)

    # If comparing two BPs directly
    if b_BP:
        W = I
    else: # Otherwise compute noise residue
        W = np.float64(I) - np.float64(cv2.filter2D(np.float64(I), -1, kernel, cv2.BORDER_REFLECT_101))

    # Stack residue and BP to compute block-wise correlations
    stacked = np.stack((W, BP), axis=-1)  # shape HxWx2

    # Compute correlation coefficient per block
    cc = block_corrcoef(stacked, block_size)

    # Replace NaN correlations by zero
    cc[np.isnan(cc)] = 0

    # Smooth NCC map
    NCCmap = cv2.filter2D(cc, -1, kernel, cv2.BORDER_REFLECT_101)

    # Resize NCCmap to image resolution
    NCCmap = cv2.resize(NCCmap, (I.shape[1], I.shape[0]), interpolation=cv2.INTER_NEAREST)

    # Threshold NCC map to produce the binary mask M^(PRNU)
    Mask = (NCCmap < alpha).astype(int)

    return NCCmap, Mask

def detect_BP(BP_path, path_to_im, beta=0.0072):

    # Build matrix of BP patterns and metadata
    P_mat, meta = build_P_mat_from_mat_folder(BP_path)

    # Convert image path
    im_path = Path(path_to_im)

    # If single image
    if not im_path.is_dir():
        im_files = [im_path]
    else: # Otherwise list all files
        im_files = sorted(list(im_path.glob('*')))

    # Initialize detection metadata output
    meta_det_BP: List[Dict[str, object]] = []

    # Kernel for residue extraction
    kernel_size = 5
    kernel = np.ones((kernel_size, kernel_size), np.float32) / (kernel_size * kernel_size)

    for im_fp in im_files:

        # Load image
        I = load_image(im_fp)

        # Compute residue
        W = np.float64(I) - np.float64(cv2.filter2D(np.float64(I), -1, kernel, cv2.BORDER_REFLECT_101))

        # Compute correlation with all BPs
        rho_mat = correlation_with_rows(W, P_mat)

        # Get maximum correlation
        rho = np.max(rho_mat)

        # Index of best matching BP
        index = np.argmax(rho_mat)

        # Check detection threshold
        if rho > beta:
            print(f"[info]: BP: {meta[index]["BP_ref"]} (rot_index: {meta[index]["rotation_k"]}) in: {im_fp} (rho: {rho:.3f})")
            meta_det_BP.append(
                {
                    "Filename": im_fp,
                    "rho": rho,
                    "BP_ref": meta[index]["BP_ref"],
                    "rotation_k": meta[index]["rotation_k"],
                }
            )
        else:
            print(f"[info]: No BP has been detected in: {im_fp} (rho: {rho:.4f})")
            meta_det_BP.append(
                {
                    "Filename": im_fp,
                    "rho": rho,
                    "BP_ref": None,
                    "rotation_k": None,
                }
            )

    return meta_det_BP

def BP_detection_and_localization_example(BP_path, im_path):

    # Detect BP in the provided images
    meta_det_BP = detect_BP(BP_path, im_path)

    for meta in meta_det_BP:

        # If a BP was detected
        if meta["BP_ref"] is not None:

            # Load corresponding BP
            if not Path(BP_path).is_dir():
                data = loadmat(str(Path(BP_path)))
            else:
                data = loadmat(str(Path(BP_path) / str(meta["BP_ref"])))
            BP = data["BP"]

            # Apply detected rotation
            if meta["rotation_k"] != 0:
                BP = np.rot90(BP, k=int(meta["rotation_k"]))

            # Load image
            I = load_image(str(meta["Filename"]))

            # Compute NCC map
            NCCmap, Mask = BP_driven_NCC_map(BP, I)

            # Plot NCC map
            H, W = I.shape
            max_dim = 10

            # Choose figure size preserving aspect ratio
            if W > H:
                # Horizontal
                figsize = (max_dim, max_dim * (H / W))
            else:
                # Vertical
                figsize = (max_dim * (W / H), max_dim)
            fig, ax = plt.subplots(figsize=figsize)

            # Display image
            ax.imshow(I)

            # Overlay NCC map
            im = ax.imshow(NCCmap, alpha=0.7, extent=(0, W, H, 0))

            # Add colorbar
            divider = make_axes_locatable(ax)
            cax = divider.append_axes("right", size="5%", pad=0.1)
            plt.colorbar(im, cax=cax, label='NCC')

            # Show correlation score
            ax.set_title(f"rho: {meta["rho"]:.3f}")

            ax.set_axis_off()
            plt.show()

    return

def BP_comparison_example(BP1_path, BP2_path, b_flip=False):

    # Load first BP
    data = loadmat(BP1_path)
    BP1 = data["BP"]

    # Load second BP
    data = loadmat(BP2_path)
    BP2 = data["BP"]

    # Flip second BP horizontally (if required)
    if b_flip:
        BP2 = np.fliplr(BP2)

    # Compute NCC map between BPs
    NCCmap, Mask = BP_driven_NCC_map(BP1, BP2, b_BP=True)

    # Plot NCC map
    H, W = BP1.shape
    max_dim = 10
    # Choose figure size preserving aspect ratio
    if W > H:
        # Horizontal
        figsize = (max_dim, max_dim * (H / W))
    else:
        # Vertical
        figsize = (max_dim * (W / H), max_dim)
    fig, ax = plt.subplots(figsize=figsize)

    # Show NCC map
    im = ax.imshow(NCCmap, extent=(0, W, H, 0), interpolation='bicubic')

    # Add colorbar
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.1)
    plt.colorbar(im, cax=cax, label='NCC')

    # Show correlation score
    ax.set_title(f"rho: {np.corrcoef(BP1.flatten(), BP2.flatten())[0, 1]:.3f}")

    ax.set_axis_off()
    plt.show()

    return

if __name__ == "__main__":

    # Example: comparison between two BPs
    BP1_path = "/path/to/BP06_12MP_NL_HEIC.mat"
    BP2_path = "/path/to/BP04_12MP_NL_JPEG.mat"
    BP_comparison_example(BP1_path, BP2_path, b_flip=True)

    # Example: BP detection in an image
    BP_path = "/path/to/BP04_12MP_NL_JPEG.mat"
    im_path = "/path/to/C21/bokeh/01 (6).jpg"
    BP_detection_and_localization_example(BP_path, im_path)