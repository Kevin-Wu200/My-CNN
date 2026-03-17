"""
影像分块服务模块
用于按指定块大小读取和处理 IMG 遥感影像
"""

import numpy as np
from pathlib import Path
from typing import Tuple, Optional, List, Dict, NamedTuple
import logging

from backend.utils.image_reader import ImageReader
from backend.utils.resource_monitor import ResourceMonitor

logger = logging.getLogger(__name__)


class ChunkParameters(NamedTuple):
    """影像分块参数结构体"""

    chunk_width: int  # 块宽度（像素）
    chunk_height: int  # 块高度（像素）
    chunk_index: int  # 块索引


class ImageChunkingService:
    """影像分块服务类"""

    @staticmethod
    def generate_chunk_tasks(
        image_width: int,
        image_height: int,
        chunk_width: int,
        chunk_height: int,
    ) -> Tuple[bool, Optional[List[ChunkParameters]], str]:
        """
        生成影像分块任务列表

        根据影像尺寸和块大小参数生成分块任务列表

        Args:
            image_width: 影像宽度
            image_height: 影像高度
            chunk_width: 块宽度
            chunk_height: 块高度

        Returns:
            (生成是否成功, 分块参数列表, 错误信息或成功消息)
        """
        try:
            if image_width <= 0 or image_height <= 0:
                return False, None, "影像尺寸无效"

            if chunk_width <= 0 or chunk_height <= 0:
                return False, None, "块大小无效"

            chunk_tasks = []
            chunk_index = 0

            # 按行列生成分块任务
            for y in range(0, image_height, chunk_height):
                for x in range(0, image_width, chunk_width):
                    chunk_tasks.append(
                        ChunkParameters(
                            chunk_width=chunk_width,
                            chunk_height=chunk_height,
                            chunk_index=chunk_index,
                        )
                    )
                    chunk_index += 1

            logger.info(
                f"已生成 {len(chunk_tasks)} 个分块任务: "
                f"影像尺寸={image_width}x{image_height}, "
                f"块大小={chunk_width}x{chunk_height}"
            )

            return True, chunk_tasks, "分块任务生成成功"

        except Exception as e:
            logger.error(f"生成分块任务失败: {str(e)}")
            return False, None, f"生成分块任务失败: {str(e)}"

    @staticmethod
    def read_image_chunk(
        image_path: str,
        chunk_x: int,
        chunk_y: int,
        chunk_width: int,
        chunk_height: int,
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        读取影像的单个块

        Args:
            image_path: 影像文件路径
            chunk_x: 块的起始 X 坐标
            chunk_y: 块的起始 Y 坐标
            chunk_width: 块的宽度
            chunk_height: 块的高度

        Returns:
            (读取是否成功, 影像块数据, 错误信息或成功消息)
        """
        try:
            # 使用 ImageReader 读取块
            success, chunk_data, message = ImageReader.read_image_chunk(
                image_path, chunk_x, chunk_y, chunk_width, chunk_height
            )

            return success, chunk_data, message

        except Exception as e:
            logger.error(f"读取影像块失败: {str(e)}")
            return False, None, f"读取影像块失败: {str(e)}"

    @staticmethod
    def process_chunk(
        chunk_data: np.ndarray,
        normalize: bool = True,
        band_indices: Optional[List[int]] = None,
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        处理单个影像块

        支持影像裁剪、归一化和波段选择操作

        Args:
            chunk_data: 影像块数据
            normalize: 是否进行归一化
            band_indices: 要选择的波段索引

        Returns:
            (处理是否成功, 处理后的块数据, 错误信息或成功消息)
        """
        try:
            if chunk_data is None or chunk_data.size == 0:
                return False, None, "影像块数据为空"

            processed_data = chunk_data.copy()

            # 波段选择
            if band_indices is not None:
                processed_data = processed_data[:, :, band_indices]

            # 归一化
            if normalize:
                from backend.services.image_processing import ImageProcessingService

                success, normalized_data, message = (
                    ImageProcessingService.normalize_image(processed_data)
                )
                if not success:
                    return False, None, message

                processed_data = normalized_data

            return True, processed_data, "块处理成功"

        except Exception as e:
            logger.error(f"块处理失败: {str(e)}")
            return False, None, f"块处理失败: {str(e)}"

    @staticmethod
    def merge_chunks(
        chunks: List[np.ndarray],
        image_width: int,
        image_height: int,
        chunk_width: int,
        chunk_height: int,
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        合并所有影像块为完整影像

        Args:
            chunks: 影像块列表
            image_width: 原始影像宽度
            image_height: 原始影像高度
            chunk_width: 块宽度
            chunk_height: 块高度

        Returns:
            (合并是否成功, 合并后的影像, 错误信息或成功消息)
        """
        import sys
        import time as _time

        try:
            logger.info("开始执行图像合并 (merge_chunks)")
            merge_start = _time.time()

            if not chunks or len(chunks) == 0:
                return False, None, "影像块列表为空"

            logger.info(f"chunk count: {len(chunks)}")
            logger.info(f"output size: {image_width}x{image_height}, chunk_size={chunk_width}x{chunk_height}")

            logger.info(f"检查 chunks 内容: {len(chunks)} 个")
            invalid_chunks = [i for i, c in enumerate(chunks) if c is None or c.size == 0]
            if invalid_chunks:
                logger.error(f"chunks contains invalid entries at indices: {invalid_chunks}")

            chunk_dtypes = set()
            chunk_bands = set()
            for i, chunk in enumerate(chunks):
                chunk_dtypes.add(str(chunk.dtype))
                chunk_bands.add(chunk.shape[2] if len(chunk.shape) == 3 else 1)
            if len(chunk_dtypes) > 1:
                logger.warning(f"chunk dtype 不一致: {chunk_dtypes}")
            if len(chunk_bands) > 1:
                logger.warning(f"chunk 波段数不一致: {chunk_bands}")

            # 获取通道数
            num_channels = chunks[0].shape[2]

            logger.info(f"output_width={image_width}, output_height={image_height}, num_channels={num_channels}")

            # 初始化合并后的影像
            dtype = chunks[0].dtype
            estimated_size = image_height * image_width * num_channels * np.dtype(dtype).itemsize
            memory_info = ResourceMonitor.get_memory_usage()
            available_memory = memory_info['available'] * 1024 * 1024  # MB -> bytes
            logger.info(
                f"内存检查: 可用={available_memory/1024/1024:.1f}MB, "
                f"需要={estimated_size/1024/1024:.1f}MB"
            )
            if estimated_size > available_memory * 0.8:
                error_msg = (
                    f"内存不足: 需要 {estimated_size/1024/1024:.1f}MB, "
                    f"可用 {available_memory/1024/1024:.1f}MB (使用率超过80%)"
                )
                logger.error(error_msg)
                return False, None, error_msg

            merged_image = np.zeros(
                (image_height, image_width, num_channels),
                dtype=chunks[0].dtype,
            )

            logger.info(f"merged_image.nbytes={merged_image.nbytes} ({merged_image.nbytes / 1024 / 1024:.1f} MB)")
            if merged_image.nbytes > 2 * 1024 * 1024 * 1024:
                logger.warning("merged_image 超过 2GB，可能导致内存问题")

            # 合并块
            chunk_idx = 0
            total_chunks = len(chunks)
            log_interval = max(1, total_chunks // 20)  # 最多输出20次进度日志
            for y in range(0, image_height, chunk_height):
                for x in range(0, image_width, chunk_width):
                    if chunk_idx >= len(chunks):
                        break

                    chunk = chunks[chunk_idx]

                    # 只在关键节点输出日志
                    if chunk_idx % log_interval == 0 or chunk_idx == total_chunks - 1:
                        progress = int((chunk_idx + 1) / total_chunks * 100)
                        logger.info(f"合并进度: {chunk_idx+1}/{total_chunks} ({progress}%)")

                    # 计算实际的块大小（边界处可能更小）
                    actual_height = min(chunk_height, image_height - y)
                    actual_width = min(chunk_width, image_width - x)

                    # 确保 chunk 不超出目标图边界
                    if y + actual_height > image_height or x + actual_width > image_width:
                        logger.error(
                            f"chunk {chunk_idx} 超出目标图边界: "
                            f"region=({y},{y+actual_height},{x},{x+actual_width}), "
                            f"target=({image_height},{image_width})"
                        )

                    # 将块放入合并后的影像
                    merged_image[y : y + actual_height, x : x + actual_width, :] = chunk[
                        :actual_height, :actual_width, :
                    ]

                    chunk_idx += 1

            logger.info(f"chunks 总大小: {sys.getsizeof(chunks)} bytes")

            merge_elapsed = _time.time() - merge_start
            logger.info(f"merge time: {merge_elapsed:.2f}s")

            if merge_elapsed > 300:
                logger.warning(f"merge taking too long: {merge_elapsed:.2f}s > 300s")

            logger.info(f"影像块合并完成: {len(chunks)} 个块")

            logger.info("图像合并完成")

            return True, merged_image, "块合并成功"

        except Exception as e:
            logger.exception(f"块合并失败: {e}")
            return False, None, f"块合并失败: {str(e)}"

    @staticmethod
    def validate_chunk_parameters(
        chunk_width: int,
        chunk_height: int,
        max_chunk_size: int = 2048,
    ) -> Tuple[bool, str]:
        """
        验证分块参数

        Args:
            chunk_width: 块宽度
            chunk_height: 块高度
            max_chunk_size: 最大块大小

        Returns:
            (验证是否通过, 错误信息或成功消息)
        """
        if chunk_width <= 0 or chunk_height <= 0:
            return False, "块大小必须为正数"

        if chunk_width > max_chunk_size or chunk_height > max_chunk_size:
            return False, f"块大小不能超过 {max_chunk_size} 像素"

        if chunk_width % 32 != 0 or chunk_height % 32 != 0:
            logger.warning("建议块大小为 32 的倍数以获得最佳性能")

        return True, "分块参数验证通过"
