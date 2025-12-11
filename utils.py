import os
import sys
from PIL import Image, ImageDraw
import numpy as np
import cv2
import re
import json
import math

def pil_to_opencv(pil_img):
    """
    Convert a PIL Image to an OpenCV image (NumPy array).
    Handles RGB, RGBA, and L (grayscale).
    """
    # Ensure it's a PIL Image object
    if not isinstance(pil_img, Image.Image):
        raise TypeError("Input must be a PIL Image.")

    # Convert to NumPy
    np_img = np.array(pil_img)

    # Handle different PIL modes
    if pil_img.mode == "RGB":
        # PIL (RGB) -> OpenCV (BGR)
        return cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)
    elif pil_img.mode == "RGBA":
        # PIL (RGBA) -> OpenCV (BGRA)
        return cv2.cvtColor(np_img, cv2.COLOR_RGBA2BGRA)
    elif pil_img.mode == "L":
        # PIL (grayscale) just becomes 2D array, no color channel swap needed
        return np_img
    else:
        # Fallback: convert PIL to RGB first
        rgb_img = pil_img.convert("RGB")
        np_img = np.array(rgb_img)
        return cv2.cvtColor(np_img, cv2.COLOR_RGB2BGR)

def opencv_to_pil(cv_img):
    """
    Convert an OpenCV image (NumPy array, BGR/BGRA/Gray) back to a PIL Image.
    """
    if not isinstance(cv_img, np.ndarray):
        raise TypeError("Input must be a NumPy array (OpenCV image).")

    # Check shape to figure out color space
    if len(cv_img.shape) == 2:
        # Grayscale
        return Image.fromarray(cv_img)
    elif len(cv_img.shape) == 3:
        channels = cv_img.shape[2]
        if channels == 3:
            # OpenCV (BGR) -> PIL (RGB)
            return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
        elif channels == 4:
            # OpenCV (BGRA) -> PIL (RGBA)
            return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGRA2RGBA))
    
    # Fallback: Convert to RGB
    return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))

def set_zero_outside_mask(image, mask):
    """Sets pixel values outside the mask to 0."""

    # Ensure image and mask have compatible shapes
    if image.shape[:2] != mask.shape:
        raise ValueError("Image and mask must have the same height and width.")

    # Create a copy of the image to avoid modifying the original
    masked_image = image.copy()

    # Set values outside mask to 0
    masked_image[~mask] = 255

    return masked_image


def polygon_orientation(points):
    """
    Computes the orientation (in degrees) of a polygon via PCA on its vertices.

    :param points: N x 2 numpy array of (x, y) polygon vertices
    :return: Angle in degrees in the range (-180, +180]
    """
    # 1. Compute centroid
    centroid = np.mean(points, axis=0)

    # 2. Shift polygon to the origin based on centroid
    shifted = points - centroid

    # 3. Perform PCA: compute covariance, eigenvalues, eigenvectors
    cov = np.cov(shifted.T)
    eigvals, eigvecs = np.linalg.eig(cov)

    # The principal axis corresponds to the eigenvector with the largest eigenvalue
    principal_axis = eigvecs[:, np.argmax(eigvals)]

    # 4. Compute the angle with respect to the x-axis
    angle = np.arctan2(principal_axis[1], principal_axis[0])

    # Convert from radians to degrees
    angle_deg = np.degrees(angle)

    # For a more standard orientation in [-180, 180], you can do:
    if angle_deg > 180:
        angle_deg -= 360
    elif angle_deg <= -180:
        angle_deg += 360

    return angle_deg

def extract_bbox_removing_incomplete(text):
    """
    Parse truncated JSON that looks like an array of objects,
    discard any incomplete final object, and extract bbox_2d arrays.
    """

    # 1) Strip away the initial ```json plus everything before it
    #    and any trailing backticks or text.
    #    This regex grabs everything after ```json until the end,
    #    then removes any trailing ``` if present.
    match = re.search(r'```json\s*(.*)', text, re.DOTALL)
    if not match:
        return None
    json_str = match.group(1)
    # Remove any trailing triple backticks and beyond
    json_str = re.sub(r'```.*$', '', json_str, flags=re.DOTALL).strip()

    # 2) If the entire thing is wrapped in [...] at the top level, remove them.
    #    We'll parse object by object ourselves.
    #    - We'll do this only if it starts with '[' and ends with ']'.
    if json_str.startswith('[') and json_str.endswith(']'):
        # remove the first '[' and the last ']'
        json_str = json_str[1:-1].strip()

    # 3) Collect each *complete* top-level `{ ... }` object
    #    ignoring any trailing incomplete object.
    objects = []
    brace_stack = 0
    start_idx = None
    for i, ch in enumerate(json_str):
        if ch == '{':
            if brace_stack == 0:
                # Potential start of a new object
                start_idx = i
            brace_stack += 1
        elif ch == '}':
            brace_stack -= 1
            if brace_stack == 0 and start_idx is not None:
                # We found a complete object from start_idx to i
                obj_str = json_str[start_idx:i+1]
                objects.append(obj_str)
                start_idx = None

    # Now `objects` holds each fully closed `{...}`

    # 4) Build a valid JSON array from these objects
    #    For example: [{...},{...},...]
    if not objects:
        return None  # No complete objects found
    array_str = "[" + ",".join(objects) + "]"

    # 5) Parse the array
    try:
        data_list = json.loads(array_str)
    except json.JSONDecodeError:
        return None  # Something else is malformed

    return data_list

def rotated_bbox_polygon(bbox_rot, angle, orig_size, rot_size):
    """
    Convert a bounding box from rotated image coordinates to the original image coordinates as a polygon.

    Parameters:
    - bbox_rot: tuple (x1, y1, x2, y2) representing the bounding box on the rotated image.
    - angle: rotation angle in degrees (same as used in Image.rotate).
    - orig_size: (width, height) of the original image.
    - rot_size: (width, height) of the rotated image.

    Returns:
    - A list of four (x, y) tuples corresponding to the transformed corners in the original image.
    """
    # Convert angle to radians
    angle_rad = math.radians(angle)

    # Original image center
    w, h = orig_size
    cx, cy = w / 2, h / 2

    # Rotated image center
    new_w, new_h = rot_size
    new_cx, new_cy = new_w / 2, new_h / 2

    # Unpack bounding box in rotated image
    x1, y1, x2, y2 = bbox_rot
    # Define the four corners of the bounding box
    corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    transformed_corners = []

    for (x_r, y_r) in corners:
        # Shift the point so the rotated image's center is at the origin
        x_dash = x_r - new_cx
        y_dash = y_r - new_cy

        # Apply the inverse rotation (rotating back by the same angle)
        x_orig = x_dash * math.cos(angle_rad) + y_dash * math.sin(angle_rad) + cx
        y_orig = -x_dash * math.sin(angle_rad) + y_dash * math.cos(angle_rad) + cy
        transformed_corners.append((x_orig, y_orig))

    return transformed_corners
