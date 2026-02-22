import cv2
import numpy as np

# Multi-class mapping (Green vs Jonah vs Rock)
MULTI_CLASS_MAP = {
    0: 'Jonah Crab',
    1: 'Green Crab',
    2: 'Rock Crab'
}

# Binary mapping (Green vs Not Green)
BINARY_CLASS_MAP = {
    0: 'Green Crab',
    1: 'Not Green Crab'
}

def count_green_crabs(detections, mode='multi'):
    """
    Counts the number of Green Crabs in the detections.
    
    Args:
        detections (list): List of detections [x1, y1, x2, y2, score, class_id]
        mode (str): 'binary' or 'multi'.
                           
    Returns:
        int: Number of Green Crabs detected.
    """
    count = 0
    target_id = 1 if mode == 'multi' else 0 # In binary, Green is usually 0 (positive class)
    
    for det in detections:
        class_id = int(det[5])
        if class_id == target_id:
            count += 1
    return count

def draw_bounding_boxes(image, detections, mode='multi'):
    """
    Draws bounding boxes on the image.
    
    Args:
        image (np.array): The image to draw on.
        detections (list): List of detections [x1, y1, x2, y2, score, class_id]
        mode (str): 'binary' or 'multi'.
    """
    img_copy = image.copy()
    class_map = MULTI_CLASS_MAP if mode == 'multi' else BINARY_CLASS_MAP
    
    for det in detections:
        x1, y1, x2, y2, score, class_id = det
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        class_id = int(class_id)
        
        colour = (0, 0, 255) # Red (default)
        label = f"Unknown: {score:.2f}"
        
        if class_id in class_map:
            name = class_map[class_id]
            label = f"{name}: {score:.2f}"
            
            # Colour logic
            if name == 'Green Crab':
                colour = (0, 255, 0) # Green
            elif name == 'Not Green Crab':
                colour = (0, 0, 255) # Red
            elif name == 'Jonah Crab':
                colour = (255, 0, 0) # Blue
            elif name == 'Rock Crab':
                colour = (0, 255, 255) # Yellow
        
        cv2.rectangle(img_copy, (x1, y1), (x2, y2), colour, 2)
        cv2.putText(img_copy, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 2)
            
    return img_copy
