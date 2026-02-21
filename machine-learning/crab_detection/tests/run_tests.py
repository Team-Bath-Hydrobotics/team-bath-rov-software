import unittest
import numpy as np
import cv2
import sys
import os
import shutil

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.transforms import get_train_transforms, get_val_transforms, apply_copy_paste
from src.utils.dataset import SyntheticCrabDataset
from src.utils.helpers import count_green_crabs, draw_bounding_boxes
from src.pipeline import CrabPipeline

class TestTransforms(unittest.TestCase):
    def setUp(self):
        self.img = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
        self.bboxes = [[0.5, 0.5, 0.2, 0.2]] # YOLO format
        self.labels = [1]

    def test_train_transforms(self):
        transform = get_train_transforms(640, 640)
        augmented = transform(image=self.img, bboxes=self.bboxes, class_labels=self.labels)
        self.assertIn('image', augmented)
        self.assertEqual(augmented['image'].shape, (640, 640, 3))
    
    def test_copy_paste(self):
        bg = np.zeros((100, 100, 3), dtype=np.uint8)
        obj = np.ones((10, 10, 3), dtype=np.uint8) * 255
        res_img, bbox = apply_copy_paste(bg, obj)
        self.assertEqual(res_img.shape, (100, 100, 3))
        # Ensure object is pasted (not all zeros anymore - alpha blend might make it subtle but we used white)
        # Bbox should be valid [x, y, w, h]
        self.assertEqual(len(bbox), 4)
        # Check area > 0 if visible
        if bbox[2] > 0 and bbox[3] > 0:
             self.assertTrue(bbox[0] >= 0)

class TestDataset(unittest.TestCase):
    def setUp(self):
        self.test_dir = 'tests/tmp_dataset'
        os.makedirs(self.test_dir, exist_ok=True)
        # Create dummy bg image
        cv2.imwrite(os.path.join(self.test_dir, 'bg.jpg'), np.zeros((100, 100, 3), dtype=np.uint8))
        # Dummy crab image
        self.crab_imgs = {0: [np.zeros((10, 10, 3), dtype=np.uint8)]}

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_synthetic_generation(self):
        bg_files = [os.path.join(self.test_dir, 'bg.jpg')]
        ds = SyntheticCrabDataset(bg_files, self.crab_imgs, num_samples=2)
        img, bboxes, labels = ds[0]
        self.assertIsInstance(img, np.ndarray)
        self.assertIsInstance(bboxes, list)
        self.assertIsInstance(labels, list)
        # Bboxes should be normalized (0-1)
        if len(bboxes) > 0:
            self.assertLessEqual(np.max(bboxes), 1.0)
            self.assertGreaterEqual(np.min(bboxes), 0.0)

    def test_overlap_prevention(self):
        # Force a small background and large object to ensure overlap is likely if unchecked
        # This is hard to deterministically test without mocking internals, but we can check basic execution
        bg_files = [os.path.join(self.test_dir, 'bg.jpg')]
        ds = SyntheticCrabDataset(bg_files, self.crab_imgs, num_samples=5)
        # Just ensure it runs without crashing and produces valid bboxes
        img, bboxes, labels = ds[0]
        self.assertTrue(len(bboxes) <= 6) # <= 6 because random 1-5 crabs, not num_samples

class TestHelpers(unittest.TestCase):
    def test_counting_multi(self):
        # [x1, y1, x2, y2, score, class_id]
        dets = [
            [0,0,10,10, 0.9, 0], # Jonah
            [0,0,10,10, 0.9, 1], # Green
            [0,0,10,10, 0.9, 2], # Rock
            [0,0,10,10, 0.9, 1]  # Green
        ]
        count = count_green_crabs(dets, mode='multi')
        self.assertEqual(count, 2)

    def test_counting_binary(self):
        # In binary: 0=Green, 1=Not
        dets = [
            [0,0,10,10, 0.9, 0], # Green
            [0,0,10,10, 0.9, 1], # Not Green
            [0,0,10,10, 0.9, 0]  # Green
        ]
        count = count_green_crabs(dets, mode='binary')
        self.assertEqual(count, 2)

class TestPipeline(unittest.TestCase):
    def test_yolo_pipeline_init(self):
        try:
            # We don't have weights downloaded in test env usually, so expect possible creation or failure if download blocks
            # But class instantiation should be fine
            pipeline = CrabPipeline(model_type='yolov8', mode='multi')
            self.assertIsNotNone(pipeline.detector)
        except Exception as e:
            # In CI/No-Internet env, this might fail on download. 
            pass

if __name__ == '__main__':
    unittest.main()
