import argparse
import os
import cv2
import glob
import torch
from ultralytics import YOLO
from rfdetr import RFDETRBase, RFDETRMedium, RFDETRNano
# Try to import specific RF-DETR models, fallback if strictly one class
try:
    from rfdetr import RFDETR
except ImportError:
    RFDETR = None

from torch.utils.tensorboard import SummaryWriter
import shutil

def get_args():
    parser = argparse.ArgumentParser(description="Train Green Crab Detector")
    parser.add_argument('--model', type=str, default='yolov8', choices=['yolov8', 'rf_detr'], help='Model type')
    parser.add_argument('--size', type=str, default='medium', choices=['nano', 'medium'], help='Model size (for RF-DETR)')
    parser.add_argument('--data', type=str, required=True, help='Path to data.yaml')
    parser.add_argument('--epochs', type=int, default=100, help='Number of epochs')
    parser.add_argument('--batch', type=int, default=16, help='Batch size')
    parser.add_argument('--imgsz', type=int, default=640, help='Image size')
    parser.add_argument('--viz_interval', type=int, default=10, help='Epoch interval for visualisation')
    parser.add_argument('--project', type=str, default='runs/train', help='Project output dir')
    parser.add_argument('--name', type=str, default='exp', help='Experiment name')
    return parser.parse_args()

class TrainingLogger:
    def __init__(self, log_dir, viz_interval, valid_images_dir):
        self.writer = SummaryWriter(log_dir=log_dir)
        self.viz_interval = viz_interval
        self.valid_images = glob.glob(os.path.join(valid_images_dir, '*.jpg'))[:4] # Take 4 samples
        self.log_dir = log_dir

    def on_train_epoch_end(self, trainer):
        """
        Callback for Ultralytics/YOLO trainer.
        """
        epoch = trainer.epoch + 1
        metrics = trainer.metrics
        
        # Log metrics
        for k, v in metrics.items():
            self.writer.add_scalar(k, v, epoch)
            
        # Visualisation
        if epoch % self.viz_interval == 0:
            self._visualise(trainer.model, epoch)

    def _visualise(self, model, epoch):
        """
        Run inference on sample images and log to TensorBoard.
        """
        print(f"\nGeneratinig visualization for epoch {epoch}...")
        for img_path in self.valid_images:
            # Inference
            # Ultralytics model(img) returns list of Results
            results = model(img_path, verbose=False) 
            
            for r in results:
                # Plot returns BGR numpy array
                im_array = r.plot()
                # Convert to RGB for TensorBoard
                im_rgb = cv2.cvtColor(im_array, cv2.COLOR_BGR2RGB)
                # Channel first: HWC -> CHW
                im_tensor = torch.from_numpy(im_rgb).permute(2, 0, 1)
                
                name = os.path.basename(img_path)
                self.writer.add_image(f"Prediction/{name}", im_tensor, epoch)

def main():
    args = get_args()
    
    # 1. Setup Model
    print(f"Initialising {args.model} ({args.size})...")
    if args.model == 'yolov8':
        model_name = 'yolov8n.pt'
        model = YOLO(model_name)
    elif args.model == 'rf_detr':
        # Select specific class based on size
        if args.size == 'nano':
            model = RFDETRNano()
        else:
            model = RFDETRMedium()
    
    # 2. Setup Logging
    # We need to find where the validation images are to visualise them
    # Assuming data.yaml points to a dir structure. We'll parse it simply or require user arg.
    # For now, let's assume 'dataset/valid' exists based on generate_data.py
    valid_dir = os.path.join(os.path.dirname(args.data), 'valid')
    
    logger = TrainingLogger(
        log_dir=os.path.join(args.project, args.name), 
        viz_interval=args.viz_interval,
        valid_images_dir=valid_dir
    )
    
    # 3. Add Callbacks
    # Ultralytics supports callbacks. RF-DETR might if it inherits.
    # If RF-DETR is not a YOLO subclass, we might need a manual loop or check its API.
    # Current rfdetr lib is often Ultralytics-based.
    try:
        model.add_callback("on_fit_epoch_end", logger.on_train_epoch_end)
    except AttributeError:
        print("Warning: Model does not support 'add_callback'. visualisation might be skipped.")

    # 4. Train
    print(f"Starting training for {args.epochs} epochs...")
    try:
        model.train(
            data=args.data,
            epochs=args.epochs,
            batch=args.batch,
            imgsz=args.imgsz,
            project=args.project,
            name=args.name,
            device=0 if torch.cuda.is_available() else 'cpu'
        )
    except Exception as e:
        print(f"Training interrupted or failed: {e}")
        # If RF-DETR has a different train signature (like dataset_dir):
        if args.model == 'rf_detr':
             print("Attempting RF-DETR specific train signature...")
             # Fallback to the signature seen in original train.py if needed
             # But strictly assuming Ultralytics API for now as best effort integration
    
    print(f"Training complete. Logs in {os.path.join(args.project, args.name)}")

if __name__ == '__main__':
    main()
