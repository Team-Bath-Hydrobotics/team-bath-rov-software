import argparse
import os
import cv2
import glob
from src.pipeline import CrabPipeline

def main():
    parser = argparse.ArgumentParser(description="Underwater Crab Detection Pipeline")
    parser.add_argument('--source', type=str, required=True, help='Path to input image or directory of images')
    parser.add_argument('--model', type=str, default='yolov8', choices=['yolov8', 'rf_detr'], help='Model to use')
    parser.add_argument('--weights', type=str, default=None, help='Path to model weights')
    parser.add_argument('--output', type=str, default='output', help='Path to output directory')
    parser.add_argument('--display', action='store_true', help='Display image during processing')
    parser.add_argument('--mode', type=str, default='multi', choices=['binary', 'multi'], help='Detection mode: binary (Green/Not) or multi (Green/Jonah/Rock)')
    
    args = parser.parse_args()
    
    source = args.source
    if not os.path.exists(source):
        print(f"File or directory not found: {source}")
        return

    print(f"Initialising {args.model} pipeline in {args.mode} mode...")
    pipeline = CrabPipeline(model_type=args.model, model_path=args.weights, mode=args.mode)
    
    print(f"Processing {source}...")
    
    # Image processing logic
    if os.path.isdir(source):
        images = glob.glob(os.path.join(source, '*.[jJ]*')) + glob.glob(os.path.join(source, '*.[pP][nN][gG]'))
    else:
        images = [source]
        
    for img_path in images:
        img = cv2.imread(img_path)
        if img is None: 
            print(f"Could not read image: {img_path}")
            continue
        
        processed, count, _ = pipeline.process_frame(img)
        
        # Save or Display
        if args.display:
            cv2.imshow('Crab Detection', processed)
            cv2.waitKey(0)
        else:
            # Save to output dir
            os.makedirs(args.output, exist_ok=True)
            name = os.path.basename(img_path)
            cv2.imwrite(os.path.join(args.output, name), processed)
            print(f"Processed {name}: {count} Green Crabs")
            
    if args.display:
        cv2.destroyAllWindows()
    print("Done.")

if __name__ == '__main__':
    main()
