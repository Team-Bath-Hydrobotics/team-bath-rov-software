import albumentations as A
import cv2
import numpy as np


def get_crab_transforms():
    """
    Returns the Albumentations transform pipeline for individual crab images.
    Applies geometric augmentations to individual crabs before pasting.
    """
    return A.Compose(
        [
            A.RandomRotate90(p=0.5),
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.5),
            A.Affine(
                scale=(0.8, 1.2),
                translate_percent=(0.0, 0.0625),
                rotate=(-180, 180),
                shear=(-20, 20),
                p=0.8,
                fit_output=True,
            ),
        ]
    )


def get_crab_color_transforms():
    """
    Returns the Albumentations transform pipeline for crab color augmentation.
    """
    return A.Compose(
        [
            A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1, p=0.8),
            A.RGBShift(r_shift_limit=20, g_shift_limit=20, b_shift_limit=20, p=0.8),
        ]
    )


def get_bg_transforms(height=640, width=640):
    """
    Returns the Albumentations transform pipeline for the final composite image.
    Applies global effects like blur, colour changes, and resizing.
    """
    return A.Compose(
        [
            A.OneOf(
                [
                    A.GaussNoise(std_range=(0.012, 0.027), p=1.0),
                ],
                p=0.05,
            ),
            A.OneOf(
                [
                    A.MotionBlur(p=0.2),
                    A.MedianBlur(blur_limit=3, p=0.1),
                    A.Blur(blur_limit=3, p=0.1),
                ],
                p=0.1,
            ),
            A.OneOf(
                [
                    A.ElasticTransform(p=0.3),
                ],
                p=0.1,
            ),
            A.OneOf(
                [
                    A.CLAHE(clip_limit=2),
                    A.Sharpen(),
                    A.Emboss(),
                    A.RandomBrightnessContrast(),
                ],
                p=0.2,
            ),
            A.HueSaturationValue(p=0.2),
            A.Resize(height, width),
        ],
        bbox_params=A.BboxParams(format="yolo", label_fields=["class_labels"]),
    )


def get_val_transforms(height=640, width=640):
    """
    Returns the Albumentations transform pipeline for validation or inference.
    Mainly applies resizing and normalisation.
    """
    return A.Compose(
        [
            A.Resize(height, width),
        ],
        bbox_params=A.BboxParams(format="yolo", label_fields=["class_labels"]),
    )


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

    # Resize object to ensure crabs aren't too large
    max_scale = 0.35  # Max size relative to background
    scale = 1.0
    if obj_h > bg_h * max_scale or obj_w > bg_w * max_scale:
        scale = min((bg_h * max_scale) / obj_h, (bg_w * max_scale) / obj_w)

    # Scale down a bit more randomly for variety
    scale *= np.random.uniform(0.5, 1.0)

    if scale < 1.0:
        new_w = max(1, int(obj_w * scale))
        new_h = max(1, int(obj_h * scale))
        object_img = cv2.resize(
            object_img, (new_w, new_h), interpolation=cv2.INTER_AREA
        )
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
                alpha_s * cropped_obj[:, :, c] + alpha_l * bg_slice[:, :, c]
            )

        # Update background with blended slice
        background_img[inter_y1:inter_y2, inter_x1:inter_x2] = bg_slice

        # Mathematically tightening the box to the non-transparent visible pixels
        mask = (cropped_obj[:, :, 3] > 10).astype(np.uint8)
        x, y, w, h = cv2.boundingRect(mask)

        if w == 0 or h == 0:
            return background_img, [0, 0, 0, 0]

        vis_cx = inter_x1 + x + w / 2.0
        vis_cy = inter_y1 + y + h / 2.0
        vis_w = w
        vis_h = h
    else:
        bg_slice[:] = cropped_obj
        # Update background with blended slice
        background_img[inter_y1:inter_y2, inter_x1:inter_x2] = bg_slice

        vis_w = inter_x2 - inter_x1
        vis_h = inter_y2 - inter_y1
        vis_cx = inter_x1 + vis_w / 2.0
        vis_cy = inter_y1 + vis_h / 2.0

    # If the object is too occluded (e.g. < 20% visible), we might want to discard it or keep it.
    # For object detection, usually we keep it if recognizable.

    norm_cx = vis_cx / bg_w
    norm_cy = vis_cy / bg_h
    norm_w = vis_w / bg_w
    norm_h = vis_h / bg_h

    return background_img, [norm_cx, norm_cy, norm_w, norm_h]
