"""
验证服务模块
用于验证训练样本的完整性和格式正确性
"""

import json
import re
from pathlib import Path
from typing import Tuple, List, Dict
import logging

logger = logging.getLogger(__name__)


class ValidationService:
    """训练样本验证服务类"""

    # 支持的影像格式（训练样本）
    SUPPORTED_IMAGE_FORMATS = {".img", ".tif", ".tiff"}
    # 支持的检测影像格式
    SUPPORTED_DETECTION_FORMATS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    # GeoJSON 文件扩展名
    GEOJSON_EXTENSION = ".geojson"

    @staticmethod
    def validate_training_sample(extract_dir: Path) -> Tuple[bool, str, Dict]:
        """
        验证训练样本的完整性

        Args:
            extract_dir: 解压后的目录路径

        Returns:
            (验证是否通过, 错误信息或成功消息, 验证结果详情)
        """
        result = {
            "image_files": [],
            "geojson_file": None,
            "errors": [],
        }

        # 获取所有文件
        all_files = list(extract_dir.rglob("*"))
        files = [f for f in all_files if f.is_file()]

        if not files:
            return False, "解压目录中没有找到任何文件", result

        # 检查影像文件
        image_files = ValidationService._validate_image_files(files, result)
        if not image_files:
            error_msg = "未找到有效的影像文件（支持 img、tif、tiff 格式）"
            result["errors"].append(error_msg)
            return False, error_msg, result

        # 检查影像文件命名连续性
        naming_valid, naming_error = ValidationService._validate_image_naming(
            image_files
        )
        if not naming_valid:
            result["errors"].append(naming_error)
            return False, naming_error, result

        # 检查 GeoJSON 文件
        geojson_file = ValidationService._validate_geojson_file(files, result)
        if not geojson_file:
            error_msg = "未找到 GeoJSON 文件"
            result["errors"].append(error_msg)
            return False, error_msg, result

        # 验证 GeoJSON 文件格式
        geojson_valid, geojson_error = ValidationService._validate_geojson_format(
            geojson_file
        )
        if not geojson_valid:
            result["errors"].append(geojson_error)
            return False, geojson_error, result

        result["image_files"] = [str(f) for f in image_files]
        result["geojson_file"] = str(geojson_file)

        return True, "训练样本验证通过", result

    @staticmethod
    def _validate_image_files(
        files: List[Path], result: Dict
    ) -> List[Path]:
        """
        验证并收集影像文件

        Args:
            files: 文件列表
            result: 结果字典

        Returns:
            有效的影像文件列表
        """
        image_files = []

        for file_path in files:
            # 检查文件扩展名
            if file_path.suffix.lower() not in ValidationService.SUPPORTED_IMAGE_FORMATS:
                continue

            # 检查文件大小（至少 1KB）
            if file_path.stat().st_size < 1024:
                result["errors"].append(
                    f"影像文件过小（可能损坏）: {file_path.name}"
                )
                continue

            image_files.append(file_path)

        return sorted(image_files, key=lambda x: x.name)

    @staticmethod
    def _validate_image_naming(image_files: List[Path]) -> Tuple[bool, str]:
        """
        验证影像文件命名的连续性

        Args:
            image_files: 影像文件列表

        Returns:
            (验证是否通过, 错误信息)
        """
        if not image_files:
            return False, "没有找到影像文件"

        # 提取文件名中的数字
        numbers = []
        for file_path in image_files:
            # 从文件名中提取数字（如 1.img, 2.img, 3.img）
            match = re.match(r"(\d+)", file_path.stem)
            if not match:
                return False, f"影像文件命名格式不符合要求: {file_path.name}（应为数字开头）"

            numbers.append(int(match.group(1)))

        # 检查数字是否连续
        numbers.sort()
        for i in range(len(numbers) - 1):
            if numbers[i + 1] - numbers[i] != 1:
                return (
                    False,
                    f"影像文件命名不连续: 期望 {numbers[i] + 1}，但找到 {numbers[i + 1]}",
                )

        return True, "影像文件命名连续"

    @staticmethod
    def _validate_geojson_file(files: List[Path], result: Dict) -> Path:
        """
        查找并验证 GeoJSON 文件

        Args:
            files: 文件列表
            result: 结果字典

        Returns:
            GeoJSON 文件路径，如果不存在则返回 None
        """
        for file_path in files:
            if file_path.suffix.lower() == ValidationService.GEOJSON_EXTENSION:
                return file_path

        return None

    @staticmethod
    def _validate_geojson_format(geojson_path: Path) -> Tuple[bool, str]:
        """
        验证 GeoJSON 文件格式

        Args:
            geojson_path: GeoJSON 文件路径

        Returns:
            (验证是否通过, 错误信息或成功消息)
        """
        try:
            with open(geojson_path, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)

            # 检查必要的字段
            if "type" not in geojson_data:
                return False, "GeoJSON 缺少 'type' 字段"

            if geojson_data["type"] not in ["FeatureCollection", "Feature"]:
                return False, f"不支持的 GeoJSON 类型: {geojson_data['type']}"

            # 如果是 FeatureCollection，检查 features 字段
            if geojson_data["type"] == "FeatureCollection":
                if "features" not in geojson_data:
                    return False, "FeatureCollection 缺少 'features' 字段"

                if not isinstance(geojson_data["features"], list):
                    return False, "'features' 必须是数组"

                if len(geojson_data["features"]) == 0:
                    return False, "GeoJSON 中没有任何特征点"

            return True, "GeoJSON 格式验证通过"

        except json.JSONDecodeError as e:
            return False, f"GeoJSON 格式错误: {str(e)}"
        except Exception as e:
            return False, f"验证 GeoJSON 时出错: {str(e)}"

    @staticmethod
    def validate_detection_images(extract_dir: Path) -> Tuple[bool, str, Dict]:
        """
        验证待检测影像（不要求 GeoJSON）

        Args:
            extract_dir: 解压后的目录路径

        Returns:
            (验证是否通过, 错误信息或成功消息, 验证结果详情)
        """
        result = {
            "image_files": [],
            "errors": [],
        }

        # 获取所有文件
        all_files = list(extract_dir.rglob("*"))
        files = [f for f in all_files if f.is_file()]

        if not files:
            return False, "解压目录中没有找到任何文件", result

        # 检查影像文件
        image_files = ValidationService._validate_detection_image_files(files, result)
        if not image_files:
            error_msg = "未找到有效的影像文件（支持 jpg、jpeg、png、tif、tiff 格式）"
            result["errors"].append(error_msg)
            return False, error_msg, result

        result["image_files"] = [str(f) for f in image_files]

        return True, "待检测影像验证通过", result

    @staticmethod
    def _validate_detection_image_files(
        files: List[Path], result: Dict
    ) -> List[Path]:
        """
        验证并收集检测影像文件

        Args:
            files: 文件列表
            result: 结果字典

        Returns:
            有效的影像文件列表
        """
        image_files = []

        for file_path in files:
            # 检查文件扩展名
            if file_path.suffix.lower() not in ValidationService.SUPPORTED_DETECTION_FORMATS:
                continue

            # 检查文件大小（至少 1KB）
            if file_path.stat().st_size < 1024:
                result["errors"].append(
                    f"影像文件过小（可能损坏）: {file_path.name}"
                )
                continue

            image_files.append(file_path)

        return sorted(image_files, key=lambda x: x.name)
