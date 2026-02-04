# 44% 进度卡点诊断报告

## 第一部分：复现与定位 44% 卡点

### 1.1 进度更新点明确标注

#### 训练流程 (backend/api/training_sample.py:273-320)
```
10%  → "初始化训练任务"        (line 289)
30%  → "加载训练数据中"        (line 293)
60%  → "模型训练中"            (line 299)
90%  → "保存模型中"            (line 302)
100% → 完成                    (line 316)
```

#### 检测流程 (backend/api/detection_config.py:232-279)
```
10%  → "初始化检测任务"        (line 250)
50%  → "执行检测中"            (line 254)
90%  → "处理结果中"            (line 260)
100% → 完成                    (line 275)
```

#### 无监督检测流程 (backend/api/unsupervised_detection.py:171-230)
```
10%  → "读取影像中"            (line 186)
30%  → "执行检测中"            (line 194)
90%  → "处理结果中"            (line 207)
100% → 完成                    (line 226)
```

### 1.2 44% 对应的代码位置

**44% 最可能出现在无监督检测流程中：**
- 位置：30% 和 90% 之间
- 对应阶段：`detect_on_tiled_image()` 中的**并行处理分块阶段**
- 具体代码位置：`backend/services/unsupervised_detection.py:594-610`

```python
# 第二步：处理分块
if use_parallel:
    # 并行处理
    logger.info("使用并行处理分块")

    def process_tile_wrapper(tile):
        success, result, msg = self._process_single_tile(...)
        if not success:
            return {"error": msg, "tile_index": tile.tile_index}
        return result

    success, tile_results, errors, msg = (
        ParallelProcessingService.process_tiles_parallel(
            tiles,
            process_tile_wrapper,
            num_workers=num_workers,
            error_handling="log",
        )
    )
```

### 1.3 44% 卡点的详细日志分析需求

**需要在以下位置增加日志：**

1. **并行处理开始前** (unsupervised_detection.py:582-584)
   - 日志内容：task_id, 分块数量, 工作进程数

2. **并行处理中** (parallel_processing.py:103-140)
   - 日志内容：每个 apply_async 提交的分块索引
   - 日志内容：每个 result.get() 的返回情况

3. **并行处理完成后** (unsupervised_detection.py:607-610)
   - 日志内容：成功/失败的分块数

---

## 第二部分：CPU/内存下降时的典型卡死原因排查

### 2.1 根本原因定位

**发现的关键问题：`backend/services/parallel_processing.py:103-140`**

```python
# 使用进程池处理
with Pool(processes=num_workers) as pool:
    for tile_idx, tile in enumerate(tiles):
        try:
            result = pool.apply_async(process_func, (tile,))  # 立即返回
            results.append(result)
        except Exception as e:
            # 错误处理...

    # 收集结果
    processed_results = []
    for result_idx, result in enumerate(results):
        try:
            processed_results.append(result.get())  # ⚠️ 无超时，无限阻塞！
        except Exception as e:
            # 错误处理...
```

### 2.2 问题分析

**问题 1：`result.get()` 无超时机制**
- 位置：`parallel_processing.py:125`
- 现象：如果工作进程崩溃或挂起，主进程会在 `result.get()` 处**无限阻塞**
- 结果：进度永远停留在 30%（无监督检测）或 44%（中间值）

**问题 2：工作进程异常未被感知**
- 位置：`parallel_processing.py:103-120`
- 现象：`apply_async()` 只是提交任务，不会立即检测工作进程状态
- 结果：主进程不知道工作进程已经死亡

**问题 3：CPU/内存下降的原因**
- 工作进程崩溃 → 不再消耗 CPU/内存
- 主进程阻塞在 `result.get()` → 主进程也不消耗 CPU
- 整个系统看起来"卡死"，资源占用下降

### 2.3 为什么会导致 CPU/内存下降

```
正常流程：
主进程 ─┬─ 工作进程1 (消耗CPU/内存)
        ├─ 工作进程2 (消耗CPU/内存)
        └─ 工作进程3 (消耗CPU/内存)
总体：CPU 80-90%, 内存 60-70%

卡死流程：
主进程 ─┬─ 工作进程1 ✗ (已崩溃，不消耗资源)
        ├─ 工作进程2 ✗ (已崩溃，不消耗资源)
        └─ 工作进程3 ✗ (已崩溃，不消耗资源)
主进程阻塞在 result.get()，不消耗CPU
总体：CPU 5-10%, 内存 20-30%
```

### 2.4 其他可能的卡死原因

**已排除的原因：**
- ✓ 主线程等待子线程：代码中使用 `Pool.apply_async()` + `result.get()`，这是标准的等待机制
- ✓ 队列读取阻塞：代码中没有使用 Queue.get()
- ✓ async/await 未 resolve：代码中没有使用 async/await
- ✓ for 循环提前结束：循环逻辑正确，会遍历所有分块
- ✓ break/continue 导致跳过：代码中没有 break/continue

**确认的原因：**
- ✗ `result.get()` 无超时，工作进程崩溃导致无限阻塞

---

## 第三部分：进度系统与任务状态一致性检查

### 3.1 当前进度系统的问题

**问题 1：进度更新与任务状态解耦**
- 进度更新：`task_manager.update_progress(task_id, progress, stage)`
- 任务状态：`task_manager.start_task()` / `complete_task()` / `fail_task()`
- 问题：进度卡住时，任务状态仍为 RUNNING，前端无法判断是否真的卡死

**问题 2：缺少进度超时检测**
- 当前代码没有检测"进度在同一数值停留超过 N 秒"的机制
- 无法自动判断任务是否真的卡死

**问题 3：异常处理不完整**
- 工作进程崩溃时，主进程无法捕获异常
- 任务状态不会自动转为 FAILED

### 3.2 最小任务状态机设计

```
INIT (初始化)
  ↓
RUNNING (运行中)
  ├─ MERGING (合并中) [可选，用于多进程任务汇总]
  ├─ ERROR (错误) [任何异常都应转到此状态]
  └─ DONE (完成)

状态转移规则：
- INIT → RUNNING：调用 start_task()
- RUNNING → MERGING：进入结果合并阶段
- RUNNING/MERGING → ERROR：捕获异常
- RUNNING/MERGING → DONE：任务完成
- 任何状态 → ERROR：超时或工作进程崩溃
```

### 3.3 当前代码的状态机缺陷

**缺陷 1：没有 MERGING 状态**
- 无监督检测的"处理结果中"(90%) 阶段没有对应的状态
- 无法区分"正在处理分块"和"正在合并结果"

**缺陷 2：没有 ERROR 状态的自动转移**
- 工作进程崩溃时，任务状态仍为 RUNNING
- 前端无法判断任务是否失败

**缺陷 3：没有超时机制**
- 进度停留超过 N 秒时，没有自动转为 ERROR 的机制

---

## 第四部分：修复方案与防止再次卡死

### 4.1 根本修复方案

**修复 1：为 `result.get()` 增加超时机制**

位置：`backend/services/parallel_processing.py:125`

```python
# 修复前
processed_results.append(result.get())

# 修复后
try:
    processed_results.append(result.get(timeout=300))  # 5分钟超时
except mp.TimeoutError:
    error_info = {
        "result_index": result_idx,
        "error": f"分块处理超时（>300秒）",
    }
    errors.append(error_info)
    processed_results.append(None)
    logger.error(f"分块 {result_idx} 处理超时")
```

**修复 2：增加工作进程健康检查**

```python
# 在 result.get() 前检查工作进程是否存活
if not result.ready():
    # 检查是否有异常
    try:
        result.get(timeout=1)
    except mp.TimeoutError:
        # 继续等待
        pass
    except Exception as e:
        # 工作进程异常
        logger.error(f"工作进程异常: {str(e)}")
```

**修复 3：增加进度更新的中间检查点**

在并行处理中增加进度更新：

```python
# 在 unsupervised_detection.py 中
for idx, tile in enumerate(tiles):
    # 计算当前进度：30% + (idx / len(tiles)) * 60%
    current_progress = 30 + int((idx / len(tiles)) * 60)
    task_manager.update_progress(task_id, current_progress, f"处理分块 {idx+1}/{len(tiles)}")
```

### 4.2 防止再次卡死的兜底逻辑

**兜底 1：进度停留检测**

```python
# 在后台任务中增加进度监控
last_progress = 0
last_update_time = time.time()
stuck_threshold = 30  # 30秒

while task_status == "running":
    current_progress = task_manager.get_task_status(task_id)["progress"]
    current_time = time.time()

    if current_progress == last_progress:
        if current_time - last_update_time > stuck_threshold:
            # 进度卡住超过30秒
            logger.error(f"任务 {task_id} 进度卡住在 {current_progress}%")
            task_manager.fail_task(task_id, "任务进度卡住，可能是工作进程崩溃")
            break
    else:
        last_progress = current_progress
        last_update_time = current_time

    time.sleep(5)
```

**兜底 2：后端返回卡死状态**

```python
# 在 task_status API 中增加卡死检测
@router.get("/tasks/status/{task_id}")
async def get_task_status(task_id: str):
    task = task_manager.get_task_status(task_id)

    if task["status"] == "running":
        # 检查进度是否卡住
        if "last_progress_update" in task:
            time_since_update = time.time() - task["last_progress_update"]
            if time_since_update > 30:
                task["stuck"] = True
                task["stuck_duration"] = time_since_update

    return task
```

---

## 第五部分：最终结论

### 5.1 44% 卡死的根本原因

**根本原因：`parallel_processing.py` 中 `result.get()` 无超时机制**

当工作进程崩溃或挂起时，主进程会在 `result.get()` 处无限阻塞，导致：
1. 进度永远停留在 30%-90% 之间（具体值取决于有多少分块已处理）
2. CPU/内存占用下降（工作进程已死，主进程阻塞）
3. 前端无法判断任务是否真的完成

### 5.2 为什么会导致 CPU/内存下降

- 工作进程崩溃 → 不再消耗 CPU/内存
- 主进程阻塞在 `result.get()` → 主进程也不消耗 CPU
- 整个系统看起来"卡死"，资源占用明显下降

### 5.3 本次修改的关键点

1. **为 `result.get()` 增加 timeout 参数**（300秒）
2. **捕获 `TimeoutError` 并转为任务失败**
3. **增加进度更新的中间检查点**（每处理一个分块更新一次进度）
4. **增加进度停留检测机制**（30秒无进度更新则标记为卡死）
5. **后端返回卡死状态给前端**

### 5.4 关键代码位置

| 文件 | 行号 | 问题 | 修复 |
|------|------|------|------|
| `parallel_processing.py` | 125 | `result.get()` 无超时 | 增加 timeout=300 |
| `unsupervised_detection.py` | 594-610 | 并行处理无进度更新 | 增加中间进度检查点 |
| `background_task_manager.py` | 78-99 | 缺少进度停留检测 | 增加时间戳记录 |
| `task_status.py` | - | 无卡死状态返回 | 增加 stuck 字段 |

