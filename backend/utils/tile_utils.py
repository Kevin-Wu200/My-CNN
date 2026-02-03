"""
统一影像分块模块
用于对所有遥感影像进行统一的 1024×1024 分块处理
分块逻辑独立于具体算法，仅负责数据切分与索引管理
"""

import numpy as np
from pathlib import Path
from typing import Tuple, Optional, List, Dict, NamedTuple, Generator
import logging

logger = logging.getLogger(__name__)

# 系统默认分块尺寸
DEFAULT_TILE_SIZE = 1024


class TileInfo(NamedTuple):
    """分块信息结构体"""
    tile_index: int  # 分块全局索引
    row_index: int  # 分块行索引
    col_index: int  # 分块列索引
    offset_y: int  # 分块在原始影像中的 Y 偏移（像素）
    offset_x: int  # 分块在原始影像中的 X 偏移（像素）
    tile_height: int  # 分块实际高度
    tile_width: int  # 分块实际宽度
    is_padded: bool  # 是否进行了 padding


class Tile:
    """分块对象，包含影像数据和空间信息"""

    def __init__(
        self,
        data: np.ndarray,
        tile_info: TileInfo,
        spatial_ref: Optional[Dict] = None,
    ):
        """
        初始化分块对象

        Args:
            data: 分块影像数据 (H, W, C) 或 (H, W)
            tile_info: 分块信息
            spatial_ref: 空间参考信息（如投影、地理坐标等）
        """
        self.data = data
        self.tile_info = tile_info
        self.spatial_ref = spatial_ref or {}

    @property
    def tile_index(self) -> int:
        """获取分块全局索引"""
        return self.tile_info.tile_index

    @property
    def row_index(self) -> int:
        """获取分块行索引"""
        return self.tile_info.row_index

    @property
    def col_index(self) -> int:
        """获取分块列索引"""
        return self.tile_info.col_index

    @property
    def offset_y(self) -> int:
        """获取 Y 偏移"""
        return self.tile_info.offset_y

    @property
    def offset_x(self) -> int:
        """获取 X 偏移"""
        return self.tile_info.offset_x

    @property
    def height(self) -> int:
        """获取分块高度"""
        return self.data.shape[0]

    @property
    def width(self) -> int:
        """获取分块宽度"""
        return self.data.shape[1]

    @property
    def is_padded(self) -> bool:
        """是否进行了 padding"""
        return self.tile_info.is_padded

    def get_original_bounds(self) -> Tuple[int, int, int, int]:
        """
        获取分块在原始影像中的边界（不包括 padding 部分）

        Returns:
            (y_start, y_end, x_start, x_end)
        """
        y_start = self.offset_y
        x_start = self.offset_x
        y_end = y_start + self.tile_info.tile_height
        x_end = x_start + self.tile_info.tile_width
        return y_start, y_end, x_start, x_end

    def __repr__(self) -> str:
        return (
            f"Tile(index={self.tile_index}, "
            f"row={self.row_index}, col={self.col_index}, "
            f"offset=({self.offset_y}, {self.offset_x}), "
            f"size=({self.height}, {self.width}), "
            f"padded={self.is_padded})"
        )


class TilingService:
    """影像分块服务类"""

    @staticmethod
    def generate_tiles(
        image_data: np.ndarray,
        tile_size: int = DEFAULT_TILE_SIZE,
        padding_mode: str = "pad",
        spatial_ref: Optional[Dict] = None,
    ) -> Tuple[bool, Optional[List[Tile]], str]:
        """
        将影像分块为多个 Tile 对象

        Args:
            image_data: 影像数据 (H, W, C) 或 (H, W)
            tile_size: 分块尺寸（默认 1024×1024）
            padding_mode: 边缘处理方式
                - "pad": 对不足 tile_size 的边缘块进行 padding
                - "crop": 对不足 tile_size 的边缘块进行裁剪
            spatial_ref: 空间参考信息

        Returns:
            (生成是否成功, Tile 对象列表, 错误信息或成功消息)
        """
        try:
            if image_data is None or image_data.size == 0:
                return False, None, "影像数据为空"

            if tile_size <= 0:
                return False, None, "分块尺寸必须为正数"

            if padding_mode not in ["pad", "crop"]:
                return False, None, "padding_mode 必须为 'pad' 或 'crop'"

            image_height, image_width = image_data.shape[:2]
            tiles = []
            tile_index = 0

            # 按行列顺序生成分块
            for row_idx, y in enumerate(range(0, image_height, tile_size)):
                for col_idx, x in enumerate(range(0, image_width, tile_size)):
                    # 计算分块的实际尺寸
                    actual_height = min(tile_size, image_height - y)
                    actual_width = min(tile_size, image_width - x)

                    # 提取分块数据
                    tile_data = image_data[y : y + actual_height, x : x + actual_width]

                    is_padded = False

                    # 处理边缘块
                    if actual_height < tile_size or actual_width < tile_size:
                        if padding_mode == "pad":
                            # Padding 处理
                            pad_height = tile_size - actual_height
                            pad_width = tile_size - actual_width

                            if len(tile_data.shape) == 3:
                                # 多波段影像
                                pad_width_tuple = (
                                    (0, pad_height),
                                    (0, pad_width),
                                    (0, 0),
                                )
                            else:
                                # 单波段影像
                                pad_width_tuple = ((0, pad_height), (0, pad_width))

                            tile_data = np.pad(
                                tile_data, pad_width_tuple, mode="edge"
                            )
                            is_padded = True
                        else:
                            # crop 模式：跳过不足 tile_size 的边缘块
                            if actual_height < tile_size or actual_width < tile_size:
                                continue

                    # 创建 TileInfo
                    tile_info = TileInfo(
                        tile_index=tile_index,
                        row_index=row_idx,
                        col_index=col_idx,
                        offset_y=y,
                        offset_x=x,
                        tile_height=actual_height,
                        tile_width=actual_width,
                        is_padded=is_padded,
                    )

                    # 创建 Tile 对象
                    tile = Tile(tile_data, tile_info, spatial_ref)
                    tiles.append(tile)
                    tile_index += 1

            logger.info(
                f"影像分块完成: 影像尺寸={image_width}x{image_height}, "
                f"分块尺寸={tile_size}x{tile_size}, "
                f"分块数={len(tiles)}, "
                f"padding_mode={padding_mode}"
            )

            return True, tiles, "影像分块成功"

        except Exception as e:
            logger.error(f"影像分块失败: {str(e)}")
            return False, None, f"影像分块失败: {str(e)}"

    @staticmethod
    def generate_tiles_generator(
        image_data: np.ndarray,
        tile_size: int = DEFAULT_TILE_SIZE,
        padding_mode: str = "pad",
        spatial_ref: Optional[Dict] = None,
    ) -> Generator[Tile, None, Tuple[bool, str]]:
        """
        以生成器形式返回分块（适合大影像，节省内存）

        Args:
            image_data: 影像数据 (H, W, C) 或 (H, W)
            tile_size: 分块尺寸（默认 1024×1024）
            padding_mode: 边缘处理方式
            spatial_ref: 空间参考信息

        Yields:
            Tile 对象

        Returns:
            (生成是否成功, 错误信息或成功消息)
        """
        try:
            if image_data is None or image_data.size == 0:
                return False, "影像数据为空"

            if tile_size <= 0:
                return False, "分块尺寸必须为正数"

            if padding_mode not in ["pad", "crop"]:
                return False, "padding_mode 必须为 'pad' 或 'crop'"

            image_height, image_width = image_data.shape[:2]
            tile_index = 0

            # 按行列顺序生成分块
            for row_idx, y in enumerate(range(0, image_height, tile_size)):
                for col_idx, x in enumerate(range(0, image_width, tile_size)):
                    # 计算分块的实际尺寸
                    actual_height = min(tile_size, image_height - y)
                    actual_width = min(tile_size, image_width - x)

                    # 提取分块数据
                    tile_data = image_data[y : y + actual_height, x : x + actual_width]

                    is_padded = False

                    # 处理边缘块
                    if actual_height < tile_size or actual_width < tile_size:
                        if padding_mode == "pad":
                            # Padding 处理
                            pad_height = tile_size - actual_height
                            pad_width = tile_size - actual_width

                            if len(tile_data.shape) == 3:
                                # 多波段影像
                                pad_width_tuple = (
                                    (0, pad_height),
                                    (0, pad_width),
                                    (0, 0),
                                )
                            else:
                                # 单波段影像
                                pad_width_tuple = ((0, pad_height), (0, pad_width))

                            tile_data = np.pad(
                                tile_data, pad_width_tuple, mode="edge"
                            )
                            is_padded = True
                        else:
                            # crop 模式：跳过不足 tile_size 的边缘块
                            if actual_height < tile_size or actual_width < tile_size:
                                continue

                    # 创建 TileInfo
                    tile_info = TileInfo(
                        tile_index=tile_index,
                        row_index=row_idx,
                        col_index=col_idx,
                        offset_y=y,
                        offset_x=x,
                        tile_height=actual_height,
                        tile_width=actual_width,
                        is_padded=is_padded,
                    )

                    # 创建 Tile 对象
                    tile = Tile(tile_data, tile_info, spatial_ref)
                    yield tile
                    tile_index += 1

            logger.info(
                f"影像分块生成完成: 影像尺寸={image_width}x{image_height}, "
                f"分块尺寸={tile_size}x{tile_size}, "
                f"padding_mode={padding_mode}"
            )
            return True, "影像分块生成成功"

        except Exception as e:
            logger.error(f"影像分块生成失败: {str(e)}")
            return False, f"影像分块生成失败: {str(e)}"

    @staticmethod
    def merge_tiles(
        tiles: List[Tile],
        image_height: int,
        image_width: int,
        tile_size: int = DEFAULT_TILE_SIZE,
    ) -> Tuple[bool, Optional[np.ndarray], str]:
        """
        将处理后的分块合并回原始影像尺寸

        Args:
            tiles: 处理后的 Tile 对象列表
            image_height: 原始影像高度
            image_width: 原始影像宽度
            tile_size: 分块尺寸

        Returns:
            (合并是否成功, 合并后的影像, 错误信息或成功消息)
        """
        try:
            if not tiles or len(tiles) == 0:
                return False, None, "分块列表为空"

            # 获取通道数
            num_channels = tiles[0].data.shape[2] if len(tiles[0].data.shape) == 3 else 1

            # 初始化合并后的影像
            if num_channels == 1:
                merged_image = np.zeros(
                    (image_height, image_width),
                    dtype=tiles[0].data.dtype,
                )
            else:
                merged_image = np.zeros(
                    (image_height, image_width, num_channels),
                    dtype=tiles[0].data.dtype,
                )

            # 合并分块
            for tile in tiles:
                y_start, y_end, x_start, x_end = tile.get_original_bounds()

                # 获取分块的有效数据部分（去除 padding）
                if tile.is_padded:
                    tile_data = tile.data[
                        : tile.tile_info.tile_height,
                        : tile.tile_info.tile_width,
                    ]
                else:
                    tile_data = tile.data

                # 将分块数据放入合并后的影像
                if num_channels == 1:
                    merged_image[y_start:y_end, x_start:x_end] = tile_data
                else:
                    merged_image[y_start:y_end, x_start:x_end, :] = tile_data

            logger.info(
                f"分块合并完成: {len(tiles)} 个分块, "
                f"合并后影像尺寸={image_width}x{image_height}"
            )

            return True, merged_image, "分块合并成功"

        except Exception as e:
            logger.error(f"分块合并失败: {str(e)}")
            return False, None, f"分块合并失败: {str(e)}"

    @staticmethod
    def validate_tile_size(tile_size: int = DEFAULT_TILE_SIZE) -> Tuple[bool, str]:
        """
        验证分块尺寸

        Args:
            tile_size: 分块尺寸

        Returns:
            (验证是否通过, 错误信息或成功消息)
        """
        if tile_size <= 0:
            return False, "分块尺寸必须为正数"

        if tile_size != DEFAULT_TILE_SIZE:
            logger.warning(
                f"分块尺寸 ({tile_size}) 与系统默认值 ({DEFAULT_TILE_SIZE}) 不同"
            )

        return True, "分块尺寸验证通过"
