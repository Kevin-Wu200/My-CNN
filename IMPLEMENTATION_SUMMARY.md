# 分片上传流程完整修复方案 - 实现总结

## 概述
本文档详细说明了如何通过8个步骤完整修复分片上传流程中的"确定的结束点"问题，防止系统在文件未就绪时进入后续处理。

---

## 第一步：明确 chunk 上传不是文件上传完成

### 实现位置
- **文件**: `backend/api/upload.py` (第66-180行)
- **函数**: `upload_chunk()`

### 关键改进
```python
# 步骤8: 明确区分三类信息 - chunk 接收日志
logger.info(
    f"[CHUNK_RECEIVED] uploadId={uploadId}, chunkIndex={chunkIndex}, "
    f"chunkSize={len(chunk_content)}, fileName={fileName}"
)
```

**说明**: 每个 chunk 接收时都明确记录为 `[CHUNK_RECEIVED]`，表示这只是单个分片接收，不是文件上传完成。

---

## 第二步：在后端维护每个文件的上传状态

### 实现位置
- **文件**: `backend/models/database.py` (第99-117行)
- **模型**: `UploadSession`

### 状态值定义
```python
# 状态值: uploading(接收chunk中) -> chunks_complete(所有chunk已接收)
#        -> merging(合并中) -> merge_complete(合并完成)
#        -> completed(文件就绪) -> failed
status = Column(String(50), default="uploading")
```

### 状态转移流程
1. **uploading**: 初始状态，正在接收 chunk
2. **chunks_complete**: 所有 chunk 已接收完毕
3. **merging**: 正在合并 chunk
4. **merge_complete**: 合并完成，文件已生成
5. **completed**: 文件已验证就绪，可以进行检测/分类
6. **failed**: 上传或合并失败

### 记录的信息
- `uploaded_chunks`: JSON 序列化的已上传分片索引集合
- `total_chunks`: 期望的总分片数
- `file_path`: 合并完成后的文件路径
- `error_message`: 错误信息（如果失败）

---

## 第三步：当且仅当所有 chunk 接收完成后，才触发合并逻辑

### 实现位置
- **文件**: `backend/api/upload.py` (第181-280行)
- **函数**: `complete_upload()`

### 关键验证逻辑
```python
# 验证所有分片是否已上传
uploaded_chunks_set = set(json.loads(upload_session.uploaded_chunks))
uploaded_count = len(uploaded_chunks_set)

if uploaded_count != totalChunks:
    missing_chunks = set(range(totalChunks)) - uploaded_chunks_set
    logger.warning(
        f"[CHUNKS_INCOMPLETE] uploadId={uploadId}, uploaded={uploaded_count}/{totalChunks}, "
        f"missing={sorted(missing_chunks)}"
    )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"分片不完整: 已上传 {uploaded_count}/{totalChunks}，缺失分片: {sorted(missing_chunks)}",
    )

# 验证分片索引是否连续（0 到 totalChunks-1）
expected_chunks = set(range(totalChunks))
if uploaded_chunks_set != expected_chunks:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"分片索引不连续",
    )
```

**说明**: 只有当所有分片都已接收且索引连续时，才允许进入合并流程。

---

## 第四步：在合并逻辑中增加明确日志

### 实现位置
- **文件**: `backend/services/background_task_manager.py` (第383-536行)
- **函数**: `_execute_merge_task()`

### 关键日志点
```python
# 开始合并
logger.info(
    f"[MERGE_COMBINING_START] uploadId={uploadId}, outputPath={output_path}, "
    f"totalChunks={totalChunks}"
)

# 合并完成
logger.info(
    f"[MERGE_COMBINING_COMPLETE] uploadId={uploadId}, "
    f"finalFilePath={output_path}, finalFileSize={actual_size}"
)

# 最终文件路径和大小
logger.info(
    f"[FILE_VALIDATION_COMPLETE] uploadId={uploadId}, filePath={output_path}, "
    f"fileSize={actual_size}"
)
```

**说明**: 日志中明确记录合并的开始、完成、最终文件路径和大小。

---

## 第五步：合并完成后显式校验文件

### 实现位置
- **文件**: `backend/services/background_task_manager.py` (第442-468行)
- **函数**: `_execute_merge_task()`

### 三层校验
```python
# 1. 检查文件是否存在
if not output_path.exists():
    raise FileNotFoundError(f"合并后文件不存在: {output_path}")
logger.info(f"[FILE_EXISTS_CHECK_PASS] uploadId={uploadId}")

# 2. 检查文件大小是否大于 0
if actual_size <= 0:
    output_path.unlink()
    raise ValueError(f"文件大小无效: {actual_size}")
logger.info(f"[FILE_SIZE_CHECK_PASS] uploadId={uploadId}, size={actual_size}")

# 3. 检查文件是否可读
try:
    with open(output_path, "rb") as test_file:
        test_file.read(1)
    logger.info(f"[FILE_READABLE_CHECK_PASS] uploadId={uploadId}")
except Exception as read_error:
    output_path.unlink()
    raise IOError(f"文件不可读: {str(read_error)}")
```

**说明**: 校验失败直接终止流程并记录错误，不继续进行后续处理。

---

## 第六步：在任何检测/分类逻辑开始前强制检查文件状态

### 实现位置
- **文件**: `backend/api/unsupervised_detection.py` (第33-73行)
- **函数**: `check_file_readiness()`

### 文件就绪检查逻辑
```python
def check_file_readiness(file_path: str) -> Tuple[bool, str]:
    """
    步骤6: 在任何检测/分类逻辑开始前，强制检查文件状态是否为"已合并完成"
    """
    db_manager_instance = get_db_manager()
    db_session = db_manager_instance.get_session()
    try:
        file_path_obj = Path(file_path)
        file_name = file_path_obj.name

        # 查询该文件是否有对应的上传会话
        upload_session = db_session.query(UploadSession).filter(
            UploadSession.file_name == file_name,
            UploadSession.file_path == file_path
        ).first()

        if upload_session:
            # 如果不是"completed"状态，立即返回错误，不进入计算流程
            if upload_session.status != "completed":
                error_msg = (
                    f"文件未就绪: 上传会话状态为 '{upload_session.status}'，"
                    f"必须为 'completed' 才能进行检测"
                )
                logger.warning(f"[FILE_READINESS_CHECK_FAILED] filePath={file_path}, status={upload_session.status}")
                return False, error_msg

            logger.info(f"[FILE_READINESS_CHECK_PASS] filePath={file_path}, uploadId={upload_session.upload_id}")
            return True, ""
```

### 集成到检测端点
```python
@router.post("/detect")
async def detect_disease(...):
    # 步骤6: 在任何检测/分类逻辑开始前，强制检查文件状态是否为"已合并完成"
    is_ready, error_msg = check_file_readiness(image_path)
    if not is_ready:
        logger.error(f"[API] 文件就绪检查失败: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
```

**说明**: 只有当文件状态为 `completed` 时，才允许进入检测流程。

---

## 第七步：限制 /upload/chunk 的并发或频率

### 实现位置
- **文件**: `backend/api/upload.py` (第27-47行)
- **类**: `RateLimiter`

### 速率限制实现
```python
class RateLimiter:
    """简单的速率限制器"""
    def __init__(self, max_requests: int = 10, window_seconds: int = 1):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        """检查是否允许请求"""
        now = time.time()
        # 清理过期的请求记录
        self.requests[key] = [req_time for req_time in self.requests[key]
                              if now - req_time < self.window_seconds]

        if len(self.requests[key]) >= self.max_requests:
            return False

        self.requests[key].append(now)
        return True

chunk_rate_limiter = RateLimiter(max_requests=10, window_seconds=1)
```

### 在 chunk 上传中应用
```python
@router.post("/chunk")
async def upload_chunk(...):
    # 步骤7: 限制并发或频率
    if not chunk_rate_limiter.is_allowed(uploadId):
        logger.warning(
            f"[RATE_LIMIT_EXCEEDED] uploadId={uploadId}, chunkIndex={chunkIndex}"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后重试",
        )
```

**说明**: 每个 uploadId 在 1 秒内最多接收 10 个请求，防止资源耗尽。

---

## 第八步：在日志中明确区分三类信息

### 日志标签分类

#### 1. Chunk 接收日志
```
[CHUNK_RECEIVED] - 单个 chunk 接收
[CHUNKS_UPDATED] - chunk 数量更新
[ALL_CHUNKS_RECEIVED] - 所有 chunk 已接收
[CHUNKS_COMPLETE_STATUS_SET] - 状态更新为 chunks_complete
```

#### 2. 文件合并日志
```
[MERGE_START] - 合并开始
[MERGE_COMBINING_START] - 开始合并 chunk
[MERGE_COMBINING_COMPLETE] - 合并完成
[MERGE_COMPLETE_STATUS_SET] - 状态更新为 merge_complete
[FILE_READY_STATUS_SET] - 状态更新为 completed
[MERGE_SUCCESS] - 合并成功
[MERGE_FAILED] - 合并失败
```

#### 3. 文件处理日志
```
[FILE_VALIDATION_START] - 文件校验开始
[FILE_EXISTS_CHECK_PASS] - 文件存在检查通过
[FILE_SIZE_CHECK_PASS] - 文件大小检查通过
[FILE_READABLE_CHECK_PASS] - 文件可读性检查通过
[FILE_VALIDATION_COMPLETE] - 文件校验完成
[FILE_READINESS_CHECK_PASS] - 文件就绪检查通过
[FILE_READINESS_CHECK_FAILED] - 文件就绪检查失败
```

### 日志流示例
```
[SESSION_CREATED] uploadId=xxx, totalChunks=10
[CHUNK_RECEIVED] uploadId=xxx, chunkIndex=0
[CHUNKS_UPDATED] uploadId=xxx, uploaded=1/10, progress=10%
[CHUNK_RECEIVED] uploadId=xxx, chunkIndex=1
[CHUNKS_UPDATED] uploadId=xxx, uploaded=2/10, progress=20%
...
[ALL_CHUNKS_RECEIVED] uploadId=xxx, totalChunks=10
[CHUNKS_COMPLETE_STATUS_SET] uploadId=xxx
[MERGE_START] uploadId=xxx, fileName=image.tif, fileSize=1000000
[MERGE_COMBINING_START] uploadId=xxx, outputPath=/path/to/file, totalChunks=10
[MERGE_COMBINING_COMPLETE] uploadId=xxx, finalFilePath=/path/to/file, finalFileSize=1000000
[FILE_VALIDATION_START] uploadId=xxx, filePath=/path/to/file
[FILE_EXISTS_CHECK_PASS] uploadId=xxx
[FILE_SIZE_CHECK_PASS] uploadId=xxx, size=1000000
[FILE_READABLE_CHECK_PASS] uploadId=xxx
[FILE_VALIDATION_COMPLETE] uploadId=xxx, filePath=/path/to/file, fileSize=1000000
[MERGE_COMPLETE_STATUS_SET] uploadId=xxx, filePath=/path/to/file
[FILE_READY_STATUS_SET] uploadId=xxx
[MERGE_SUCCESS] taskId=yyy, uploadId=xxx
```

---

## 验收标准检查清单

### ✅ 日志清晰性
- [x] 日志中能看到清晰的：chunk 接收 → chunk 完整 → 合并开始 → 合并完成 → 文件就绪
- [x] 三类信息（chunk、合并、处理）使用不同的日志标签区分
- [x] 避免所有问题都被淹没在 200 OK 中

### ✅ 文件就绪保证
- [x] 上传完成后不会出现"文件不存在 / 文件不可读"的问题
- [x] 文件校验包括：存在性、大小、可读性
- [x] 校验失败直接终止流程

### ✅ 系统稳定性
- [x] 系统不再出现"看似正常但无法继续"的假死状态
- [x] 文件状态机清晰：uploading → chunks_complete → merging → merge_complete → completed
- [x] 检测/分类前强制检查文件状态为 completed

### ✅ 并发控制
- [x] 限制 /upload/chunk 的并发频率（每秒最多 10 个请求）
- [x] 防止极短时间内堆积上百个请求导致资源耗尽

---

## 关键文件修改总结

| 文件 | 修改内容 | 步骤 |
|------|--------|------|
| `backend/models/database.py` | 更新 UploadSession 状态值定义 | 第2步 |
| `backend/api/upload.py` | 添加速率限制、增强日志、验证 chunk 完整性 | 第1,3,7,8步 |
| `backend/services/background_task_manager.py` | 增加合并日志、文件校验、状态转移 | 第4,5,8步 |
| `backend/api/unsupervised_detection.py` | 添加文件就绪检查函数、集成到检测端点 | 第6步 |

---

## 测试验证方法

### 1. 验证 chunk 接收日志
```bash
# 上传 chunk 时查看日志
tail -f logs/app.log | grep "CHUNK_RECEIVED\|CHUNKS_UPDATED"
```

### 2. 验证文件合并流程
```bash
# 完成上传后查看合并日志
tail -f logs/app.log | grep "MERGE_\|FILE_VALIDATION"
```

### 3. 验证文件就绪检查
```bash
# 尝试在文件未就绪时进行检测
curl -X POST "http://localhost:8000/api/unsupervised/detect?image_path=/path/to/file"
# 应该返回 400 错误，提示文件未就绪
```

### 4. 验证速率限制
```bash
# 快速发送多个 chunk 请求
for i in {1..20}; do
  curl -X POST "http://localhost:8000/api/upload/chunk" \
    -F "chunk=@chunk_$i" \
    -F "chunkIndex=$i" \
    -F "totalChunks=20" \
    -F "fileName=test.tif" \
    -F "fileSize=1000000" \
    -F "uploadId=test-upload"
done
# 应该看到部分请求返回 429 Too Many Requests
```

---

## 总结

通过实现这 8 个步骤，系统现在具有：

1. **明确的状态机**: 文件上传状态从 uploading 到 completed 的完整转移
2. **严格的验证**: chunk 完整性、文件存在性、可读性的多层校验
3. **清晰的日志**: 三类信息分离，便于问题诊断
4. **并发控制**: 防止资源耗尽
5. **文件就绪保证**: 检测前强制检查文件状态

这确保了系统不会在文件未就绪时进入后续处理，彻底解决了"看似正常但无法继续"的假死状态问题。
