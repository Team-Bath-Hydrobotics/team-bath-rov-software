import sys
import os
import cv2
import numpy as np
import traceback

# Add current directory to path so we can import src
sys.path.append(os.getcwd())

def test_pipeline():
    print("Testing the Pipeline Setup...")
    
    # Create a dummy image (black 640x640)
    dummy_img = np.zeros((640, 640, 3), dtype=np.uint8)
    
    try:
        from src.pipeline import CrabPipeline
        
        # 1. Test YOLOv8
        print("\nTesting YOLOv8 initialisation...")
        # We perform a try-except here because the user might not have 'yolov8n.pt' downloaded yet,
        # but Ultralytics usually downloads it automatically.
        yolo_pipeline = CrabPipeline(model_type='yolov8')
        print("YOLOv8 initialised.")
        
        # Predict
        processed, count, dets = yolo_pipeline.process_frame(dummy_img.copy())
        print(f"YOLOv8 Inference successful. Count: {count}, Detections: {len(dets)}")

        # 2. Test RF-DETR
        print("\nTesting RF-DETR initialisation...")
        # Roboflow's rfdetr library will be used.
        rf_pipeline = CrabPipeline(model_type='rf_detr')
        print("RF-DETR initialised.")
        
        # Predict
        processed, count, dets = rf_pipeline.process_frame(dummy_img.copy())
        print(f"RF-DETR (Multi) Inference successful. Count: {count}, Detections: {len(dets)}")

        # 3. Test Binary Mode (YOLOv8)
        print("\nTesting YOLOv8 (Binary Mode)...")
        binary_pipeline = CrabPipeline(model_type='yolov8', mode='binary')
        processed, count, dets = binary_pipeline.process_frame(dummy_img.copy())
        print(f"YOLOv8 (Binary) Inference successful. Count: {count}, Detections: {len(dets)}")
        
        print("\nAll tests passed!")
        return True
        
    except Exception as e:
        print(f"\nTest FAILED with error:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_pipeline()
