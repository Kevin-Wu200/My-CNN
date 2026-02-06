# 文件上传流程闭环修复 - 实现总结

## 问题描述
系统缺失"文件何时真正可用"的确定判断，导致后续处理阶段读取不到完整文件。

## 7步修复方案实现情况

### 第一步：明确区分三个上传阶段 ✅
**文件**: `backend/models/database.py` (UploadSession 模型)

**实现**:
- 状态值明确定义: `uploading` → `chunks_complete` → `merging` → `merge_complete` → `completed` → `failed`
- 每个状态代表明确的阶段：
  - `uploading`: 接收单个 chunk
  - `chunks_complete`: 确认所有 chunk 已接收
  - `merging`: 执行分片合并
  - `merge_complete`: 合并完成
  - `completed`: 文件就绪

**代码位置**: `backend/models/database.py:109-110`

---

### 第二步：维护明确的文件上传状态信息 ✅
**文件**: `backend/models/database.py` (UploadSession 模型)

**实现**:
```python
class UploadSession(Base):
    upload_id: str              # 上传会话ID
    file_name: str              # 文件名
    file_size: int              # 期望文件大小
    total_chunks: int           # 期望 chunk 总数
    uploaded_chunks: JSON       # 已接收 chunk 索引集合
    status: str                 # 上传状态
    file_path: str              # 合并完成后的文件路径
    error_message: str          # 错误信息
    created_at, updated_at: DateTime
```

**代码位置**: `backend/models/database.py:99-117`

---

### 第三步：只在所有 chunk 接收完成后触发合并 ✅
**文件**: `backend/api/upload.py` (complete_upload 端点)

**实现**:
- 验证所有分片是否已上传
- 验证分片索引是否连续（0 到 totalChunks-1）
- 只有验证通过才更新状态为 `chunks_complete` 并触发合并

**关键代码**:
```python
# 验证所有分片是否已上传
uploaded_chunks_set = set(json.loads(upload_session.uploaded_chunks))
uploaded_count = len(uploaded_chunks_set)

if uploaded_count != totalChunks:
    missing_chunks = set(range(totalChunks)) - uploaded_chunks_set
    raise HTTPException(detail=f"分片不完整: 已上传 {uploaded_count}/{totalChunks}")

# 验证分片索引是否连续
expected_chunks = set(range(totalChunks))
if uploaded_chunks_set != expected_chunks:
    raise HTTPException(detail="分片索引不连续")
```

**代码位置**: `backend/api/upload.py:270-296`

---

### 第四步：合并逻辑中增加明确日志输出 ✅
**文件**: `backend/services/background_task_manager.py` (_execute_merge_task 方法)

**实现**:
- 合并开始日志: `[MERGE_COMBINING_START]`
- 合并完成日志: `[MERGE_COMBINING_COMPLETE]`
- 输出生成的完整文件路径和最终大小

**关键日志**:
```python
# 合并开始
logger.info(
    f"[MERGE_COMBINING_START] uploadId={uploadId}, outputPath={output_path}, "
    f"totalChunks={totalChunks}"
)

# 合并完成
logger.info(
    f"[MERGE_COMBINING_COMPLETE] uploadId={uploadId}, "
    f"finalFilePath={output_path}, finalFileSize={actual_size}"
)
```

**代码位置**: `backend/services/background_task_manager.py:417-448`

---

### 第五步：合并完成后立刻校验完整文件 ✅
**文件**: `backend/services/background_task_manager.py` (_execute_merge_task 方法)

**实现**:
- 文件是否存在检查
- 文件大小是否大于 0 检查
- 文件是否可读检查
- 校验失败直接返回错误并记录日志

**关键代码**:
```python
# 检查文件是否存在
if not output_path.exists():
    raise FileNotFoundError(f"合并后文件不存在: {output_path}")
logger.info(f"[FILE_EXISTS_CHECK_PASS] uploadId={uploadId}")

# 检查文件大小是否大于 0
if actual_size <= 0:
    output_path.unlink()
    raise ValueError(f"文件大小无效: {actual_size}")
logger.info(f"[FILE_SIZE_CHECK_PASS] uploadId={uploadId}, size={actual_size}")

# 检查文件是否可读
try:
    with open(output_path, "rb") as test_file:
        test_file.read(1)
    logger.info(f"[FILE_READABLE_CHECK_PASS] uploadId={uploadId}")
except Exception as read_error:
    output_path.unlink()
    raise IOError(f"文件不可读: {str(read_error)}")
```

**代码位置**: `backend/services/background_task_manager.py:450-476`

---

### 第六步：处理阶段强制检查文件状态 ✅
**文件**: `backend/api/unsupervised_detection.py` (check_file_readiness 函数)

**实现**:
- 在任何检测/分类逻辑开始前，强制检查文件状态
- 查询数据库中该文件的上传会话
- 只有状态为 `completed` 才允许进行检测
- 未完成直接返回错误，不进入计算流程

**关键代码**:
```python
def check_file_readiness(file_path: str) -> Tuple[bool, str]:
    """步骤6: 在任何检测/分类逻辑开始前，强制检查文件状态是否为"已合并完成" """
    upload_session = db_session.query(UploadSession).filter(
        UploadSession.file_name == file_name,
        UploadSession.file_path == file_path
    ).first()

    if upload_session:
        if upload_session.status != "completed":
            error_msg = (
                f"文件未就绪: 上传会话状态为 '{upload_session.status}'，"
                f"必须为 'completed' 才能进行检测"
            )
            logger.warning(f"[FILE_READINESS_CHECK_FAILED] filePath={file_path}")
            return False, error_msg
        logger.info(f"[FILE_READINESS_CHECK_PASS] filePath={file_path}")
        return True, ""
```

**使用位置**: `backend/api/unsupervised_detection.py:164-171`

---

### 第七步：统一文件路径来源 ✅
**文件**: `backend/utils/file_path_manager.py` (新建)

**实现**:
- 创建统一的 FilePathManager 类
- 所有文件路径操作都通过此类进行
- 集中管理所有存储目录配置
- 提供统一的路径获取接口

**关键方法**:
```python
class FilePathManager:
    @classmethod
    def get_chunk_dir(cls, upload_id: str) -> Path:
        """获取分片存储目录"""

    @classmethod
    def get_chunk_path(cls, upload_id: str, chunk_index: int) -> Path:
        """获取单个分片文件路径"""

    @classmethod
    def get_merged_file_path(cls, file_name: str) -> Path:
        """获取合并后的文件路径"""

    @classmethod
    def get_detection_images_dir(cls) -> Path:
        """获取检测影像目录"""

    @classmethod
    def validate_path_is_in_storage(cls, file_path: str) -> bool:
        """验证文件路径是否在存储目录内（防止路径遍历）"""
```

**更新的文件**:
- `backend/api/upload.py`: 使用 FilePathManager
- `backend/services/background_task_manager.py`: 使用 FilePathManager
- `backend/api/unsupervised_detection.py`: 使用 FilePathManager
- `backend/api/training_sample.py`: 使用 FilePathManager

**代码位置**: `backend/utils/file_path_manager.py` (新建)

---

## 验收标准检查清单

### ✅ 日志清晰性
日志中能够清晰看到完整的流程链路：
```
chunk 接收 → chunk 完整 → 合并开始 → 合并完成 → 文件就绪
```

**日志标记**:
- `[CHUNK_RECEIVED]`: 单个chunk接收
- `[CHUNKS_UPDATED]`: chunk计数更新
- `[ALL_CHUNKS_RECEIVED]`: 所有chunk已接收
- `[CHUNKS_COMPLETE_STATUS_SET]`: 状态更新为chunks_complete
- `[MERGE_START]`: 合并开始
- `[MERGE_COMBINING_START]`: 合并执行开始
- `[MERGE_COMBINING_COMPLETE]`: 合并执行完成
- `[FILE_EXISTS_CHECK_PASS]`: 文件存在检查通过
- `[FILE_SIZE_CHECK_PASS]`: 文件大小检查通过
- `[FILE_READABLE_CHECK_PASS]`: 文件可读性检查通过
- `[FILE_VALIDATION_COMPLETE]`: 文件校验完成
- `[MERGE_COMPLETE_STATUS_SET]`: 状态更新为merge_complete
- `[FILE_READY_STATUS_SET]`: 状态更新为completed
- `[FILE_READINESS_CHECK_PASS]`: 检测前文件就绪检查通过

### ✅ 后续处理阶段稳定性
后续处理阶段不再出现文件不存在或不可用的问题：
- 检测前强制检查文件状态（第6步）
- 文件路径统一管理（第7步）
- 所有路径操作都通过 FilePathManager

### ✅ 日志完整性
日志不再出现"看似正常但流程中断"的情况：
- 每个关键阶段都有明确的日志标记
- 错误情况都有详细的错误日志
- 文件校验失败会立即记录并返回错误

---

## 文件修改清单

### 新建文件
- `backend/utils/file_path_manager.py` - 统一文件路径管理器

### 修改文件
- `backend/api/upload.py` - 使用 FilePathManager
- `backend/services/background_task_manager.py` - 使用 FilePathManager
- `backend/api/unsupervised_detection.py` - 使用 FilePathManager
- `backend/api/training_sample.py` - 使用 FilePathManager

---

## 总结

本次修复通过7个步骤完整解决了文件上传流程中"文件何时真正可用"的问题：

1. **明确的状态机**: 上传状态从 uploading 到 completed 的完整链路
2. **完整的状态信息**: 数据库中维护每个文件的详细状态
3. **严格的合并触发**: 只在所有chunk接收完成后才触发合并
4. **详细的日志**: 合并过程中的每个关键步骤都有日志
5. **严格的文件校验**: 合并后立即校验文件的完整性和可用性
6. **强制的就绪检查**: 处理前必须检查文件状态
7. **统一的路径管理**: 所有文件路径操作都通过 FilePathManager

这样确保了：
- 日志中能清晰看到完整的流程链路
- 后续处理阶段不再出现文件不存在或不可用的问题
- 日志不再出现"看似正常但流程中断"的情况
