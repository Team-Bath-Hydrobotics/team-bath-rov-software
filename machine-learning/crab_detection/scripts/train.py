import argparse
import os

import torch
from rfdetr import RFDETRBase, RFDETRLarge, RFDETRMedium, RFDETRNano, RFDETRSmall
from ultralytics import YOLO

# Try to import specific RF-DETR models, fallback if strictly one class
try:
    from rfdetr import RFDETR
except ImportError:
    RFDETR = None

import shutil

import supervision as sv
import yaml


def get_args():
    parser = argparse.ArgumentParser(description="Train Green Crab Detector")
    parser.add_argument(
        "--model",
        type=str,
        default="yolov8",
        choices=["yolov8", "rf_detr"],
        help="Model type",
    )
    parser.add_argument(
        "--size",
        type=str,
        default="medium",
        choices=["nano", "small", "medium", "base", "large"],
        help="Model size (for RF-DETR)",
    )
    parser.add_argument("--data", type=str, required=True, help="Path to data.yaml")
    parser.add_argument("--epochs", type=int, default=100, help="Number of epochs")
    parser.add_argument("--batch", type=int, default=8, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument(
        "--viz_interval", type=int, default=1, help="Epoch interval for visualisation"
    )
    parser.add_argument(
        "--project", type=str, default="runs/train", help="Project output dir"
    )
    parser.add_argument("--name", type=str, default="exp", help="Experiment name")
    return parser.parse_args()


def main():
    args = get_args()

    # 1. Setup Model
    print(f"Initialising {args.model} ({args.size})...")
    if args.model == "yolov8":
        model_name = "yolov8n.pt"
        model = YOLO(model_name)
    elif args.model == "rf_detr":
        # Select specific class based on size
        if args.size == "nano":
            model = RFDETRNano()
        elif args.size == "small":
            model = RFDETRSmall()
        elif args.size == "medium":
            model = RFDETRMedium()
        elif args.size == "large":
            model = RFDETRLarge()
        elif args.size == "base":
            model = RFDETRBase()

    # 2. Setup Logging
    log_dir_path = os.path.join(args.project, args.name)
    if os.path.exists(log_dir_path):
        print(f"Cleaning up previous Tensorboard logs in {log_dir_path}...")
        shutil.rmtree(log_dir_path, ignore_errors=True)

    print(f"Starting training for {args.epochs} epochs...")
    train_kwargs = {
        "epochs": args.epochs,
        "batch": args.batch,
        "imgsz": args.imgsz,
        "workers": 2,
        "project": args.project,
        "name": args.name,
        "save": True,  # Explicitly save best.pt model
        "device": 0 if torch.cuda.is_available() else "cpu",
    }

    if args.model == "rf_detr":
        # RF-DETR expects the directory containing data.yaml
        train_kwargs["dataset_dir"] = (
            os.path.dirname(args.data) if os.path.dirname(args.data) else "."
        )
        train_kwargs["tensorboard"] = True
        train_kwargs["output_dir"] = log_dir_path

        # Transparently auto-convert YOLO to COCO for RF-DETR
        try:
            with open(args.data, "r") as f:
                yaml_content = yaml.safe_load(f)

            base_dir = train_kwargs["dataset_dir"]
            for split in ["train", "val", "test"]:
                if split not in yaml_content:
                    continue

                rfdetr_split_name = "valid" if split == "val" else split
                # Roboflow expects {dataset_dir}/{split}/_annotations.coco.json
                out_json = os.path.join(
                    base_dir, rfdetr_split_name, "_annotations.coco.json"
                )

                img_dir = os.path.join(base_dir, yaml_content[split])
                # In standard YOLO formats, labels are mirrored from images
                lbl_dir = (
                    img_dir.replace("images", "labels")
                    if "images" in img_dir
                    else os.path.join(base_dir, "labels", split)
                )
                split_dir = os.path.dirname(out_json)

                if not os.path.exists(out_json):
                    print(
                        f"Auto-converting YOLO to COCO format for RF-DETR ({split} -> {rfdetr_split_name})..."
                    )
                    if not os.path.exists(img_dir) or not os.path.exists(lbl_dir):
                        continue

                    ds = sv.DetectionDataset.from_yolo(
                        images_directory_path=img_dir,
                        annotations_directory_path=lbl_dir,
                        data_yaml_path=args.data,
                    )

                    os.makedirs(split_dir, exist_ok=True)
                    ds.as_coco(annotations_path=out_json)

                # Ensure images are copied alongside COCO json (regardless of whether json was just created)
                if os.path.exists(img_dir):
                    os.makedirs(split_dir, exist_ok=True)
                    for img in os.listdir(img_dir):
                        src = os.path.join(img_dir, img)
                        dst = os.path.join(split_dir, img)
                        if not os.path.exists(dst):
                            shutil.copy(src, dst)
        except Exception as conv_err:
            print(f"Warning: Failed to auto-convert dataset format: {conv_err}")

    else:
        # YOLOv8 expects the path to data.yaml
        train_kwargs["data"] = args.data

    try:
        model.train(**train_kwargs)
    except Exception as e:
        print(f"Training interrupted or failed: {e}")

    print(f"Training complete. Logs in {os.path.join(args.project, args.name)}")


if __name__ == "__main__":
    main()
