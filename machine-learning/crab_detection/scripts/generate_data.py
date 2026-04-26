import argparse
import os
import sys

import cv2
import yaml
from datasets import load_dataset
from src.utils.dataset import SyntheticCrabDataset
from src.utils.transforms import (
    get_bg_transforms,
    get_crab_color_transforms,
    get_crab_transforms,
)
from tqdm import tqdm

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def generate_split(dataset, output_dir, split_name):
    """
    Generates data for a specific split (train/val/test) and saves it.
    """
    img_dir = os.path.join(output_dir, "images", split_name)
    label_dir = os.path.join(output_dir, "labels", split_name)

    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(label_dir, exist_ok=True)

    print(f"Generating {split_name} data...")

    for i in tqdm(range(len(dataset))):
        # Get sample
        img, bboxes, labels = dataset[i]

        # Save Image
        # Convert RGB to BGR for OpenCV saving
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        filename = f"{split_name}_{i:06d}"
        img_path = os.path.join(img_dir, f"{filename}.jpg")
        cv2.imwrite(img_path, img_bgr)

        # Save Label
        label_path = os.path.join(label_dir, f"{filename}.txt")
        with open(label_path, "w") as f:
            for bbox, label in zip(bboxes, labels):
                # YOLO format: class_id x_center y_center width height
                # bbox is [xc, yc, w, h] normalized
                xc, yc, w, h = bbox
                f.write(f"{label} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic crab data")
    parser.add_argument(
        "--samples", type=int, default=100, help="Total number of samples to generate"
    )
    parser.add_argument(
        "--src_dir",
        type=str,
        default="source_images",
        help="Directory with source crab images",
    )
    parser.add_argument(
        "--output", type=str, default="dataset", help="Output directory"
    )
    args = parser.parse_args()

    # 1. Setup Crab Images
    # Map class IDs to file paths based on filenames.
    # 0: Jonah, 1: Green, 2: Rock

    # Check source dir content
    if not os.path.exists(args.src_dir):
        print(f"Error: Source directory {args.src_dir} not found.")
        return

    # Map based on filenames containing keywords
    crab_images = {0: [], 1: [], 2: []}

    allowed_exts = (".jpg", ".jpeg", ".png")
    for f in os.listdir(args.src_dir):
        if not f.lower().endswith(allowed_exts):
            continue

        path = os.path.join(args.src_dir, f)
        name = f.lower()

        if "jonah" in name:
            crab_images[0].append(path)
        elif "green" in name:
            crab_images[1].append(path)
        elif "rock" in name:
            crab_images[2].append(path)

    # Verification
    print("Found source images:")
    for cls_id, paths in crab_images.items():
        print(f"  Class {cls_id}: {len(paths)} images")

    if not any(len(p) > 0 for p in crab_images.values()):
        print("Error: No crab images found matching 'jonah', 'green', or 'rock'.")
        return

    # 2. Setup Backgrounds
    print(
        "Loading streaming background dataset from Hugging Face: unography/BG-20k-1200px"
    )
    hf_dataset = load_dataset("unography/BG-20k-1200px", split="train", streaming=True)

    # 3. Splits
    # 70% Train, 20% Val, 10% Test
    n_train = int(args.samples * 0.7)
    n_val = int(args.samples * 0.2)
    n_test = args.samples - n_train - n_val

    # 4. Generate
    # Train
    train_ds = SyntheticCrabDataset(
        hf_dataset=hf_dataset,
        crab_images=crab_images,
        num_samples=n_train,
        crab_transform=get_crab_transforms(),
        crab_color_transform=get_crab_color_transforms(),
        bg_transform=get_bg_transforms(640, 640),
        bg_size=(640, 640),
    )
    generate_split(train_ds, args.output, "train")

    # Val (Use validation transforms - less heavy aug, mostly resizing)
    val_ds = SyntheticCrabDataset(
        hf_dataset=hf_dataset,
        crab_images=crab_images,
        num_samples=n_val,
        crab_transform=get_crab_transforms(),
        crab_color_transform=get_crab_color_transforms(),
        bg_transform=get_bg_transforms(640, 640),
        bg_size=(640, 640),
    )
    generate_split(val_ds, args.output, "val")

    # Test
    test_ds = SyntheticCrabDataset(
        hf_dataset=hf_dataset,
        crab_images=crab_images,
        num_samples=n_test,
        crab_transform=get_crab_transforms(),
        crab_color_transform=get_crab_color_transforms(),
        bg_transform=get_bg_transforms(640, 640),
        bg_size=(640, 640),
    )
    generate_split(test_ds, args.output, "test")

    # 5. Create data.yaml
    yaml_data = {
        "path": os.path.abspath(args.output),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {0: "Jonah Crab", 1: "Green Crab", 2: "Rock Crab"},
    }

    yaml_path = os.path.join(args.output, "data.yaml")
    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f, default_flow_style=False)

    print(f"\nData generation complete. Saved to {args.output}")
    print("Format: YOLO")
    print(f"Configuration: {yaml_path}")


if __name__ == "__main__":
    main()
