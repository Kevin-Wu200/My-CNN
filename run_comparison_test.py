
import sys
import os
import pandas as pd
import numpy as np
import time
from pathlib import Path

# Add backend to path
sys.path.append(os.getcwd())

from backend.services.unsupervised_detection import UnsupervisedDiseaseDetectionService
from backend.utils.image_reader import ImageReader

def run_test():
    image_path = "dataset_download/test_sample.tif"
    gt_path = "dataset_download/ground_truth.csv"
    
    if not os.path.exists(image_path) or not os.path.exists(gt_path):
        print("Test data not found. Run prepare_test_data.py first.")
        return

    # 1. Load Ground Truth
    gt_df = pd.read_csv(gt_path)
    print(f"Loaded {len(gt_df)} ground truth points.")

    # 2. Run Unsupervised Detection
    service = UnsupervisedDiseaseDetectionService()
    
    print("Reading image...")
    success, image_data, msg = ImageReader.read_image(image_path)
    if not success:
        print(f"Failed to read image: {msg}")
        return

    print("Running Unsupervised Detection (on-tiled) with manual thresholds...")
    start_time = time.time()
    # Using manual thresholds to be less restrictive
    success, result, msg = service.detect_on_tiled_image(
        image_data, 
        n_clusters=6, # Increase clusters
        min_area=30,  # Decrease area
        use_parallel=False,
        r_threshold_factor=1.0, 
        g_threshold_factor=1.1,
        contrast_threshold_factor=0.9
    )
    elapsed = time.time() - start_time

    if not success:
        print(f"Detection failed: {msg}")
        return

    pred_points = result["center_points"]
    print(f"Detection completed in {elapsed:.2f}s. Found {len(pred_points)} points.")

    # 3. Compare Results
    pred_df = pd.DataFrame(pred_points)
    
    # Matching logic: for each GT point, find the nearest pred point
    matches = 0
    distance_threshold = 20 # pixels
    
    matched_preds = set()
    
    for _, gt in gt_df.iterrows():
        min_dist = float('inf')
        best_match = -1
        
        for i, pred in pred_df.iterrows():
            dist = np.sqrt((gt['x'] - pred['x'])**2 + (gt['y'] - pred['y'])**2)
            if dist < min_dist:
                min_dist = dist
                best_match = i
        
        if min_dist < distance_threshold:
            matches += 1
            matched_preds.add(best_match)

    precision = matches / len(pred_df) if len(pred_df) > 0 else 0
    recall = matches / len(gt_df) if len(gt_df) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    print("\n--- Test Results ---")
    print(f"Matches: {matches}")
    print(f"Ground Truth Count: {len(gt_df)}")
    print(f"Predicted Count: {len(pred_df)}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"F1 Score: {f1:.4f}")
    
    if f1 < 0.5:
        print("\nWARNING: High deviation detected!")
        analyze_deviation(gt_df, pred_df)
    else:
        print("\nSUCCESS: Results are stable.")

def analyze_deviation(gt, pred):
    print("Analysis:")
    if len(pred) > len(gt) * 2:
        print("- Over-segmentation: Algorithm found too many candidate regions.")
    elif len(pred) < len(gt) / 2:
        print("- Under-segmentation: Algorithm missed many regions (possibly due to min_area or contrast threshold).")
    
    print("- Mean Prediction Area:", pred['area'].mean() if 'area' in pred.columns else "N/A")
    print("- Mean Ground Truth Area:", gt['area'].mean())

if __name__ == "__main__":
    run_test()
