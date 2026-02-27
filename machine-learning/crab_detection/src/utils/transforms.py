import albumentations as A
import cv2
import numpy as np

def get_crab_transforms():
    """
    Returns the Albumentations transform pipeline for individual crab images.
    Applies geometric augmentations to individual crabs before pasting.
    """
    return A.Compose([
        A.RandomRotate90(p=0.5),
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.5),
        A.Transpose(p=0.5),
        A.Affine(scale=(0.8, 1.2), translate_percent=(0.0, 0.0625), rotate=(-45, 45), p=0.2),
    ])

def get_bg_transforms(height=640, width=640):
    """
    Returns the Albumentations transform pipeline for the final composite image.
    Applies global effects like blur, colour changes, and resizing.
    """
    return A.Compose([
        A.OneOf([
            A.GaussNoise(),
        ], p=0.2),
        A.OneOf([
            A.MotionBlur(p=0.2),
            A.MedianBlur(blur_limit=3, p=0.1),
            A.Blur(blur_limit=3, p=0.1),
        ], p=0.2),
        A.OneOf([
            A.ElasticTransform(p=0.3),
        ], p=0.2),
        A.OneOf([
            A.CLAHE(clip_limit=2),
            A.Sharpen(),
            A.Emboss(),
            A.RandomBrightnessContrast(),
        ], p=0.3),
        A.HueSaturationValue(p=0.3),
        A.Resize(height, width),
    ], bbox_params=A.BboxParams(format='yolo', label_fields=['class_labels']))

def get_val_transforms(height=640, width=640):
    """
    Returns the Albumentations transform pipeline for validation or inference.
    Mainly applies resizing and normalisation.
    """
    return A.Compose([
        A.Resize(height, width),
    ], bbox_params=A.BboxParams(format='yolo', label_fields=['class_labels']))

def apply_copy_paste(background_img, object_img, paste_x=None, paste_y=None):
    """
    Simulates Copy-Paste augmentation by pasting an object onto a background.
    
    Args:
        background_img: The background image (e.g., underwater scene).
        object_img: The object image (e.g., crab).
        paste_x, paste_y: Coordinates to paste top-left corner. Random if None.
        
    Returns:
        augmented_image: Image with object pasted.
        bbox: Bounding box of pasted object [x_center, y_center, width, height] (normalized).
    """
    bg_h, bg_w = background_img.shape[:2]
    obj_h, obj_w = object_img.shape[:2]

    # Resize object if it's too big for background
    if obj_h > bg_h or obj_w > bg_w:
        scale = min(bg_h / obj_h, bg_w / obj_w) * 0.8
        new_w = int(obj_w * scale)
        new_h = int(obj_h * scale)
        object_img = cv2.resize(object_img, (new_w, new_h))
        obj_h, obj_w = object_img.shape[:2]

    # Allow pasting outside bounds (e.g. -50% to +100%)
    # This simulates partial occlusion at edges
    if paste_x is None:
        paste_x = np.random.randint(-int(obj_w * 0.5), bg_w - int(obj_w * 0.2))
    if paste_y is None:
        paste_y = np.random.randint(-int(obj_h * 0.5), bg_h - int(obj_h * 0.2))

    # Calculate intersection between background and object placement
    # Object coords in background frame
    x1, y1 = paste_x, paste_y
    x2, y2 = paste_x + obj_w, paste_y + obj_h
    
    # Background coords
    bg_x1, bg_y1 = 0, 0
    bg_x2, bg_y2 = bg_w, bg_h
    
    # Intersection
    inter_x1 = max(x1, bg_x1)
    inter_y1 = max(y1, bg_y1)
    inter_x2 = min(x2, bg_x2)
    inter_y2 = min(y2, bg_y2)
    
    # Check if any overlap
    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        # No overlap/out of frame entirely - return original
        return background_img, [0, 0, 0, 0]

    # Crop object to fit in background
    # Object slice
    obj_x1 = inter_x1 - x1
    obj_y1 = inter_y1 - y1
    obj_x2 = obj_x1 + (inter_x2 - inter_x1)
    obj_y2 = obj_y1 + (inter_y2 - inter_y1)
    
    cropped_obj = object_img[obj_y1:obj_y2, obj_x1:obj_x2]
    
    # Background slice
    bg_slice = background_img[inter_y1:inter_y2, inter_x1:inter_x2]
    
    # Paste logic (Blending)
    if cropped_obj.shape[2] == 4:
        alpha_s = cropped_obj[:, :, 3] / 255.0
        alpha_l = 1.0 - alpha_s
        
        for c in range(0, 3):
            bg_slice[:, :, c] = (
                alpha_s * cropped_obj[:, :, c] +
                alpha_l * bg_slice[:, :, c]
            )
    else:
        bg_slice[:] = cropped_obj

    # Update background with blended slice
    background_img[inter_y1:inter_y2, inter_x1:inter_x2] = bg_slice

    # Calculate Visible Bounding Box (YOLO format: x_center, y_center, width, height, normalized)
    # Based on INTERSECTION (visible part)
    vis_w = inter_x2 - inter_x1
    vis_h = inter_y2 - inter_y1
    vis_cx = inter_x1 + vis_w / 2
    vis_cy = inter_y1 + vis_h / 2
    
    # If the object is too occluded (e.g. < 20% visible), we might want to discard it or keep it.
    # For object detection, usually we keep it if recognizable.
    
    norm_cx = vis_cx / bg_w
    norm_cy = vis_cy / bg_h
    norm_w = vis_w / bg_w
    norm_h = vis_h / bg_h
    
    return background_img, [norm_cx, norm_cy, norm_w, norm_h]
