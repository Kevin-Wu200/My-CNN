"""
流式持久化工具模块
用于将海量检测点位数据分批写入磁盘/数据库，避免百万级点位常驻内存造成系统不稳定。
"""

import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Iterator, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class StreamingPersistence:
    """流式持久化工具类：支持分批写入和分批读取"""

    # 默认批次大小（每批写入磁盘的点位数）
    DEFAULT_BATCH_SIZE = 5000

    @staticmethod
    def batch_write_geojson(
        points_iterator: Iterator[Dict],
        output_path: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
        crs: Optional[Dict] = None,
    ) -> int:
        """
        流式写入 GeoJSON：逐批接收检测点位，分批次追加写入文件。

        适用于超大影像检测场景（百万级点位），避免全部点位常驻内存。

        Args:
            points_iterator: 点位生成器/迭代器，每次 yield 一个点位字典
            output_path: 输出 GeoJSON 文件路径
            batch_size: 每批次写入磁盘的点位数量
            crs: 坐标参考系（可选）

        Returns:
            写入的总点位数
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        batch = []
        total_count = 0
        first_batch = True

        start_time = time.time()

        for point in points_iterator:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [point.get("x", 0), point.get("y", 0)],
                },
                "properties": {
                    k: v for k, v in point.items() if k not in ("x", "y")
                },
            }
            batch.append(feature)

            if len(batch) >= batch_size:
                StreamingPersistence._flush_geojson_batch(
                    output, batch, first_batch, crs
                )
                total_count += len(batch)
                first_batch = False

                if total_count % (batch_size * 10) == 0:
                    elapsed = time.time() - start_time
                    logger.info(
                        f"[STREAMING_PERSIST] 已写入 {total_count} 个点位, "
                        f"耗时={elapsed:.1f}s, 速率={total_count / elapsed:.0f} pts/s"
                    )

                batch = []

        # 写入最后一批
        if batch:
            StreamingPersistence._flush_geojson_batch(
                output, batch, first_batch, crs
            )
            total_count += len(batch)

        elapsed = time.time() - start_time
        logger.info(
            f"[STREAMING_PERSIST_COMPLETE] 共写入 {total_count} 个点位, "
            f"文件={output_path}, 总耗时={elapsed:.1f}s"
        )

        return total_count

    @staticmethod
    def _flush_geojson_batch(
        output_path: Path,
        features: List[Dict],
        is_first: bool,
        crs: Optional[Dict] = None,
    ) -> None:
        """
        将一批 Feature 写入 GeoJSON 文件。

        Args:
            output_path: 输出文件路径
            features: Feature 列表
            is_first: 是否是第一批（需要写入文件头）
            crs: 坐标参考系
        """
        if is_first:
            # 第一批：写入完整的 GeoJSON 结构（开括号）
            with open(output_path, "w", encoding="utf-8") as f:
                f.write('{\n  "type": "FeatureCollection",\n')
                if crs:
                    crs_str = json.dumps(crs, indent=2)
                    f.write(f'  "crs": {crs_str},\n')
                f.write('  "features": [\n')

                for i, feature in enumerate(features):
                    if i > 0:
                        f.write(",\n")
                    json.dump(feature, f, indent=4)

            # 记录当前文件大小
            file_size = output_path.stat().st_size
            logger.debug(
                f"[GEOJSON_BATCH_FLUSH] first_batch, features={len(features)}, "
                f"fileSize={file_size}"
            )
        else:
            # 后续批次：追加 Feature
            with open(output_path, "a", encoding="utf-8") as f:
                for feature in features:
                    f.write(",\n")
                    json.dump(feature, f, indent=4)

    @staticmethod
    def finalize_geojson(output_path: str) -> bool:
        """
        完成 GeoJSON 文件写入（添加闭合括号）。

        Args:
            output_path: GeoJSON 文件路径

        Returns:
            是否成功
        """
        try:
            output = Path(output_path)
            if not output.exists():
                logger.warning(f"[GEOJSON_FINALIZE] 文件不存在: {output_path}")
                return False

            with open(output_path, "a", encoding="utf-8") as f:
                f.write("\n  ]\n}\n")

            file_size = output.stat().st_size
            logger.info(
                f"[GEOJSON_FINALIZED] path={output_path}, fileSize={file_size}"
            )
            return True

        except Exception as e:
            logger.error(f"[GEOJSON_FINALIZE_ERROR] path={output_path}, error={str(e)}")
            return False

    @staticmethod
    def batch_write_csv(
        points_iterator: Iterator[Dict],
        output_path: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
        columns: Optional[List[str]] = None,
    ) -> int:
        """
        流式写入 CSV：逐批接收检测点位，分批次追加写入 CSV 文件。

        Args:
            points_iterator: 点位生成器/迭代器
            output_path: 输出 CSV 文件路径
            batch_size: 每批次写入磁盘的点位数量
            columns: 指定列顺序（可选，默认从第一批点位自动推断）

        Returns:
            写入的总点位数
        """
        import csv

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        batch = []
        total_count = 0
        start_time = time.time()
        first_batch = True

        for point in points_iterator:
            batch.append(point)

            if len(batch) >= batch_size:
                StreamingPersistence._flush_csv_batch(
                    output, batch, first_batch, columns
                )
                total_count += len(batch)
                first_batch = False

                if total_count % (batch_size * 10) == 0:
                    elapsed = time.time() - start_time
                    logger.info(
                        f"[STREAMING_CSV] 已写入 {total_count} 个点位, "
                        f"耗时={elapsed:.1f}s"
                    )

                batch = []

        if batch:
            StreamingPersistence._flush_csv_batch(
                output, batch, first_batch, columns
            )
            total_count += len(batch)

        elapsed = time.time() - start_time
        logger.info(
            f"[STREAMING_CSV_COMPLETE] 共写入 {total_count} 个点位, "
            f"文件={output_path}, 总耗时={elapsed:.1f}s"
        )

        return total_count

    @staticmethod
    def _flush_csv_batch(
        output_path: Path,
        points: List[Dict],
        is_first: bool,
        columns: Optional[List[str]] = None,
    ) -> None:
        """将一批点位写入 CSV 文件"""
        import csv

        if not points:
            return

        if columns is None:
            columns = list(points[0].keys())

        mode = "w" if is_first else "a"
        with open(output_path, mode, newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            if is_first:
                writer.writeheader()
            writer.writerows(points)
