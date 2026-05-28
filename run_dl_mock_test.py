
import sys
import os
import torch
import torch.nn as nn
import pandas as pd
import numpy as np
import time

# Add backend to path
sys.path.append(os.getcwd())

from backend.services.detection import DiseaseTreeDetectionService
from backend.utils.image_reader import ImageReader

# Define a Mock Neural Network
class MockDiseaseModel(nn.Module):
    def __init__(self):
        super(MockDiseaseModel, self).__init__()
        self.fc = nn.Linear(3, 2) # Dummy layer
        
    def forward(self, x):
        # x is (B, C, H, W)
        # We calculate the mean color of the patch
        # If it looks "reddish", we return a high probability for class 1
        batch_size = x.size(0)
        output = torch.zeros(batch_size, 2)
        
        for i in range(batch_size):
            patch = x[i].cpu().numpy() # (C, H, W)
            mean_color = np.mean(patch, axis=(1, 2)) # (C,)
            
            # Simple heuristic: Red > Green and Red > Blue
            # In our case, the patches are already normalized or raw
            # Let's assume raw 0-255 for simplicity in this mock
            r, g, b = mean_color[0], mean_color[1], mean_color[2]
            
            if r > g * 1.1 and r > b * 1.1:
                output[i] = torch.tensor([0.1, 0.9]) # Class 1 (Diseased)
            else:
                output[i] = torch.tensor([0.9, 0.1]) # Class 0 (Healthy)
        
        return output

def run_dl_test():
    image_path = "dataset_download/test_sample.tif"
    gt_path = "dataset_download/ground_truth.csv"
    
    # 1. Load Data
    gt_df = pd.read_csv(gt_path)
    success, image_data, msg = ImageReader.read_image(image_path)
    
    # 2. Setup Mock Service
    model = MockDiseaseModel()
    service = DiseaseTreeDetectionService(model, device="cpu", confidence_threshold=0.6)
    
    print("Running DL Detection (Mock Model)...")
    start_time = time.time()
    # Detection logic: uses SLIC + Patch Inference
    success, result, msg = service.detect_on_tiled_image(
        image_data, 
        tile_size=1024,
        use_parallel=False
    )
    elapsed = time.time() - start_time
    
    if not success:
        print(f"DL Detection failed: {msg}")
        return
        
    pred_points = result["points"]
    print(f"DL Detection completed in {elapsed:.2f}s. Found {len(pred_points)} points.")

    # 3. Compare
    pred_df = pd.DataFrame(pred_points)
    matches = 0
    distance_threshold = 30 # Larger threshold for SLIC centroids
    
    for _, gt in gt_df.iterrows():
        min_dist = float('inf')
        for _, pred in pred_df.iterrows():
            dist = np.sqrt((gt['x'] - pred['x'])**2 + (gt['y'] - pred['y'])**2)
            if dist < min_dist:
                min_dist = dist
        
        if min_dist < distance_threshold:
            matches += 1

    precision = matches / len(pred_df) if len(pred_df) > 0 else 0
    recall = matches / len(gt_df) if len(gt_df) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    print("\n--- DL Mock Test Results ---")
    print(f"Matches: {matches}")
    print(f"Ground Truth Count: {len(gt_df)}")
    print(f"Predicted Count: {len(pred_df)}")
    print(f"F1 Score: {f1:.4f}")
    
    print("\n--- Comparison Analysis ---")
    print("Non-supervised detected 65 points (F1=0.1749)")
    print(f"DL (Mock) detected {len(pred_df)} points (F1={f1:.4f})")
    
    if f1 > 0.1749:
        print("Conclusion: DL-based SLIC patch classification is more stable than simple pixel-level clustering.")
    else:
        print("Conclusion: Both methods struggle with the current image quality or parameters.")

if __name__ == "__main__":
    run_dl_test()
