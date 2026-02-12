# 任务文件清理机制实现文档

## 概述

本文档描述了无监督检测任务完成后的文件自动清理机制的实现。

## 实现目标

在无监督检测任务执行完成后，自动删除与该任务相关的文件，包括：
- `storage/merged/{uploadId}.tif` - 合并后的原始影像文件
- `storage/detection_images/{fileName}` - 检测用的影像副本

## 严格限制

1. ✅ 不影响现有上传、检测和任务查询逻辑
2. ✅ 不删除检测结果文件（结果存储在数据库中）
3. ✅ 不删除仍在使用中的文件
4. ✅ 不在任务运行期间删除文件
5. ✅ 如果无法确保安全删除，则放弃删除
6. ✅ 清理动作延迟 120 秒执行，防止异步读写冲突

## 实现架构

### 1. 核心服务模块

**文件**: `backend/services/task_file_cleanup.py`

**主要类**: `TaskFileCleanupService`

**核心方法**:
- `schedule_cleanup()` - 调度延迟清理任务
- `_cleanup_task_files()` - 执行实际的文件清理
- `_find_related_files()` - 查找与任务相关的文件
- `_safe_delete_file()` - 安全删除单个文件
- `_validate_file_path_for_cleanup()` - 验证文件路径是否可以安全删除

### 2. 安全机制

#### 2.1 白名单机制
只允许删除以下目录中的文件：
- `storage/merged/`
- `storage/detection_images/`

#### 2.2 黑名单机制
禁止删除以下目录中的文件：
- `storage/models/`
- `storage/training_samples/`
- `storage/uploads/`

#### 2.3 文件路径验证
删除前必须通过以下验证：
1. 文件路径在存储目录内（防止路径遍历攻击）
2. 文件真实存在
3. 文件路径属于允许删除的目录
4. 文件路径不属于禁止删除的目录

### 3. 集成点

**文件**: `backend/api/unsupervised_detection.py`

**触发时机**:
1. 任务完成（COMPLETED）- 第518行
2. 任务失败（FAILED）- 第525行
3. 任务取消（CANCELLED）- 第450、470、497行

**调用方式**:
```python
TaskFileCleanupService.schedule_cleanup(task_id, result_data, delay_seconds=120)
```

### 4. 清理流程

```
任务完成/失败/取消
    ↓
调度清理任务（延迟120秒）
    ↓
启动后台线程
    ↓
等待120秒
    ↓
查找相关文件
    ↓
验证文件路径
    ↓
按顺序删除文件
    ↓
记录清理日志
```

### 5. 清理顺序

按照以下顺序删除文件：
1. `storage/detection_images/{fileName}` - 检测影像副本
2. `storage/merged/{uploadId}.tif` - 合并后的原始文件

## 文件类型梳理

### 已清理的文件类型

| 文件类型 | 路径 | 清理时机 | 清理位置 |
|---------|------|---------|---------|
| 分片文件 | `storage/temp/{uploadId}/chunk_{index}` | 合并完成后 | `background_task_manager.py:686` |
| 合并文件 | `storage/merged/{uploadId}.tif` | 检测任务完成后延迟120秒 | `task_file_cleanup.py` |
| 检测影像副本 | `storage/detection_images/{fileName}` | 检测任务完成后延迟120秒 | `task_file_cleanup.py` |

### 不需要清理的文件类型

| 文件类型 | 说明 |
|---------|------|
| 检测结果 | 存储在数据库中，不生成独立文件 |
| GeoJSON文件 | 系统不自动生成GeoJSON文件 |
| 模型文件 | 长期保留，不清理 |
| 训练样本 | 长期保留，不清理 |

## 日志记录

### 清理调度日志
```
[CLEANUP_SCHEDULED] 任务文件清理已调度: task_id={task_id}, delay={delay_seconds}s
[CLEANUP_THREAD_STARTED] 清理线程已启动: task_id={task_id}
```

### 清理执行日志
```
[CLEANUP_START] 开始清理任务文件: task_id={task_id}
[CLEANUP_FILE_FOUND] 检测影像文件: {file_path}
[CLEANUP_FILE_FOUND] 合并文件: {file_path}, uploadId={upload_id}
[CLEANUP_DELETING] 正在删除文件: {file_path}
[FILE_DELETED] 文件已删除: {file_path}
[CLEANUP_COMPLETE] 任务文件清理完成: task_id={task_id}, deleted={count}, failed={count}
```

### 验证失败日志
```
[CLEANUP_VALIDATION_FAILED] 文件路径不在存储目录内: {file_path}
[CLEANUP_VALIDATION_FAILED] 文件路径不在允许删除的目录中: {file_path}
[CLEANUP_VALIDATION_FAILED] 文件路径在禁止删除的目录中: {file_path}
[CLEANUP_SKIP] 文件不存在，跳过删除: {file_path}
[CLEANUP_FAILED] 删除文件时发生错误: {file_path}, error={error}
```

## 测试

### 单元测试

**文件**: `tests/test_task_file_cleanup.py`

**测试覆盖**:
- ✅ 验证允许删除的目录（merged, detection_images）
- ✅ 验证禁止删除的目录（models, training_samples, uploads）
- ✅ 验证文件不存在时的处理
- ✅ 验证成功删除文件
- ✅ 验证验证失败时不删除文件
- ✅ 验证查找相关文件
- ✅ 验证调度清理创建后台线程

### 集成测试建议

1. 上传一个测试影像文件
2. 启动无监督检测任务
3. 等待任务完成
4. 验证检测结果存在于数据库中
5. 等待120秒后验证文件已被删除
6. 验证任务查询接口仍然正常工作

## 验收标准

- ✅ 任务完成后，`storage/merged/` 中不再存在该任务的文件
- ✅ 任务完成后，`storage/detection_images/` 中不再存在该任务的文件
- ✅ 检测结果仍然存在于数据库中
- ✅ 任务查询接口仍然正常工作
- ✅ 清理动作延迟120秒执行
- ✅ 所有清理操作都有详细的日志记录

## 配置参数

| 参数 | 默认值 | 说明 |
|-----|-------|------|
| `delay_seconds` | 120 | 清理延迟时间（秒） |

## 注意事项

1. **延迟执行**: 清理动作延迟120秒执行，确保所有异步操作完成
2. **线程安全**: 清理操作在独立的后台线程中执行，不影响主服务
3. **失败容错**: 如果清理失败，不会影响任务的正常完成状态
4. **日志完整**: 所有清理操作都有详细的日志记录，便于排查问题
5. **安全优先**: 如果无法确保安全删除，则放弃删除操作

## 未来优化建议

1. 支持配置清理延迟时间
2. 支持手动触发清理（通过API）
3. 支持批量清理旧任务的文件
4. 支持清理统计和报告
5. 支持清理失败重试机制
