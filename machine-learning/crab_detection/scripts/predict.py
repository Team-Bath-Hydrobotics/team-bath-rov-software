import sys
import argparse
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import cv2
import glob
from src.pipeline import CrabPipeline

def main():
    parser = argparse.ArgumentParser(description="Run inference on images")
    parser.add_argument('--source', type=str, required=True, help='Path to image or directory of images')
    parser.add_argument('--model', type=str, default='yolov8', choices=['yolov8', 'rf_detr'], help='Model type')
    parser.add_argument('--weights', type=str, default=None, help='Path to weights file')
    parser.add_argument('--mode', type=str, default='multi', choices=['binary', 'multi'], help='Detection mode (binary/multi)')
    parser.add_argument('--output', type=str, default='output_predictions', help='Output directory')
    args = parser.parse_args()

    # Setup Output
    os.makedirs(args.output, exist_ok=True)
    
    # Initialise Pipeline
    print(f"Initialising {args.model} pipeline in {args.mode} mode...")
    try:
        pipeline = CrabPipeline(model_type=args.model, model_path=args.weights, mode=args.mode)
    except Exception as e:
        print(f"Failed to initialise pipeline: {e}")
        return

    # Gather Images
    if os.path.isdir(args.source):
        images = glob.glob(os.path.join(args.source, '*.[jJ][pP]*[gG]')) # matches .jpg, .jpeg, .png etc
        images += glob.glob(os.path.join(args.source, '*.[pP][nN][gG]'))
    else:
        images = [args.source]
        
    print(f"Found {len(images)} images to process.")
    
    # Process
    for img_path in images:
        if not os.path.exists(img_path):
            print(f"Skipping missing file: {img_path}")
            continue
            
        print(f"Processing {os.path.basename(img_path)}...")
        img = cv2.imread(img_path)
        if img is None:
            print(f"Could not read image: {img_path}")
            continue
            
        # Run Pipeline
        processed_img, count, detections = pipeline.process_frame(img)
        
        # Save Result
        filename = os.path.basename(img_path)
        save_path = os.path.join(args.output, f"pred_{filename}")
        cv2.imwrite(save_path, processed_img)
        
        print(f"  -> Count: {count} | Detections: {len(detections)}")
        print(f"  -> Saved to {save_path}")

    print("\nInference Complete.")

if __name__ == "__main__":
    main()
