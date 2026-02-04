# 后端影像处理优化 - 完整部署指南

## 目录
1. [优化概述](#优化概述)
2. [测试验证](#测试验证)
3. [性能基准测试](#性能基准测试)
4. [部署步骤](#部署步骤)
5. [监控和维护](#监控和维护)
6. [故障排查](#故障排查)

## 优化概述

### 优化目标
- **分块大小**: 1024×1024 像素
- **并行处理数量**: 8 个分块
- **目标**: 提升影像处理速度，充分利用多核 CPU

### 优化内容

#### 1. 并行处理服务优化
**文件**: `backend/services/parallel_processing.py`

```python
# 新增常量
DEFAULT_PARALLEL_WORKERS = 8  # 默认并行处理数量

# 优化方法
def get_auto_worker_count(max_limit: int = MAX_WORKERS_LIMIT) -> int:
    """
    优先使用默认的 8 个工作进程进行并行处理
    如果 CPU 核心数不足，则自动降级
    """
    cpu_count = mp.cpu_count()
    num_workers = min(DEFAULT_PARALLEL_WORKERS, cpu_count, max_limit)
    num_workers = max(num_workers, MIN_WORKERS)
    return num_workers
```

#### 2. 深度学习检测服务优化
**文件**: `backend/services/detection.py`

```python
def detect_on_tiled_image(
    self,
    image_data: np.ndarray,
    tile_size: int = DEFAULT_TILE_SIZE,
    padding_mode: str = "pad",
    use_parallel: bool = True,
    num_workers: Optional[int] = 8,  # 默认 8 个工作进程
) -> Tuple[bool, Optional[Dict], str]:
    """
    对分块影像进行病害木检测
    默认使用 8 个工作进程进行并行处理
    """
```

#### 3. 无监督检测服务优化
**文件**: `backend/services/unsupervised_detection.py`

```python
def detect_on_tiled_image(
    self,
    image_data: np.ndarray,
    n_clusters: int = 4,
    min_area: int = 50,
    nodata_value: Optional[float] = None,
    tile_size: int = DEFAULT_TILE_SIZE,
    padding_mode: str = "pad",
    use_parallel: bool = True,
    num_workers: Optional[int] = 8,  # 默认 8 个工作进程
) -> Tuple[bool, Optional[Dict], str]:
    """
    对分块影像进行无监督病害木检测
    默认使用 8 个工作进程进行并行处理
    """
```

## 测试验证

### 前置条件
- Python 3.8+
- 所有依赖已安装
- Git 工作目录干净

### 运行测试

#### 1. 运行并行处理优化测试
```bash
cd /Users/wuchenkai/深度学习模型
python tests/test_parallel_optimization.py
```

**测试内容**:
- ✓ 验证默认并行工作进程数为 8
- ✓ 验证无监督检测默认参数
- ✓ 验证深度学习检测默认参数
- ✓ 验证分块大小为 1024×1024
- ✓ 验证并行处理正确性
- ✓ 性能基准测试（并行 vs 顺序）

#### 2. 运行完整测试套件
```bash
python tests/run_all_tests.py
```

**测试阶段**:
1. 并行处理优化测试
2. 代码变更验证
3. 部署前检查清单

**输出**:
- 控制台日志
- JSON 格式报告: `test_reports/test_report_YYYYMMDD_HHMMSS.json`
- 文本格式报告: `test_reports/test_report_YYYYMMDD_HHMMSS.txt`

## 性能基准测试

### 测试场景
- **数据量**: 16 个分块（模拟 4096×4096 影像）
- **分块大小**: 1024×1024
- **处理时间**: 每个分块 0.1 秒（模拟）

### 预期结果

| 指标 | 顺序处理 | 并行处理(8工作进程) | 性能提升 |
|------|---------|------------------|---------|
| 总耗时 | ~1.6s | ~0.2s | 8x |
| 吞吐量 | 10 分块/s | 80 分块/s | 8x |
| CPU 利用率 | ~12.5% | ~100% | 8x |

### 实际性能因素
- CPU 核心数
- 内存可用性
- 磁盘 I/O 速度
- 影像大小和复杂度

## 部署步骤

### 第一步: 验证测试通过
```bash
# 运行完整测试
python tests/run_all_tests.py

# 检查输出
# 应该看到: ✓ 所有测试通过，可以进行部署
```

### 第二步: 执行部署
```bash
# 部署到生产环境
DEPLOY_ENV=production python tests/deploy.py

# 或部署到测试环境
DEPLOY_ENV=staging python tests/deploy.py
```

### 第三步: 验证部署
```bash
# 检查部署报告
cat DEPLOYMENT_REPORT.md

# 检查备份
ls -la backups/
```

### 第四步: 启动后端服务
```bash
# 启动后端服务
cd /Users/wuchenkai/深度学习模型
python -m uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 第五步: 验证服务
```bash
# 检查服务状态
curl http://localhost:8000/docs

# 查看日志
tail -f logs/backend.log
```

## 监控和维护

### 关键指标监控

#### 1. 并行处理指标
```python
# 在日志中查看
"自动检测工作进程数: CPU 核心数=16, 使用工作进程数=8（默认并行处理数=8）"
```

#### 2. 分块处理指标
```python
# 在日志中查看
"已生成 N 个分块"
"并行处理完成: M 个成功, K 个失败"
```

#### 3. 性能指标
- 分块处理耗时
- 内存占用
- CPU 利用率
- 检测准确率

### 日志位置
- 后端日志: `logs/backend.log`
- 测试报告: `test_reports/`
- 部署报告: `DEPLOYMENT_REPORT.md`
- 备份文件: `backups/YYYYMMDD_HHMMSS/`

### 定期检查
- 每周检查一次性能指标
- 每月检查一次日志文件大小
- 定期清理旧的测试报告和备份

## 故障排查

### 问题 1: 并行处理数不是 8
**症状**: 日志显示工作进程数不是 8

**原因**:
- CPU 核心数少于 8
- 系统资源限制

**解决方案**:
```python
# 检查 CPU 核心数
import multiprocessing as mp
print(f"CPU 核心数: {mp.cpu_count()}")

# 如果需要强制使用 8 个工作进程
# 在调用时显式指定
service.detect_on_tiled_image(
    image_data,
    num_workers=8  # 显式指定
)
```

### 问题 2: 内存占用过高
**症状**: 系统内存不足，处理速度下降

**原因**:
- 8 个并行分块占用内存过多
- 影像尺寸过大

**解决方案**:
```python
# 减少并行工作进程数
service.detect_on_tiled_image(
    image_data,
    num_workers=4  # 降低到 4 个
)

# 或增加系统内存
```

### 问题 3: 部分分块处理失败
**症状**: 日志显示某些分块处理失败

**原因**:
- 分块数据异常
- 处理函数异常

**解决方案**:
```python
# 检查错误日志
tail -f logs/backend.log | grep "error"

# 查看详细错误信息
# 在日志中查找 "分块 X 处理失败"

# 如需调试，可使用顺序处理
service.detect_on_tiled_image(
    image_data,
    use_parallel=False  # 使用顺序处理便于调试
)
```

### 问题 4: 部署失败
**症状**: 部署脚本报错

**原因**:
- Git 工作目录不干净
- 依赖未安装
- 权限问题

**解决方案**:
```bash
# 检查 Git 状态
git status

# 提交或放弃未提交的变更
git add .
git commit -m "..."

# 检查依赖
pip install -r requirements.txt

# 检查权限
ls -la backend/services/
```

## 回滚方案

### 如需回滚到之前的版本

#### 1. 从备份恢复
```bash
# 查看备份
ls -la backups/

# 恢复文件
cp backups/YYYYMMDD_HHMMSS/parallel_processing.py backend/services/
cp backups/YYYYMMDD_HHMMSS/detection.py backend/services/
cp backups/YYYYMMDD_HHMMSS/unsupervised_detection.py backend/services/
cp backups/YYYYMMDD_HHMMSS/settings.py backend/config/
```

#### 2. 使用 Git 回滚
```bash
# 查看提交历史
git log --oneline

# 回滚到之前的提交
git revert <commit-hash>

# 或重置到之前的状态
git reset --hard <commit-hash>
```

#### 3. 重启服务
```bash
# 重启后端服务
# 使用你的服务管理工具（systemd, supervisor 等）
systemctl restart backend-service
```

## 性能优化建议

### 短期优化
1. 监控实际性能提升
2. 根据系统资源调整工作进程数
3. 优化分块大小（如需要）

### 中期优化
1. 实现动态工作进程数调整
2. 添加分块处理结果缓存
3. 优化内存管理

### 长期优化
1. 考虑使用 GPU 加速
2. 实现分布式处理
3. 优化算法效率

## 支持和反馈

如有问题或建议，请：
1. 查看日志文件
2. 运行诊断测试
3. 参考故障排查部分
4. 联系技术支持

---

**最后更新**: 2026-02-04
**版本**: 1.0
**状态**: 生产就绪
