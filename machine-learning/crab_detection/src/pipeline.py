import cv2
import time
from .models.yolov8 import YOLOv8Detector
from .models.rf_detr import RFDETRDetector
from .utils.helpers import count_green_crabs, draw_bounding_boxes

class CrabPipeline:
    """
    Main pipeline for underwater crab detection.
    """
    def __init__(self, model_type='yolov8', model_path=None, mode='multi'):
        """
        Args:
            model_type (str): 'yolov8' or 'rf_detr'.
            model_path (str): Path to weights file (optional).
            mode (str): 'binary' or 'multi'. Defaults to 'multi'.
        """
        self.model_type = model_type
        self.mode = mode
        
        if model_type == 'yolov8':
            path = model_path if model_path else 'yolov8n.pt'
            self.detector = YOLOv8Detector(model_path=path)
        elif model_type == 'rf_detr':
            # For RF-DETR we might use a repo name or local path
            path = model_path if model_path else 'rfdetr-medium'
            self.detector = RFDETRDetector(model_name=path)
        else:
            raise ValueError(f"Unknown model type: {model_type}")
            
    def process_frame(self, frame, draw=True):
        """
        Process a single frame: detect, count, and visualise.
        
        Args:
            frame (np.ndarray): The input image.
            draw (bool): Whether to draw bounding boxes.
        
        Returns:
            processed_frame (np.ndarray): The image with visualisations.
            count (int): The number of Green Crabs.
            detections (list): The raw detections.
        """
        # Inference
        detections = self.detector.predict(frame)
        
        # Count Green Crabs
        green_crab_count = count_green_crabs(detections, mode=self.mode)
        
        # Visualisation
        processed_frame = frame
        if draw:
            processed_frame = draw_bounding_boxes(frame, detections, mode=self.mode)
            
            # Overlay count
            cv2.putText(processed_frame, f"Green Crabs: {green_crab_count}", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
        return processed_frame, green_crab_count, detections

