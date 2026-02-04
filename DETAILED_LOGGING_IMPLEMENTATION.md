# 详细日志记录实现报告

## 概述

本报告详细说明了为深度学习模型项目增加的详细日志记录功能，用于验证修复效果和监控系统运行状态。

## 实现内容

### 1. 新建资源监控模块 (`backend/utils/resource_monitor.py`)

创建了一个独立的资源监控模块，提供以下功能：

#### 主要功能
- **进程监控**：获取当前系统进程数
- **线程监控**：获取当前进程的线程数
- **CPU监控**：获取 CPU 使用率（百分比）
- **内存监控**：获取系统和进程级别的内存使用情况
  - 系统总内存、已用内存、可用内存
  - 内存使用率百分比
  - 当前进程 RSS 内存（物理内存）
  - 当前进程 VMS 内存（虚拟内存）

#### 核心方法
```python
ResourceMonitor.get_process_count()           # 获取进程数
ResourceMonitor.get_thread_count()            # 获取线程数
ResourceMonitor.get_cpu_usage()               # 获取 CPU 使用率
ResourceMonitor.get_memory_usage()            # 获取内存使用情况
ResourceMonitor.log_resource_status(label)    # 记录资源状态
ResourceMonitor.get_resource_snapshot()       # 获取资源快照
ResourceMonitor.log_process_lifecycle(event)  # 记录进程生命周期
ResourceMonitor.log_thread_lifecycle(event)   # 记录线程生命周期
```

#### 日志格式示例
```
[资源状态] 进程数=245, 线程数=8, CPU使用率=45.2%,
系统内存=8192.5MB/16384.0MB (50.0%),
进程内存=RSS 512.3MB / VMS 1024.5MB
```

### 2. 增强日志工具模块 (`backend/utils/logger.py`)

#### 新增功能

**日志格式增强**
- 添加了进程ID (PID) 和线程ID (TID) 到日志格式
- 新格式：`%(asctime)s - %(name)s - [PID:%(process)d] [TID:%(thread)d] - %(levelname)s - %(message)s`

**进程生命周期日志**
```python
LoggerSetup.log_process_start(process_name)      # 记录进程启动
LoggerSetup.log_process_end(process_name)        # 记录进程结束
LoggerSetup.log_subprocess_start(name, pid)      # 记录子进程启动
LoggerSetup.log_subprocess_exit(name, pid, code) # 记录子进程退出
```

**任务生命周期日志**
```python
LoggerSetup.log_task_start(task_id, task_name)   # 记录任务开始
LoggerSetup.log_task_end(task_id, task_name)     # 记录任务结束
```

#### 日志格式示例
```
2026-02-04 14:30:45 - system - [PID:12345] [TID:140234567890] - INFO - 进程启动: detection_service, PID=12345
2026-02-04 14:30:46 - system - [PID:12345] [TID:140234567891] - INFO - 子进程启动: worker_1, 子进程PID=12346, 父进程PID=12345
2026-02-04 14:30:50 - system - [PID:12345] [TID:140234567891] - INFO - [task_001] 任务开始: unsupervised_detection
```

### 3. 并行处理服务增强 (`backend/services/parallel_processing.py`)

#### 新增日志记录点

**进程池创建**
```
进程池已创建: 8 个工作进程, 进程池ID: 140234567890
[资源状态] 进程数=245, 线程数=8, CPU使用率=45.2%, ...
```

**分块提交**
- 每提交 10 个分块记录一次资源状态
- 记录分块提交进度

**分块完成**
- 每完成 10 个分块记录一次资源状态
- 记录分块完成进度

**进程池清理**
```
开始清理进程池 (ID: 140234567890)...
[资源状态] 清理进程池前 (ID: 140234567890)
进程池已清理 (ID: 140234567890)
[资源状态] 清理进程池后 (ID: 140234567890)
```

#### 日志示例
```
INFO - 进程池已创建: 8 个工作进程, 进程池ID: 140234567890
INFO - [资源状态] 进程数=245, 线程数=8, CPU使用率=45.2%, ...
DEBUG - 分块 0 已提交到工作进程池 (总进度: 1/100)
INFO - 分块 0 处理完成 (进度: 1/100)
INFO - [资源状态] 分块完成进度 (10/100)
```

### 4. 无监督检测服务增强 (`backend/services/unsupervised_detection.py`)

#### 单个分块处理日志 (`_process_single_tile`)

```
INFO - 分块 0 处理开始
DEBUG - 分块 0: 开始影像归一化
DEBUG - 分块 0: 开始特征构建与标准化
DEBUG - 分块 0: 开始 K-means 聚类
DEBUG - 分块 0: 提取光谱特征
DEBUG - 分块 0: 开始病害木候选类别判定
DEBUG - 分块 0: 开始空间后处理
INFO - 分块 0 处理完成: 5 个候选点
[资源状态] 分块 0 处理完成
```

#### 分块检测日志 (`detect_on_tiled_image`)

```
INFO - [task_001] 开始分块检测: 影像尺寸=5000x5000, 分块尺寸=1024x1024
[资源状态] 分块检测开始 [task_001]
DEBUG - [task_001] 生成分块中...
INFO - [task_001] 已生成 25 个分块
INFO - [task_001] 使用并行处理分块，工作进程数=8
[资源状态] 并行处理分块开始 [task_001]
INFO - [task_001] 并行处理完成: 25 个成功, 0 个失败
[资源状态] 并行处理分块完成 [task_001]
INFO - [task_001] 共检测到 125 个候选点
INFO - [task_001] 分块检测完成
[资源状态] 分块检测完成 [task_001]
```

#### 完整检测流程日志 (`detect`)

```
INFO - [task_001] 无监督检测开始
[资源状态] 无监督检测开始 [task_001]
INFO - [task_001] 影像尺寸较大 (5000×5000)，使用分块处理 + 并行处理
DEBUG - [task_001] 第一步: 影像归一化
DEBUG - [task_001] 第二步和第三步: 特征构建与标准化
DEBUG - [task_001] 第四步: K-means 聚类
DEBUG - [task_001] 第五步: 病害木候选类别判定
DEBUG - [task_001] 第六步: 空间后处理
DEBUG - [task_001] 第七步: 结果输出
INFO - [task_001] 无监督检测完成，发现 125 个候选点
[资源状态] 无监督检测完成 [task_001]
```

### 5. API 端点增强 (`backend/api/unsupervised_detection.py`)

#### 后台任务生命周期日志

```
INFO - [task_001] 后台任务已启动
[资源状态] 后台任务启动 [task_001]
DEBUG - [task_001] 读取影像: /path/to/image.tif
INFO - [task_001] 影像读取成功，尺寸: (5000, 5000, 3)
[资源状态] 影像读取完成 [task_001]
INFO - [task_001] 开始执行无监督检测
INFO - [task_001] 检测完成，开始处理结果
[资源状态] 检测完成，处理结果 [task_001]
INFO - [task_001] 检测完成，发现 125 个病害木候选区域
INFO - [task_001] 后台任务已完成
[资源状态] 后台任务完成 [task_001]
```

## 日志级别说明

| 级别 | 用途 | 示例 |
|------|------|------|
| DEBUG | 详细的调试信息 | 各处理步骤的开始/结束 |
| INFO | 重要的运行信息 | 任务启动/完成、分块处理进度 |
| WARNING | 警告信息 | 进程池强制终止、超时处理 |
| ERROR | 错误信息 | 处理失败、异常情况 |

## 资源监控指标

### 系统级别
- **进程数**：当前系统运行的进程总数
- **CPU使用率**：系统 CPU 使用百分比（0-100%）
- **系统内存**：系统总内存、已用内存、可用内存、使用率

### 进程级别
- **线程数**：当前进程的线程总数
- **RSS内存**：进程占用的物理内存（MB）
- **VMS内存**：进程占用的虚拟内存（MB）

## 日志文件位置

日志文件默认保存在 `./logs/` 目录下，按日期和模块名称组织：

```
logs/
├── system_20260204.log          # 系统日志
├── backend.services.parallel_processing_20260204.log
├── backend.services.unsupervised_detection_20260204.log
├── backend.api.unsupervised_detection_20260204.log
└── ...
```

## 使用示例

### 在代码中使用资源监控

```python
from backend.utils.resource_monitor import ResourceMonitor

# 记录资源状态
ResourceMonitor.log_resource_status("处理开始")

# 获取资源快照
snapshot = ResourceMonitor.get_resource_snapshot()
print(f"当前进程数: {snapshot['process_count']}")
print(f"当前线程数: {snapshot['thread_count']}")
print(f"CPU使用率: {snapshot['cpu_usage']:.1f}%")
print(f"内存使用: {snapshot['memory']['used']:.1f}MB / {snapshot['memory']['total']:.1f}MB")
```

### 在代码中使用增强的日志记录

```python
from backend.utils.logger import LoggerSetup

logger = LoggerSetup.get_logger(__name__)

# 记录任务生命周期
LoggerSetup.log_task_start("task_001", "unsupervised_detection")
# ... 执行任务 ...
LoggerSetup.log_task_end("task_001", "unsupervised_detection", success=True)

# 记录进程生命周期
LoggerSetup.log_process_start("detection_service")
# ... 执行处理 ...
LoggerSetup.log_process_end("detection_service")
```

## 验证修复效果的方法

### 1. 查看日志文件
```bash
tail -f logs/system_20260204.log
```

### 2. 监控资源使用
日志中的 `[资源状态]` 行显示了关键时刻的系统资源使用情况，可用于：
- 验证进程数是否正常增长和回收
- 检查内存是否有泄漏
- 监控 CPU 使用率是否合理

### 3. 追踪任务执行
通过 `[task_id]` 标记可以追踪单个任务的完整执行流程：
```bash
grep "\[task_001\]" logs/system_20260204.log
```

### 4. 分析性能瓶颈
通过日志中的时间戳可以计算各个处理步骤的耗时：
```
14:30:45 - 任务开始
14:30:50 - 影像读取完成 (5秒)
14:31:00 - 检测完成 (10秒)
14:31:05 - 任务完成 (20秒总耗时)
```

## 关键改进点

1. **进程/线程生命周期追踪**
   - 每个进程和线程的启动/结束都有明确的日志记录
   - 便于诊断进程泄漏问题

2. **资源监控**
   - 在关键处理点记录系统资源状态
   - 便于识别资源瓶颈和异常

3. **任务级别追踪**
   - 使用 task_id 标记所有相关日志
   - 便于追踪单个任务的完整执行流程

4. **分块处理详细日志**
   - 记录每个分块的处理状态
   - 便于诊断分块处理中的问题

5. **后台任务监控**
   - 记录后台任务的启动、执行、完成各个阶段
   - 便于监控异步任务的执行状态

## 文件修改清单

| 文件 | 修改内容 |
|------|---------|
| `backend/utils/resource_monitor.py` | 新建 - 资源监控模块 |
| `backend/utils/logger.py` | 增强 - 添加进程/线程/任务生命周期日志 |
| `backend/services/parallel_processing.py` | 增强 - 添加进程池和分块处理日志 |
| `backend/services/unsupervised_detection.py` | 增强 - 添加检测流程和分块处理日志 |
| `backend/api/unsupervised_detection.py` | 增强 - 添加后台任务生命周期日志 |

## 总结

本次实现为项目添加了全面的日志记录功能，包括：
- 资源监控（进程、线程、CPU、内存）
- 进程/线程生命周期追踪
- 任务级别的执行流程记录
- 分块处理的详细日志
- 后台任务的完整监控

这些日志记录将帮助开发者和运维人员：
1. 验证修复效果
2. 诊断性能问题
3. 追踪任务执行流程
4. 监控系统资源使用
5. 快速定位问题根源
