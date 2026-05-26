import sys
import os
import logging
import time
import torch
import numpy as np
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.services.unsupervised_detection import UnsupervisedDiseaseDetectionService
from backend.services.training import TrainingService
from backend.services.detection import DiseaseTreeDetectionService
from backend.services.sample_construction import SampleConstructionService
from backend.models.cnn_model import DiseaseTreeCNN
from backend.models.training_dataset import create_dataloaders
from backend.utils.image_reader import ImageReader
from backend.utils.resource_monitor import ResourceMonitor
from backend.services.background_task_manager import get_task_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("simulate_workflow.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("WorkflowSimulation")

def create_dummy_geojson(output_path, points, image_info):
    """Create a GeoJSON file from points."""
    features = []
    for pt in points:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [pt["x"], pt["y"]] # Note: These are pixel coords, real GeoJSON needs geo coords but our backend handles pixel coords in some cases or we simulate
            },
            "properties": {
                "area": pt.get("area", 0),
                "type": "disease_tree"
            }
        })
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    with open(output_path, "w") as f:
        json.dump(geojson, f)
    return True

async def simulate_workflow():
    image_path = "/Users/wuchenkai/解译程序/20201023.tif"
    if not os.path.exists(image_path):
        logger.error(f"Image not found at {image_path}")
        return

    logger.info(f"Starting simulation with image: {image_path}")
    ResourceMonitor.log_resource_status("START")

    # 1. Unsupervised Detection
    logger.info("--- Step 1: Unsupervised Detection ---")
    unsupervised_service = UnsupervisedDiseaseDetectionService()
    task_manager = get_task_manager()
    task_id_unsup = "sim_unsup_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    task_manager.create_task("unsupervised_detection", task_id=task_id_unsup)
    
    start_time = time.time()
    success, unsup_result, msg = unsupervised_service.detect_from_file(
        image_path,
        n_clusters=4,
        min_area=50,
        task_manager=task_manager,
        task_id=task_id_unsup
    )
    elapsed = time.time() - start_time
    
    if not success:
        logger.error(f"Unsupervised detection failed: {msg}")
    else:
        logger.info(f"Unsupervised detection successful in {elapsed:.2f}s")
        logger.info(f"Found {unsup_result['n_candidates']} candidates")
    
    ResourceMonitor.log_resource_status("AFTER_UNSUPERVISED")

    # 2. Dummy GeoJSON Generation
    logger.info("--- Step 2: Dummy GeoJSON Generation ---")
    geojson_path = Path("storage/temp_samples/samples.geojson")
    geojson_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Use top 100 points for training simulation
    sample_points = unsup_result['center_points'][:100] if success else []
    if not sample_points:
        # Fallback to some random points if no candidates found
        logger.warning("No candidates found, using random points for simulation")
        sample_points = [{"x": 1000, "y": 1000}, {"x": 5000, "y": 5000}]
    
    create_dummy_geojson(geojson_path, sample_points, None)
    logger.info(f"Generated dummy GeoJSON with {len(sample_points)} points at {geojson_path}")

    # 3. Model Training Simulation
    logger.info("--- Step 3: Model Training Simulation ---")
    # We simulate the _run_training_task logic
    image_files = [image_path]
    patch_size = 64
    
    task_id_train = "sim_train_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    task_manager.create_task("training", task_id=task_id_train)
    
    logger.info("Cropping patches from files (streamed)...")
    success, positive_patches_gen, msg = SampleConstructionService.crop_patches_from_files(
        image_files, sample_points, patch_size=patch_size
    )
    
    if not success:
        logger.error(f"Sample construction failed: {msg}")
        return

    positive_patches = []
    for batch in positive_patches_gen:
        positive_patches.extend(batch)
    logger.info(f"Generated {len(positive_patches)} positive patches")
    
    # Generate negative patches
    success, negative_patches_gen, msg = SampleConstructionService.generate_negative_samples_from_files(
        image_files, sample_points,
        num_negative_samples=len(positive_patches),
        patch_size=patch_size,
        min_distance=100
    )
    negative_patches = []
    # Note: generate_negative_samples_from_files returns a list, not a generator in current implementation
    # but let's be safe and check if it's iterable of batches or just a list of patches
    if isinstance(negative_patches_gen, list):
        negative_patches = negative_patches_gen
    else:
        for batch in negative_patches_gen:
            negative_patches.extend(batch)
    logger.info(f"Generated {len(negative_patches)} negative patches")

    all_samples = positive_patches + negative_patches
    all_labels = np.concatenate([
        np.ones(len(positive_patches), dtype=np.int32),
        np.zeros(len(negative_patches), dtype=np.int32),
    ])

    # Split
    train_samples = all_samples # Simple split for simulation
    train_labels = all_labels
    val_samples = all_samples
    val_labels = all_labels

    # DataLoader
    train_loader, val_loader = create_dataloaders(
        train_samples, train_labels,
        val_samples, val_labels,
        batch_size=8,
        num_workers=2
    )

    # Model
    model = DiseaseTreeCNN(in_channels=4, num_timesteps=1) # Assuming 4 bands for TIFF
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    model_save_dir = Path("storage/models/sim_model")
    model_save_dir.mkdir(parents=True, exist_ok=True)
    
    training_service = TrainingService(
        model=model,
        device=device,
        model_save_dir=model_save_dir
    )

    logger.info("Starting training (simulated 2 epochs)...")
    history = training_service.train(
        train_loader=train_loader,
        val_loader=val_loader,
        num_epochs=2,
        learning_rate=0.001
    )
    
    model_path = model_save_dir / "final_model.pth"
    torch.save(model.state_dict(), model_path)
    logger.info(f"Training completed. Model saved at {model_path}")
    
    ResourceMonitor.log_resource_status("AFTER_TRAINING")

    # 4. Supervised Detection
    logger.info("--- Step 4: Supervised Detection ---")
    detection_service = DiseaseTreeDetectionService(
        model=model,
        device=device,
        confidence_threshold=0.5
    )
    
    start_time = time.time()
    success, det_result, msg = detection_service.detect_from_file(
        image_path,
        tile_size=1024,
        use_parallel=True,
        num_workers=4
    )
    elapsed = time.time() - start_time
    
    if not success:
        logger.error(f"Supervised detection failed: {msg}")
    else:
        logger.info(f"Supervised detection successful in {elapsed:.2f}s")
        logger.info(f"Found {len(det_result['points'])} disease trees")

    ResourceMonitor.log_resource_status("FINISH")
    logger.info("Simulation finished.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(simulate_workflow())
