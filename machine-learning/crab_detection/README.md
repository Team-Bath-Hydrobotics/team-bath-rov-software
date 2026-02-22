# European Green Crab Detection Pipeline

This directory contains the data generation, training, and inference scripts for training a machine learning model to detect and count invasive European Green Crabs, whilst differentiating them from Jonah and Rock crabs.

The pipeline is designed to be highly robust to underwater environments and is specifically tailored for applications running on ROV cameras capturing high-resolution (1080p+) images. It uses advanced data augmentation techniques (including copy-paste augmentations) to synthesise varied training data based on a small set of source images.

## Project Structure

```text
├── main.py                     # Entry point for processing images and running inference
├── requirements.txt            # Python dependencies
├── backgrounds/                # Directory containing background images (e.g. BG-20k)
├── source_images/              # Directory containing transparent PNGs of crabs
├── dataset/                    # Generated synthetic YOLO format dataset (created by generate_data.py)
├── scripts/                    
│   ├── generate_data.py        # Script to synthesise the training dataset
│   ├── train.py                # Script to fine-tune YOLOv8 or RF-DETR
│   └── predict.py              # Script to run explicit inferences and save predictions
├── src/                        # Core pipeline, detection models, and data utilities
│   ├── pipeline.py             # Main inference wrapper
│   ├── models/                 # Model wrappers (YOLOv8, RF-DETR)
│   └── utils/                  # Augmentation (Albumentations), dataset classes, and helpers
└── tests/                      # Unit tests for transforms, datasets, and logical helpers
```

## Installation

Ensure you have Python 3.9+ installed and a capable GPU for training. 

1. Clone this repository.
2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### 1. Data Generation

To train a robust model, you must first generate a synthetic dataset. This process takes plain images of crabs (located in `source_images/`) and pastes them onto random background images (located in `backgrounds/`), applying appropriate underwater augmentations.

If you are using a vast background dataset (such as BG-20k), you can use the `--bg_subset` parameter to randomly sample a subset of backgrounds, avoiding excessive memory usage.

```bash
python scripts/generate_data.py --samples 5000 --bg_dir backgrounds/ --src_dir source_images/ --bg_subset 500
```
This script will output a YOLO-formatted dataset inside the `dataset/` directory, including the `data.yaml` configuration required for training.

### 2. Training

The training script supports YOLOv8 and RF-DETR architectures. It automatically logs metrics to TensorBoard and saves visualisation samples throughout the training process.

```bash
python scripts/train.py --model yolov8 --data dataset/data.yaml --epochs 100 --batch 16
```
Training logs and specific weighting runs will be saved in the `runs/train/exp` directory.

### 3. Inference & Detection

You can run predictions on individual images or directories of images using either the `predict.py` script or the main pipeline entry point. 

Using the main pipeline entry point:
```bash
python main.py --source input_images/ --model yolov8 --weights runs/train/exp/weights/best.pt --output output_folder/
```

To just predict and quickly dump output images using the scripts folder:
```bash
python scripts/predict.py --source path/to/image.jpg --weights path/to/weights.pt
```

## Metrics and Visualisation
During training, you can monitor your progress using TensorBoard:
```bash
tensorboard --logdir runs/train/exp
```

## Tests

Comprehensive unit tests are provided to ensure the integrity of the bounding box logic, augmentations, and dataset generation.

To run the tests, simply execute:
```bash
python tests/run_tests.py
```
