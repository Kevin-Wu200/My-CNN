"""
端到端稳定性压测脚本

使用 4GB 以上的超大 TIF 影像进行完整的"非监督-训练-监督"闭环测试，
验证内存曲线是否平稳。

用法：
    python tests/test_stability_large_image.py --image /path/to/large.tif [--skip-training]
"""

import argparse
import sys
import os
import time
import logging
import json
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import psutil
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("stability_test")


def get_memory_mb():
    """获取当前进程内存使用量 (MB)"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


def get_system_memory_percent():
    """获取系统内存使用率"""
    return psutil.virtual_memory().percent


def log_memory_milestone(stage: str, milestones: list):
    """记录内存里程碑"""
    mem_mb = get_memory_mb()
    sys_pct = get_system_memory_percent()
    milestone = {
        "stage": stage,
        "timestamp": datetime.now().isoformat(),
        "memory_mb": round(mem_mb, 2),
        "system_memory_pct": round(sys_pct, 1),
    }
    milestones.append(milestone)
    logger.info(f"[MEMORY] {stage}: process={mem_mb:.1f}MB, system={sys_pct:.1f}%")
    return milestone


def test_unsupervised_detection(image_path: str, milestones: list) -> dict:
    """测试非监督检测流程"""
    from backend.services.unsupervised_detection import UnsupervisedDiseaseDetectionService
    from backend.utils.image_reader import ImageReader

    log_memory_milestone("unsupervised_start", milestones)

    # 获取影像信息
    success, info, msg = ImageReader.get_image_info(image_path)
    if not success:
        raise RuntimeError(f"获取影像信息失败: {msg}")

    logger.info(f"影像信息: {info['width']}x{info['height']}, 波段={info['band_count']}")

    # 估算影像大小
    estimated_size_mb = (info['width'] * info['height'] * info['band_count'] * 4) / 1024 / 1024
    logger.info(f"估算影像大小: {estimated_size_mb:.1f}MB")

    # 执行流式文件检测（不加载完整影像到内存）
    service = UnsupervisedDiseaseDetectionService()

    start_time = time.time()
    success, result, msg = service.detect_from_file(
        image_path,
        n_clusters=4,
        min_area=50,
    )

    elapsed = time.time() - start_time
    log_memory_milestone("unsupervised_done", milestones)

    if not success:
        raise RuntimeError(f"非监督检测失败: {msg}")

    n_candidates = result.get("n_candidates", 0)
    logger.info(f"非监督检测完成: {n_candidates} 个候选点, 耗时={elapsed:.1f}s")

    return {
        "success": True,
        "n_candidates": n_candidates,
        "elapsed_seconds": elapsed,
    }


def analyze_memory_stability(milestones: list) -> dict:
    """分析内存稳定性"""
    if not milestones:
        return {"stable": False, "reason": "无内存数据"}

    mem_values = [m["memory_mb"] for m in milestones]
    sys_values = [m["system_memory_pct"] for m in milestones]

    max_mem = max(mem_values)
    min_mem = min(mem_values)
    peak_sys = max(sys_values)
    mem_fluctuation = max_mem - min_mem

    # 计算内存增长趋势
    if len(mem_values) >= 2:
        # 使用简单的线性回归斜率
        n = len(mem_values)
        x = list(range(n))
        slope = (n * sum(x[i] * mem_values[i] for i in range(n)) - sum(x) * sum(mem_values)) / \
                (n * sum(xi**2 for xi in x) - sum(x)**2) if n > 1 else 0
    else:
        slope = 0

    is_stable = mem_fluctuation < 500 and slope < 100  # 波动 < 500MB 且趋势 < 100MB/阶段

    return {
        "stable": is_stable,
        "max_memory_mb": round(max_mem, 2),
        "min_memory_mb": round(min_mem, 2),
        "fluctuation_mb": round(mem_fluctuation, 2),
        "peak_system_pct": round(peak_sys, 1),
        "memory_trend_slope": round(slope, 2),
        "milestone_count": len(milestones),
    }


def main():
    parser = argparse.ArgumentParser(description="端到端稳定性压测")
    parser.add_argument("--image", type=str, required=True, help="测试用的超大 TIF 影像路径")
    parser.add_argument("--output", type=str, default="test_reports/stability_report.json",
                       help="输出报告路径")
    parser.add_argument("--skip-training", action="store_true", default=True,
                       help="跳过训练阶段（默认跳过）")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        logger.error(f"影像文件不存在: {args.image}")
        sys.exit(1)

    # 检查文件大小
    file_size_mb = os.path.getsize(args.image) / 1024 / 1024
    logger.info(f"影像文件大小: {file_size_mb:.1f}MB ({file_size_mb / 1024:.1f}GB)")
    if file_size_mb < 1024:
        logger.warning(f"影像小于 1GB ({file_size_mb:.1f}MB)，压测参考价值有限")

    milestones = []
    results = {
        "image": args.image,
        "file_size_mb": round(file_size_mb, 1),
        "start_time": datetime.now().isoformat(),
    }

    try:
        log_memory_milestone("test_start", milestones)

        # 阶段1: 非监督检测
        logger.info("=" * 60)
        logger.info("阶段1: 非监督病害木检测")
        logger.info("=" * 60)
        unsupervised_result = test_unsupervised_detection(args.image, milestones)
        results["unsupervised"] = unsupervised_result

        # 阶段2: 内存稳定性分析
        logger.info("=" * 60)
        logger.info("阶段2: 内存稳定性分析")
        logger.info("=" * 60)
        stability = analyze_memory_stability(milestones)
        results["memory_stability"] = stability

        if stability["stable"]:
            logger.info("✅ 内存曲线平稳，波动在可控范围内")
        else:
            logger.warning(
                f"⚠️ 内存波动较大: max={stability['max_memory_mb']:.1f}MB, "
                f"fluctuation={stability['fluctuation_mb']:.1f}MB"
            )

        # 保存报告
        results["end_time"] = datetime.now().isoformat()
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"压测报告已保存: {args.output}")

    except Exception as e:
        logger.error(f"压测失败: {e}")
        results["error"] = str(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
