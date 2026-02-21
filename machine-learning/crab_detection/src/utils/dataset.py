import os
import cv2
import numpy as np
from torch.utils.data import Dataset
from .transforms import get_train_transforms, get_val_transforms, apply_copy_paste

class SyntheticCrabDataset(Dataset):
    """
    A synthetic dataset that generates training images on the fly by pasting
    transformed crab images onto random backgrounds.
    """
    def __init__(self, background_files, crab_images, num_samples=1000, transform=None):
        """
        Args:
            background_files (list): List of file paths to background images.
            crab_images (dict): Dictionary mapping class_id to a list of crab image paths/arrays.
                                e.g., {0: ['path/to/jonah.jpg'], 1: ['path/to/green.jpg'], ...}
            num_samples (int): Number of synthetic images to generate per epoch.
            transform (A.Compose): Albumentations transform pipeline.
        """
        self.background_files = background_files
        self.crab_images = crab_images
        self.num_samples = num_samples
        self.transform = transform
        
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
            # Union area (not needed for simple overlap check, just intersection ratio relative to the smaller box is safer)
            # Let's just check if intersection covers a significant portion of the NEW box
            box2_area = (b2_x2 - b2_x1) * (b2_y2 - b2_y1)
            return intersection_area / (box2_area + 1e-6)

        MAX_RETRIES = 50
        
        for _ in range(num_crabs):
            # Pick a random class
            cls_id = np.random.choice(list(self.loaded_crabs.keys()))
            # Pick a random image of that class
            crab_img = self.loaded_crabs[cls_id][np.random.randint(0, len(self.loaded_crabs[cls_id]))]
            
            # Try to paste with overlap check
            placed = False
            for attempt in range(MAX_RETRIES):
                # Temporary paste to get candidate bbox
                # We need to access apply_copy_paste's logic without modifying image yet, 
                # OR we modify a temp image. 
                # Optimised way: modify apply_copy_paste to accept coords, or just try-and-discard
                
                # Let's generate random coords first to check against existing bboxes?
                # The bbox depends on the resized object size which apply_copy_paste calculates.
                # Simplest robust way: perform paste on a temp/copy, check bbox, if good, commit.
                
                # Check valid candidate
                # Note: apply_copy_paste handles random placement if we don't supply coords.
                # To check overlap BEFORE pasting, we'd need to reproduce that logic.
                # For simplicity/correctness, let's paste to a dummy variable to get the bbox, 
                # check it, and if valid, re-paste (or use the result).
                
                # BUT pasting is expensive-ish.
                # Let's just let apply_copy_paste do it, check result, and if bad, revert.
                
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
        if self.transform:
            transformed = self.transform(image=current_img, bboxes=bboxes, class_labels=class_labels)
            current_img = transformed['image']
            bboxes = transformed['bboxes']
            class_labels = transformed['class_labels']
            
        return current_img, bboxes, class_labels
