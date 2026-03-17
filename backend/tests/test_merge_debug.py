"""
步骤23: 单 tile merge 测试
验证 merge 流程是否正常工作（只合并前 3 个 tile）
"""

import numpy as np
import os
import sys
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.services.unsupervised_detection import UnsupervisedDiseaseDetectionService
from backend.utils.tile_utils import TilingService, DEFAULT_TILE_SIZE
from backend.services.image_chunking import ImageChunkingService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def test_merge_tiles_small():
    """测试 TilingService.merge_tiles: 只合并前 3 个 tile"""
    logger.info("=" * 60)
    logger.info("测试1: TilingService.merge_tiles (前3个tile)")
    logger.info("=" * 60)

    # 创建测试影像 (2048x2048, 3通道)
    H, W, C = 2048, 2048, 3
    image_data = np.random.randint(0, 255, (H, W, C), dtype=np.uint8)

    # 生成分块
    success, tiles, msg = TilingService.generate_tiles(image_data, tile_size=DEFAULT_TILE_SIZE)
    assert success, f"分块生成失败: {msg}"
    logger.info(f"生成 {len(tiles)} 个分块")

    # 只取前 3 个 tile
    tiles_subset = tiles[:3]
    logger.info(f"只合并前 {len(tiles_subset)} 个 tile")

    # 合并
    success, merged, msg = TilingService.merge_tiles(tiles_subset, H, W)
    assert success, f"合并失败: {msg}"
    assert merged.shape[:2] == (H, W), f"合并后尺寸不匹配: {merged.shape}"
    logger.info(f"合并成功: shape={merged.shape}")

    # 验证前 3 个 tile 区域的数据正确性
    for tile in tiles_subset:
        y_start, y_end, x_start, x_end = tile.get_original_bounds()
        original_region = image_data[y_start:y_end, x_start:x_end]
        merged_region = merged[y_start:y_end, x_start:x_end]
        assert np.array_equal(original_region, merged_region), (
            f"tile {tile.tile_index} 数据不匹配"
        )
    logger.info("前3个tile数据验证通过")


def test_merge_tile_masks_small():
    """测试 _merge_tile_masks: 只合并前 3 个 tile mask"""
    logger.info("=" * 60)
    logger.info("测试2: _merge_tile_masks (前3个tile)")
    logger.info("=" * 60)

    H, W = 2048, 2048
    tile_size = DEFAULT_TILE_SIZE

    # 创建模拟的 tile 结果
    tiles_mask_dir = os.path.join("storage", "tiles_mask_test")
    os.makedirs(tiles_mask_dir, exist_ok=True)

    valid_results = []
    tile_index = 0
    for y in range(0, H, tile_size):
        for x in range(0, W, tile_size):
            if tile_index >= 3:
                break
            tile_h = min(tile_size, H - y)
            tile_w = min(tile_size, W - x)
            mask = np.random.randint(0, 2, (tile_size, tile_size), dtype=np.uint8)
            mask_path = os.path.join(tiles_mask_dir, f"tile_mask_{tile_index}.npy")
            np.save(mask_path, mask)
            valid_results.append({
                "tile_index": tile_index,
                "mask_path": mask_path,
                "offset_y": y,
                "offset_x": x,
                "tile_height": tile_h,
                "tile_width": tile_w,
            })
            tile_index += 1
        if tile_index >= 3:
            break

    logger.info(f"创建 {len(valid_results)} 个模拟 tile mask")

    # 合并
    service = UnsupervisedDiseaseDetectionService()
    success, global_mask, msg = service._merge_tile_masks(valid_results, H, W)
    assert success, f"合并失败: {msg}"
    assert global_mask.shape == (H, W), f"合并后尺寸不匹配: {global_mask.shape}"
    logger.info(f"合并成功: shape={global_mask.shape}")

    # 清理
    for result in valid_results:
        if os.path.exists(result["mask_path"]):
            os.remove(result["mask_path"])
    if os.path.exists(tiles_mask_dir) and not os.listdir(tiles_mask_dir):
        os.rmdir(tiles_mask_dir)
    logger.info("清理完成")


def test_merge_chunks_small():
    """测试 ImageChunkingService.merge_chunks: 只合并前 3 个 chunk"""
    logger.info("=" * 60)
    logger.info("测试3: merge_chunks (前3个chunk)")
    logger.info("=" * 60)

    H, W, C = 2048, 2048, 3
    chunk_w, chunk_h = 1024, 1024

    # 创建模拟 chunks
    chunks = []
    for i in range(3):
        chunk = np.random.randint(0, 255, (chunk_h, chunk_w, C), dtype=np.uint8)
        chunks.append(chunk)

    logger.info(f"创建 {len(chunks)} 个模拟 chunk")

    # 合并
    success, merged, msg = ImageChunkingService.merge_chunks(chunks, W, H, chunk_w, chunk_h)
    assert success, f"合并失败: {msg}"
    assert merged.shape == (H, W, C), f"合并后尺寸不匹配: {merged.shape}"
    logger.info(f"合并成功: shape={merged.shape}")


if __name__ == "__main__":
    test_merge_tiles_small()
    print()
    test_merge_tile_masks_small()
    print()
    test_merge_chunks_small()
    print()
    logger.info("所有 merge 测试通过!")
