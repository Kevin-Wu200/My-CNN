# 文件上传流程修复 - 快速参考指南

## 📌 核心概念

### 文件上传状态机
```
uploading 
  ↓ (接收chunk)
chunks_complete 
  ↓ (所有chunk已接收)
merging 
  ↓ (执行合并)
merge_complete 
  ↓ (合并完成)
completed 
  ↓ (文件就绪)
```

### 关键日志标记
- `[CHUNK_RECEIVED]` - chunk接收
- `[ALL_CHUNKS_RECEIVED]` - 所有chunk已接收
- `[MERGE_COMBINING_START]` - 合并开始
- `[MERGE_COMBINING_COMPLETE]` - 合并完成
- `[FILE_READY_STATUS_SET]` - 文件就绪

## 🔧 FilePathManager 使用

### 导入
```python
from backend.utils.file_path_manager import FilePathManager
```

### 常用方法
```python
# 获取分片目录
chunk_dir = FilePathManager.get_chunk_dir(upload_id)

# 获取分片文件路径
chunk_path = FilePathManager.get_chunk_path(upload_id, chunk_index)

# 获取合并后文件路径
merged_path = FilePathManager.get_merged_file_path(file_name)

# 获取检测影像目录
detection_dir = FilePathManager.get_detection_images_dir()

# 验证路径安全性
is_safe = FilePathManager.validate_path_is_in_storage(file_path)

# 确保目录存在
FilePathManager.ensure_directory_exists(directory)
```

## 📝 文件位置速查

### 核心实现文件
| 文件 | 功能 | 行数 |
|------|------|------|
| `backend/utils/file_path_manager.py` | 统一路径管理 | 166 |
| `backend/api/upload.py` | 上传API | 464 |
| `backend/services/background_task_manager.py` | 后台合并任务 | 583 |
| `backend/api/unsupervised_detection.py` | 检测API | 477 |
| `backend/api/training_sample.py` | 训练样本API | 325 |

### 关键代码位置
| 功能 | 文件 | 行号 |
|------|------|------|
| 状态定义 | `backend/models/database.py` | 109-110 |
| chunk验证 | `backend/api/upload.py` | 270-296 |
| 合并日志 | `backend/services/background_task_manager.py` | 417-448 |
| 文件校验 | `backend/services/background_task_manager.py` | 450-476 |
| 就绪检查 | `backend/api/unsupervised_detection.py` | 34-79 |

## 🧪 快速测试

### 验证FilePathManager
```bash
python3 << 'PYTHON'
from backend.utils.file_path_manager import FilePathManager
paths = FilePathManager.get_all_storage_paths()
for key, value in paths.items():
    print(f"{key}: {value}")
PYTHON
```

### 查看关键日志
```bash
grep -E "\[CHUNK_RECEIVED\]|\[ALL_CHUNKS_RECEIVED\]|\[MERGE_COMBINING_START\]|\[MERGE_COMBINING_COMPLETE\]|\[FILE_READY_STATUS_SET\]" logs/app.log
```

### 检查数据库状态
```bash
sqlite3 storage/system.db "SELECT upload_id, file_name, status, file_path FROM upload_sessions ORDER BY created_at DESC LIMIT 10;"
```

## 🚀 部署检查

### 部署前
- [ ] 代码已提交到git
- [ ] 所有测试已通过
- [ ] 日志输出已验证
- [ ] 数据库备份已完成

### 部署步骤
1. 拉取最新代码
2. 重启后端服务
3. 验证日志输出
4. 监控上传流程

### 部署后
- [ ] 服务正常运行
- [ ] 日志输出正常
- [ ] 上传流程正常
- [ ] 检测流程正常

## 📊 监控指标

### 关键指标
- 上传成功率 (目标: > 95%)
- 文件合并成功率 (目标: 100%)
- 文件校验失败率 (目标: < 1%)
- 就绪检查失败率 (目标: < 5%)

### 告警规则
```
上传成功率 < 95% → 告警
文件合并失败 → 立即告警
文件校验失败 → 立即告警
就绪检查失败 > 5% → 告警
```

## 🔍 故障排查

### 问题：文件上传失败
**检查项**:
1. 查看日志中是否有 `[CHUNK_UPLOAD_ERROR]`
2. 检查临时目录是否有足够空间
3. 检查文件权限是否正确

### 问题：文件合并失败
**检查项**:
1. 查看日志中是否有 `[MERGE_FAILED]`
2. 检查所有chunk是否都已接收
3. 检查文件大小是否匹配

### 问题：检测前就绪检查失败
**检查项**:
1. 查看日志中是否有 `[FILE_READINESS_CHECK_FAILED]`
2. 检查数据库中文件状态是否为 `completed`
3. 检查文件是否存在

## 📚 相关文档

- `IMPLEMENTATION_SUMMARY.md` - 详细实现总结
- `UPLOAD_FIX_COMPLETION_REPORT.md` - 完成报告
- `backend/utils/file_path_manager.py` - FilePathManager源代码

## 🎯 后续优化

### 短期
- [ ] 添加单元测试
- [ ] 添加集成测试
- [ ] 优化数据库查询

### 中期
- [ ] 实现断点续传
- [ ] 添加上传速度限制
- [ ] 优化合并算法

### 长期
- [ ] 考虑对象存储
- [ ] 实现分布式上传
- [ ] 添加CDN支持

## 💡 常见问题

**Q: 如何添加新的存储目录?**
A: 在 `backend/config/settings.py` 中添加新的目录配置，然后在 `FilePathManager` 中添加对应的方法。

**Q: 如何修改chunk大小?**
A: 修改 `backend/config/settings.py` 中的 `IMAGE_PROCESSING_CONFIG` 配置。

**Q: 如何查看上传进度?**
A: 调用 `/api/upload/status/{uploadId}` 端点查询上传状态。

**Q: 如何清理过期的上传会话?**
A: 调用 `/api/upload/cleanup` 端点清理超过24小时未完成的会话。

