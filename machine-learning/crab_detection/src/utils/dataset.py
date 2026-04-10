import os
import cv2
import numpy as np
from torch.utils.data import Dataset
from .transforms import apply_copy_paste

class SyntheticCrabDataset(Dataset):
    """
    A synthetic dataset that generates training images by pasting
    transformed crab images onto random backgrounds.
    """
    def __init__(self, background_files, crab_images, num_samples=1000, crab_transform=None, bg_transform=None):
        """
        Args:
            background_files (list): List of file paths to background images.
            crab_images (dict): Dictionary mapping class_id to a list of crab image paths/arrays.
                                e.g., {0: ['path/to/jonah.jpg'], 1: ['path/to/green.jpg'], ...}
            num_samples (int): Number of synthetic images to generate per epoch.
            crab_transform (A.Compose): Transform pipeline for individual crabs.
            bg_transform (A.Compose): Transform pipeline for the full background image.
        """
        self.background_files = background_files
        self.crab_images = crab_images
        self.num_samples = num_samples
        self.crab_transform = crab_transform
        self.bg_transform = bg_transform
        
        # Load crab images into memory if paths are provided
        self.loaded_crabs = {}
        for cls_id, paths in crab_images.items():
            self.loaded_crabs[cls_id] = []
            for p in paths:
                if isinstance(p, str):
                    img = cv2.imread(p)
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    self.loaded_crabs[cls_id].append(img)
                else:
                    self.loaded_crabs[cls_id].append(p)

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        # 1. Select a random background
        bg_path = np.random.choice(self.background_files)
        background = cv2.imread(bg_path)
        background = cv2.cvtColor(background, cv2.COLOR_BGR2RGB)
        
        # 2. Select the number of crabs to paste (random 1-5)
        num_crabs = np.random.randint(1, 6)
        
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
                x1 = xc - w/2
                y1 = yc - h/2
                x2 = xc + w/2
                y2 = yc + h/2
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
            crab_img = self.loaded_crabs[cls_id][np.random.randint(0, len(self.loaded_crabs[cls_id]))]
            
            if self.crab_transform:
                transformed_crab = self.crab_transform(image=crab_img)
                crab_img = transformed_crab['image']
                
            # Attempt to paste object while ensuring minimum overlap
            placed = False
            for attempt in range(MAX_RETRIES):
                # Perform copy-paste on a temporary duplicate image to validate candidate bounding box
                
                temp_img, candidate_bbox = apply_copy_paste(current_img.copy(), crab_img)
                
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
            transformed = self.bg_transform(image=current_img, bboxes=bboxes, class_labels=class_labels)
            current_img = transformed['image']
            bboxes = transformed['bboxes']
            class_labels = transformed['class_labels']
            
        return current_img, bboxes, class_labels
