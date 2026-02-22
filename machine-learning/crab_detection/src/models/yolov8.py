from ultralytics import YOLO
import cv2
import numpy as np

class YOLOv8Detector:
    """
    Wrapper for YOLOv8 model using Ultralytics.
    """
    def __init__(self, model_path='yolov8n.pt', confine_conf=0.25, iou_thres=0.45):
        """
        Args:
            model_path (str): Path to the .pt model file or 'yolov8n.pt' for pretrained.
            confine_conf (float): Confidence threshold.
            iou_thres (float): NMS IoU threshold.
        """
        self.model = YOLO(model_path)
        self.conf = confine_conf
        self.iou = iou_thres

    def train(self, data_yaml, epochs=50, imgsz=640):
        """
        Train the model.
        Args:
            data_yaml (str): Path to data.yaml.
            epochs (int): Number of epochs.
            imgsz (int): Image size.
        """
        self.model.train(data=data_yaml, epochs=epochs, imgsz=imgsz)

    def predict(self, image):
        """
        Perform inference on the given image.
        Args:
            image (str or np.ndarray): The image path or numpy array (BGR).
            
        Returns:
            detections (list): A list of [x1, y1, x2, y2, score, class_id]
        """
        results = self.model.predict(image, conf=self.conf, iou=self.iou, verbose=False)
        
        detections = []
        for r in results:
            boxes = r.boxes.cpu().numpy()
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0]
                conf = box.conf[0]
                cls = box.cls[0]
                detections.append([x1, y1, x2, y2, conf, cls])
                
        return detections
