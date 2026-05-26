"""
召回率对比实验脚本

针对非监督分类参数调整前后的候选点数量进行量化对比，
确保病害木样本捕获率提升。

用法：
    python tests/test_recall_comparison.py --image /path/to/image.tif [--output report.json]
"""

import argparse
import sys
import os
import time
import logging
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("recall_comparison")


def run_detection(image_path: str, mode: str, **kwargs) -> dict:
    """
    运行一次检测并返回结果。

    Args:
        image_path: 影像文件路径
        mode: 检测模式标识
        **kwargs: 传递给 detect_from_file 的额外参数
    """
    from backend.services.unsupervised_detection import UnsupervisedDiseaseDetectionService

    service = UnsupervisedDiseaseDetectionService()

    start_time = time.time()
    success, result, msg = service.detect_from_file(
        image_path,
        n_clusters=kwargs.get("n_clusters", 4),
        min_area=kwargs.get("min_area", 50),
        r_threshold_factor=kwargs.get("r_threshold_factor"),
        g_threshold_factor=kwargs.get("g_threshold_factor"),
        contrast_threshold_factor=kwargs.get("contrast_threshold_factor"),
    )
    elapsed = time.time() - start_time

    if not success:
        return {"mode": mode, "success": False, "error": msg, "elapsed_seconds": elapsed}

    return {
        "mode": mode,
        "success": True,
        "n_candidates": result.get("n_candidates", 0),
        "n_tiles": result.get("n_tiles", 0),
        "n_successful_tiles": result.get("n_successful_tiles", 0),
        "elapsed_seconds": elapsed,
    }


def compare_results(baseline: dict, enhanced: dict) -> dict:
    """对比两组检测结果"""
    if not baseline.get("success") or not enhanced.get("success"):
        return {"error": "检测未全部成功，无法对比"}

    n_baseline = baseline["n_candidates"]
    n_enhanced = enhanced["n_candidates"]

    if n_baseline > 0:
        change_pct = (n_enhanced - n_baseline) / n_baseline * 100
    else:
        change_pct = float('inf') if n_enhanced > 0 else 0

    return {
        "baseline_candidates": n_baseline,
        "enhanced_candidates": n_enhanced,
        "absolute_change": n_enhanced - n_baseline,
        "relative_change_pct": round(change_pct, 2),
        "baseline_elapsed": baseline["elapsed_seconds"],
        "enhanced_elapsed": enhanced["elapsed_seconds"],
        "speed_ratio": round(baseline["elapsed_seconds"] / enhanced["elapsed_seconds"], 2) if enhanced["elapsed_seconds"] > 0 else None,
    }


def main():
    parser = argparse.ArgumentParser(description="召回率对比实验")
    parser.add_argument("--image", type=str, required=True, help="测试影像路径")
    parser.add_argument("--output", type=str, default="test_reports/recall_report.json",
                       help="输出报告路径")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        logger.error(f"影像文件不存在: {args.image}")
        sys.exit(1)

    logger.info(f"开始召回率对比实验: {args.image}")

    results = {
        "image": args.image,
        "file_size_mb": round(os.path.getsize(args.image) / 1024 / 1024, 1),
    }

    # 实验组1: 原始硬编码阈值模式（baseline）
    logger.info("=" * 50)
    logger.info("实验组1 (Baseline): 硬编码阈值模式 (R>1.1*mean, G<0.9*mean, Contrast>1.1*mean)")
    logger.info("=" * 50)
    baseline = run_detection(
        args.image, "baseline_hardcoded",
        r_threshold_factor=1.1,
        g_threshold_factor=0.9,
        contrast_threshold_factor=1.1,
    )
    results["baseline"] = baseline
    logger.info(f"Baseline 结果: {baseline.get('n_candidates', 0)} 个候选点, 耗时={baseline.get('elapsed_seconds', 0):.1f}s")

    # 实验组2: 动态分位数阈值模式（enhanced）
    logger.info("=" * 50)
    logger.info("实验组2 (Enhanced): 动态分位数阈值模式 (P75/P25)")
    logger.info("=" * 50)
    enhanced = run_detection(
        args.image, "enhanced_dynamic",
        r_threshold_factor=None,  # None = 动态分位数模式
        g_threshold_factor=None,
        contrast_threshold_factor=None,
    )
    results["enhanced"] = enhanced
    logger.info(f"Enhanced 结果: {enhanced.get('n_candidates', 0)} 个候选点, 耗时={enhanced.get('elapsed_seconds', 0):.1f}s")

    # 对比分析
    logger.info("=" * 50)
    logger.info("对比分析")
    logger.info("=" * 50)
    comparison = compare_results(baseline, enhanced)
    results["comparison"] = comparison

    logger.info(f"候选点数变化: {comparison['baseline_candidates']} -> {comparison['enhanced_candidates']} "
                f"({comparison['absolute_change']:+d}, {comparison['relative_change_pct']:+.2f}%)")
    logger.info(f"速度比率: {comparison['speed_ratio']}x")

    if comparison.get("relative_change_pct", 0) > 0:
        logger.info("✅ 召回率提升！动态分位数模式捕获了更多病害木候选点")
    elif comparison.get("relative_change_pct", 0) < 0:
        logger.info("⚠️ 候选点数下降，动态分位数模式可能更严格地过滤了误检")
    else:
        logger.info("候选点数持平")

    # 保存报告
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"对比报告已保存: {args.output}")


if __name__ == "__main__":
    main()
