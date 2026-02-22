import torch
import cv2
import numpy as np
from PIL import Image
try:
    from rfdetr import RFDETRNano, RFDETRMedium
except ImportError:
    print("Error: rfdetr not installed. Please install via pip.")
    RFDETRNano = None
    RFDETRMedium = None

class RFDETRDetector:
    """
    Wrapper for RF-DETR using the official Roboflow implementation.
    Offers a choice between Nano and Medium models for optimised real-time performance.
    """
    def __init__(self, model_name='rfdetr-medium', threshold=0.5):
        """
        Initialise the RF-DETR detector.

        Args:
            model_name (str): 'rfdetr-nano' or 'rfdetr-medium'. Defaults to medium.
            threshold (float): Confidence threshold for predictions.
        """
        self.threshold = threshold
        
        if RFDETRMedium is None:
            raise ImportError("The 'rfdetr' library is missing. Please run 'pip install rfdetr'.")

        if 'nano' in model_name.lower():
            self.model = RFDETRNano()
        else:
            self.model = RFDETRMedium() # Default to medium as requested
            
        # The model automatically handles device placement (CUDA if available)

    def predict(self, image):
        """
        Run inference on an image.

        Args:
            image (str or np.ndarray): Image path or numpy array (BGR).
            
        Returns:
            detections (list): List of [x1, y1, x2, y2, score, class_id]
        """
        # Convert BGR (OpenCV) to RGB (PIL) or utilize internal handling
        # RF-DETR expects PIL Image or similar
        if isinstance(image, str):
            pil_image = Image.open(image).convert("RGB")
        elif isinstance(image, np.ndarray):
            # Convert BGR to RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_image)
        else:
            pil_image = image # Assume PIL
            
        # Run inference
        # Returns a supervision.Detections object usually, or similar dataclass
        results = self.model.predict(pil_image, threshold=self.threshold)
        
        detections = []
        
        # rfdetr returns a supervision.Detections object efficiently
        # properties: xyxy, confidence, class_id
        # We need to check if results is a list or single object. Usually single for one image.
        
        # Ensure we have data to iterate over
        if hasattr(results, 'xyxy'):
            for i in range(len(results.xyxy)):
                x1, y1, x2, y2 = results.xyxy[i].tolist()
                score = results.confidence[i].item() if results.confidence is not None else 0.0
                class_id = int(results.class_id[i].item()) if results.class_id is not None else -1
                
                # Format: [x1, y1, x2, y2, score, class_id]
                detections.append([x1, y1, x2, y2, score, class_id])
                
        return detections
