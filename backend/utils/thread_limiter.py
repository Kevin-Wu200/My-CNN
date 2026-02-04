"""
数值库线程限制模块
用于在应用启动时限制 PyTorch、NumPy、scikit-learn 等数值库的线程数
防止过度的线程创建导致资源竞争和性能下降
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def limit_numerical_library_threads(num_threads: int = 2) -> None:
    """
    限制数值库的线程数

    此函数必须在导入任何数值库之前调用，以确保环境变量生效。
    设置以下库的线程数：
    - PyTorch (torch)
    - NumPy (numpy)
    - scikit-learn (sklearn)
    - OpenBLAS
    - MKL (Intel Math Kernel Library)
    - OpenMP (OMP)
    - NumExpr

    Args:
        num_threads: 每个进程使用的线程数，默认为 2
                    建议值：2-4（对于 8 个 worker 进程，总线程数 = 8 × num_threads）

    Returns:
        None

    Example:
        >>> limit_numerical_library_threads(num_threads=2)
        # 8 个 worker 进程 × 2 线程 = 16 个线程（而不是 64+ 个）
    """
    logger.info("=" * 70)
    logger.info("开始配置数值库线程限制")
    logger.info("=" * 70)
    logger.info(f"目标线程数: {num_threads}")

    # 设置环境变量（必须在导入库之前设置）
    _set_environment_variables(num_threads)

    # 配置各个库的线程数
    _configure_pytorch_threads(num_threads)
    _configure_numpy_threads(num_threads)
    _configure_sklearn_threads(num_threads)

    logger.info("=" * 70)
    logger.info("数值库线程限制配置完成")
    logger.info("=" * 70)


def _set_environment_variables(num_threads: int) -> None:
    """
    设置环境变量以限制线程数

    Args:
        num_threads: 线程数
    """
    logger.info("[环境变量配置]")

    env_vars = {
        "OMP_NUM_THREADS": str(num_threads),  # OpenMP
        "MKL_NUM_THREADS": str(num_threads),  # Intel MKL
        "OPENBLAS_NUM_THREADS": str(num_threads),  # OpenBLAS
        "NUMEXPR_NUM_THREADS": str(num_threads),  # NumExpr
        "VECLIB_MAXIMUM_THREADS": str(num_threads),  # macOS Accelerate
    }

    for var_name, var_value in env_vars.items():
        os.environ[var_name] = var_value
        logger.info(f"  设置 {var_name} = {var_value}")

    logger.info("环境变量设置完成")


def _configure_pytorch_threads(num_threads: int) -> None:
    """
    配置 PyTorch 的线程数

    Args:
        num_threads: 线程数
    """
    logger.info("[PyTorch 线程配置]")

    try:
        import torch

        # 设置 PyTorch 线程数
        torch.set_num_threads(num_threads)
        logger.info(f"  设置 torch.set_num_threads({num_threads})")

        # 设置 PyTorch 内部线程数
        torch.set_num_interop_threads(1)
        logger.info(f"  设置 torch.set_num_interop_threads(1)")

        # 记录 PyTorch 线程配置
        actual_threads = torch.get_num_threads()
        actual_interop_threads = torch.get_num_interop_threads()
        logger.info(f"  PyTorch 实际线程数: {actual_threads}")
        logger.info(f"  PyTorch 实际 interop 线程数: {actual_interop_threads}")

        # 检查 CUDA 可用性
        if torch.cuda.is_available():
            logger.info(f"  CUDA 可用，设备数: {torch.cuda.device_count()}")
        else:
            logger.info("  CUDA 不可用，使用 CPU")

        logger.info("PyTorch 线程配置完成")

    except ImportError:
        logger.warning("  PyTorch 未安装，跳过配置")
    except Exception as e:
        logger.error(f"  配置 PyTorch 线程失败: {str(e)}", exc_info=True)


def _configure_numpy_threads(num_threads: int) -> None:
    """
    配置 NumPy 的线程数

    Args:
        num_threads: 线程数
    """
    logger.info("[NumPy 线程配置]")

    try:
        import numpy as np

        # NumPy 主要通过环境变量控制线程数
        # 但我们可以记录当前配置
        logger.info(f"  NumPy 版本: {np.__version__}")

        # 尝试获取 NumPy 的线程信息（如果可用）
        try:
            # NumPy 1.17+ 支持 get_num_threads()
            if hasattr(np, "get_num_threads"):
                actual_threads = np.get_num_threads()
                logger.info(f"  NumPy 实际线程数: {actual_threads}")
        except Exception as e:
            logger.debug(f"  无法获取 NumPy 线程数: {str(e)}")

        logger.info("NumPy 线程配置完成")

    except ImportError:
        logger.warning("  NumPy 未安装，跳过配置")
    except Exception as e:
        logger.error(f"  配置 NumPy 线程失败: {str(e)}", exc_info=True)


def _configure_sklearn_threads(num_threads: int) -> None:
    """
    配置 scikit-learn 的线程数

    Args:
        num_threads: 线程数
    """
    logger.info("[scikit-learn 线程配置]")

    try:
        from sklearn import __version__ as sklearn_version

        logger.info(f"  scikit-learn 版本: {sklearn_version}")

        # scikit-learn 主要通过环境变量控制线程数
        # 但我们可以尝试通过 joblib 配置
        try:
            from joblib import parallel_backend

            logger.info(f"  joblib 后端配置已准备")
            logger.info(f"  建议在并行任务中使用: with parallel_backend('threading', n_jobs={num_threads})")

        except ImportError:
            logger.debug("  joblib 未安装或无法导入")

        logger.info("scikit-learn 线程配置完成")

    except ImportError:
        logger.warning("  scikit-learn 未安装，跳过配置")
    except Exception as e:
        logger.error(f"  配置 scikit-learn 线程失败: {str(e)}", exc_info=True)


def log_thread_configuration() -> None:
    """
    记录当前的线程配置信息
    """
    logger.info("=" * 70)
    logger.info("当前线程配置信息")
    logger.info("=" * 70)

    # 记录环境变量
    logger.info("[环境变量]")
    env_vars = [
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ]
    for var_name in env_vars:
        var_value = os.environ.get(var_name, "未设置")
        logger.info(f"  {var_name} = {var_value}")

    # 记录 PyTorch 配置
    logger.info("[PyTorch 配置]")
    try:
        import torch

        logger.info(f"  线程数: {torch.get_num_threads()}")
        logger.info(f"  Interop 线程数: {torch.get_num_interop_threads()}")
        logger.info(f"  CUDA 可用: {torch.cuda.is_available()}")

    except ImportError:
        logger.info("  PyTorch 未安装")
    except Exception as e:
        logger.warning(f"  获取 PyTorch 配置失败: {str(e)}")

    # 记录 NumPy 配置
    logger.info("[NumPy 配置]")
    try:
        import numpy as np

        logger.info(f"  版本: {np.__version__}")
        if hasattr(np, "get_num_threads"):
            logger.info(f"  线程数: {np.get_num_threads()}")

    except ImportError:
        logger.info("  NumPy 未安装")
    except Exception as e:
        logger.warning(f"  获取 NumPy 配置失败: {str(e)}")

    logger.info("=" * 70)
