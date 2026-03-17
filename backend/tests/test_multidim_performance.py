"""
3D-2D-1D 多维降维性能基准测试

测试项：
- 参数量对比
- 推理速度对比 (batch size 1, 4, 8, 16)
- 内存占用对比
- 不同分辨率下的性能
- 消融实验（各降维组合对比）
"""

import torch
import time
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.models.backbones import (
    VGGBackbone, ResNetBackbone, DenseNetBackbone,
    MobileNetBackbone, EfficientNetBackbone,
)
from backend.models.multidim_reducer import (
    MultiDimConvReducer, ProgressiveReducer, SEBlock, CBAM,
)


def count_parameters(model):
    """统计模型参数量"""
    return sum(p.numel() for p in model.parameters())


def measure_inference_time(model, x, num_runs=10):
    """测量推理时间"""
    model.eval()
    with torch.no_grad():
        # 预热
        _ = model(x)
        start = time.time()
        for _ in range(num_runs):
            _ = model(x)
        elapsed = (time.time() - start) / num_runs
    return elapsed


def measure_memory(model, x):
    """测量前向传播内存占用（仅 CPU 估算）"""
    import tracemalloc
    tracemalloc.start()
    model.eval()
    with torch.no_grad():
        _ = model(x)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak / 1024 / 1024  # MB
def test_parameter_comparison():
    """参数量对比测试"""
    print("\n" + "=" * 70)
    print("1. 参数量对比")
    print("=" * 70)
    print(f"{'模型':<30} {'无降维':>12} {'3D-2D-1D':>12} {'变化':>10}")
    print("-" * 70)

    configs = [
        ("VGG", lambda r: VGGBackbone(num_classes=4, use_rmfs=True, use_multidim_reduction=r)),
        ("ResNet18", lambda r: ResNetBackbone(num_classes=4, depth=18, use_rmfs=True, use_multidim_reduction=r)),
        ("ResNet50", lambda r: ResNetBackbone(num_classes=4, depth=50, use_rmfs=True, use_multidim_reduction=r)),
        ("DenseNet", lambda r: DenseNetBackbone(num_classes=4, use_rmfs=True, use_multidim_reduction=r)),
        ("MobileNet", lambda r: MobileNetBackbone(num_classes=4, use_rmfs=True, use_multidim_reduction=r)),
        ("EfficientNet", lambda r: EfficientNetBackbone(num_classes=4, use_rmfs=True, use_multidim_reduction=r)),
    ]

    for name, model_fn in configs:
        params_base = count_parameters(model_fn(False))
        params_reduce = count_parameters(model_fn(True))
        change = (params_reduce - params_base) / params_base * 100
        print(f"  {name:<28} {params_base:>10,} {params_reduce:>12,} {change:>+9.1f}%")


def test_inference_speed():
    """推理速度对比测试"""
    print("\n" + "=" * 70)
    print("2. 推理速度对比 (各 batch size)")
    print("=" * 70)

    batch_sizes = [1, 4, 8, 16]

    for bs in batch_sizes:
        print(f"\n  Batch Size = {bs}")
        print(f"  {'模型':<28} {'无降维(ms)':>12} {'3D-2D-1D(ms)':>14} {'加速比':>8}")
        print("  " + "-" * 66)

        x = torch.randn(bs, 3, 224, 224)

        configs = [
            ("VGG", lambda r: VGGBackbone(num_classes=4, use_rmfs=True, use_multidim_reduction=r)),
            ("ResNet50", lambda r: ResNetBackbone(num_classes=4, depth=50, use_rmfs=True, use_multidim_reduction=r)),
        ]

        for name, model_fn in configs:
            model_base = model_fn(False)
            model_reduce = model_fn(True)
            t_base = measure_inference_time(model_base, x) * 1000
            t_reduce = measure_inference_time(model_reduce, x) * 1000
            speedup = t_base / t_reduce if t_reduce > 0 else float('inf')
            print(f"  {name:<28} {t_base:>10.1f} {t_reduce:>12.1f} {speedup:>7.2f}x")

def test_memory_usage():
    """内存占用对比测试"""
    print("\n" + "=" * 70)
    print("3. 内存占用对比")
    print("=" * 70)
    print(f"  {'模型':<28} {'无降维(MB)':>12} {'3D-2D-1D(MB)':>14} {'变化':>10}")
    print("  " + "-" * 66)

    x = torch.randn(4, 3, 224, 224)

    configs = [
        ("VGG", lambda r: VGGBackbone(num_classes=4, use_rmfs=True, use_multidim_reduction=r)),
        ("ResNet50", lambda r: ResNetBackbone(num_classes=4, depth=50, use_rmfs=True, use_multidim_reduction=r)),
    ]

    for name, model_fn in configs:
        mem_base = measure_memory(model_fn(False), x)
        mem_reduce = measure_memory(model_fn(True), x)
        change = (mem_reduce - mem_base) / mem_base * 100 if mem_base > 0 else 0
        print(f"  {name:<28} {mem_base:>10.1f} {mem_reduce:>12.1f} {change:>+9.1f}%")


def test_resolution_performance():
    """不同分辨率下的性能测试"""
    print("\n" + "=" * 70)
    print("4. 不同分辨率下的性能")
    print("=" * 70)

    resolutions = [64, 128, 224, 384]

    model = VGGBackbone(num_classes=4, use_rmfs=True, use_multidim_reduction=True)
    model.eval()

    print(f"  {'分辨率':<12} {'推理时间(ms)':>14} {'输出 shape':>20}")
    print("  " + "-" * 50)

    for res in resolutions:
        x = torch.randn(2, 3, res, res)
        t = measure_inference_time(model, x) * 1000
        with torch.no_grad():
            y = model(x)
        print(f"  {res}x{res:<8} {t:>12.1f} {str(y.shape):>20}")


def test_ablation_study():
    """消融实验：各降维组合对比"""
    print("\n" + "=" * 70)
    print("5. 消融实验 - 降维组合对比")
    print("=" * 70)

    x_feat = torch.randn(2, 1024, 7, 7)  # 模拟 backbone 输出

    configs = [
        ("仅 1D 降维", MultiDimConvReducer(1024, final_channels=128, adaptive_strategy=False)),
        ("仅 2D-1D 降维", None),
        ("完整 3D-2D-1D", MultiDimConvReducer(1024, final_channels=128, adaptive_strategy=False)),
        ("3D-2D-1D + SE", MultiDimConvReducer(1024, final_channels=128, use_attention=True,
                                                attention_type="se", adaptive_strategy=False)),
        ("3D-2D-1D + CBAM", MultiDimConvReducer(1024, final_channels=128, use_attention=True,
                                                  attention_type="cbam", adaptive_strategy=False)),
    ]

    # 手动创建仅 2D-1D 的配置
    reducer_2d_1d = MultiDimConvReducer(1024, final_channels=128, adaptive_strategy=True)
    # 强制 2d_1d 模式（通过设置 adaptive_strategy 和合适的通道数）
    configs[1] = ("仅 2D-1D 降维", MultiDimConvReducer(384, final_channels=128, adaptive_strategy=True))

    print(f"  {'配置':<20} {'参数量':>10} {'推理时间(ms)':>14} {'输出 shape':>16}")
    print("  " + "-" * 64)

    for name, reducer in configs:
        if reducer is None:
            continue
        params = count_parameters(reducer)
        input_tensor = torch.randn(2, reducer.input_channels, 7, 7)
        t = measure_inference_time(reducer, input_tensor) * 1000
        reducer.eval()
        with torch.no_grad():
            out = reducer(input_tensor)
        print(f"  {name:<20} {params:>8,} {t:>12.2f} {str(out.shape):>16}")


def run_all_benchmarks():
    """运行所有基准测试"""
    print("=" * 70)
    print("3D-2D-1D 多维降维性能基准测试")
    print("=" * 70)

    test_parameter_comparison()
    test_inference_speed()
    test_memory_usage()
    test_resolution_performance()
    test_ablation_study()

    print("\n" + "=" * 70)
    print("所有基准测试完成")
    print("=" * 70)


if __name__ == "__main__":
    run_all_benchmarks()
