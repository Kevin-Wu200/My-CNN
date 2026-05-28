
import os
import cv2
import numpy as np
import pandas as pd
from PIL import Image

def prepare_data():
    source_img = "PWD-MFS/R018.JPG"
    target_tif = "dataset_download/test_sample.tif"
    os.makedirs("dataset_download", exist_ok=True)
    
    print(f"Converting {source_img} to {target_tif}...")
    img = cv2.imread(source_img)
    if img is None:
        print("Error: Could not read image.")
        return
        
    # Save as TIFF
    cv2.imwrite(target_tif, img)
    
    # Simple color-based detection to simulate ground truth
    # Pine Wilt diseased trees often look reddish-brown
    # BGR format
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Define range for reddish-brown (diseased)
    lower_red1 = np.array([0, 50, 50])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 50, 50])
    upper_red2 = np.array([180, 255, 255])
    
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = cv2.bitwise_or(mask1, mask2)
    
    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    gt_points = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 100: # Filter small noise
            M = cv2.moments(cnt)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
                gt_points.append({"x": cX, "y": cY, "area": area})
    
    df = pd.DataFrame(gt_points)
    df.to_csv("dataset_download/ground_truth.csv", index=False)
    print(f"Generated ground truth with {len(gt_points)} points.")

if __name__ == "__main__":
    prepare_data()
