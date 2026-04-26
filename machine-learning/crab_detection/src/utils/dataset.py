import cv2
import numpy as np
from torch.utils.data import Dataset

from .transforms import apply_copy_paste


class SyntheticCrabDataset(Dataset):
    """
    A synthetic dataset that generates training images by pasting
    transformed crab images onto random backgrounds.
    """

    def __init__(
        self,
        hf_dataset,
        crab_images,
        num_samples=1000,
        crab_transform=None,
        crab_color_transform=None,
        bg_transform=None,
        bg_size=(640, 640),
    ):
        """
        Args:
            hf_dataset (IterableDataset): HuggingFace streaming dataset for backgrounds.
            crab_images (dict): Dictionary mapping class_id to a list of crab image paths/arrays.
                                e.g., {0: ['path/to/jonah.jpg'], 1: ['path/to/green.jpg'], ...}
            num_samples (int): Number of synthetic images to generate per epoch.
            crab_transform (A.Compose): Transform pipeline for individual crabs.
            bg_transform (A.Compose): Transform pipeline for the full background image.
        """
        self.hf_dataset = hf_dataset
        self.bg_iterator = iter(self.hf_dataset)
        self.crab_images = crab_images
        self.num_samples = num_samples
        self.crab_transform = crab_transform
        self.crab_color_transform = crab_color_transform
        self.bg_transform = bg_transform
        self.bg_size = bg_size

        # Load crab images into memory if paths are provided
        self.loaded_crabs = {}
        for cls_id, paths in crab_images.items():
            self.loaded_crabs[cls_id] = []
            for p in paths:
                if isinstance(p, str):
                    img = cv2.imread(p, cv2.IMREAD_UNCHANGED)
                    if img is None:
                        continue
                    if len(img.shape) == 2:
                        img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGBA)
                    elif img.shape[2] == 3:
                        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        alpha = np.full(
                            (img.shape[0], img.shape[1], 1), 255, dtype=np.uint8
                        )
                        img = np.concatenate([img, alpha], axis=2)
                    elif img.shape[2] == 4:
                        img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
                    self.loaded_crabs[cls_id].append(img)
                else:
                    self.loaded_crabs[cls_id].append(p)

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        # 1. Select a random background from HF streaming dataset
        try:
            bg_data = next(self.bg_iterator)
        except StopIteration:
            self.bg_iterator = iter(self.hf_dataset)
            bg_data = next(self.bg_iterator)

        background_pil = bg_data["image"].convert("RGB")
        background = np.array(background_pil)

        # Crop background to specified size
        h, w = background.shape[:2]
        crop_h, crop_w = self.bg_size

        if h < crop_h or w < crop_w:
            scale = max(crop_h / h, crop_w / w)
            new_w = int(w * scale) + 1
            new_h = int(h * scale) + 1
            background = cv2.resize(
                background, (new_w, new_h), interpolation=cv2.INTER_LINEAR
            )
            h, w = background.shape[:2]

        y1 = np.random.randint(0, h - crop_h + 1) if h > crop_h else 0
        x1 = np.random.randint(0, w - crop_w + 1) if w > crop_w else 0
        background = background[y1 : y1 + crop_h, x1 : x1 + crop_w]

        # 2. Select the number of crabs to paste (random 0-5)
        # 0 crabs simulates a background / negative image for reducing false positives
        num_crabs = np.random.randint(0, 6)

        bboxes = []
        class_labels = []

        # 3. Paste the crabs
        current_img = background.copy()

        # Helper to check overlap
        def get_intersection_area(box1, box2):
            # box: [xc, yc, w, h] normalized
            # Convert to [x1, y1, x2, y2]
            def to_coords(b):
                xc, yc, w, h = b
                x1 = xc - w / 2
                y1 = yc - h / 2
                x2 = xc + w / 2
                y2 = yc + h / 2
                return x1, y1, x2, y2

            b1_x1, b1_y1, b1_x2, b1_y2 = to_coords(box1)
            b2_x1, b2_y1, b2_x2, b2_y2 = to_coords(box2)

            # Intersection rectangle
            x_left = max(b1_x1, b2_x1)
            y_top = max(b1_y1, b2_y1)
            x_right = min(b1_x2, b2_x2)
            y_bottom = min(b1_y2, b2_y2)

            if x_right < x_left or y_bottom < y_top:
                return 0.0

            intersection_area = (x_right - x_left) * (y_bottom - y_top)
            box1_area = (b1_x2 - b1_x1) * (b1_y2 - b1_y1)
            box2_area = (b2_x2 - b2_x1) * (b2_y2 - b2_y1)
            min_area = min(box1_area, box2_area)
            return intersection_area / (min_area + 1e-6)

        MAX_RETRIES = 50

        for _ in range(num_crabs):
            # Pick a random class
            cls_id = np.random.choice(list(self.loaded_crabs.keys()))
            # Pick a random image of that class
            crab_img = self.loaded_crabs[cls_id][
                np.random.randint(0, len(self.loaded_crabs[cls_id]))
            ]

            if self.crab_transform:
                transformed_crab = self.crab_transform(image=crab_img)
                crab_img = transformed_crab["image"]

            if getattr(self, "crab_color_transform", None) and crab_img.shape[2] == 4:
                rgb = crab_img[:, :, :3]
                alpha = crab_img[:, :, 3:]
                transformed_color = self.crab_color_transform(image=rgb)
                crab_img = np.concatenate([transformed_color["image"], alpha], axis=2)

            # Attempt to paste object while ensuring minimum overlap
            placed = False
            for attempt in range(MAX_RETRIES):
                # Perform copy-paste on a temporary duplicate image to validate candidate bounding box

                temp_img, candidate_bbox = apply_copy_paste(
                    current_img.copy(), crab_img
                )

                # Check if crab is completely out of frame or heavily cropped (< 2% of frame width/height)
                if candidate_bbox[2] < 0.02 or candidate_bbox[3] < 0.02:
                    continue

                overlap_found = False
                for existing_bbox in bboxes:
                    # check intersection > 10%
                    if get_intersection_area(existing_bbox, candidate_bbox) > 0.1:
                        overlap_found = True
                        break

                if not overlap_found:
                    current_img = temp_img
                    bboxes.append(candidate_bbox)
                    class_labels.append(cls_id)
                    placed = True
                    break

            if not placed:
                # Could not place crab after retries (scene too full)
                pass

        # 4. Apply global transformations (underwater effects, etc.)
        if self.bg_transform:
            transformed = self.bg_transform(
                image=current_img, bboxes=bboxes, class_labels=class_labels
            )
            current_img = transformed["image"]
            bboxes = transformed["bboxes"]
            class_labels = transformed["class_labels"]

        return current_img, bboxes, class_labels
