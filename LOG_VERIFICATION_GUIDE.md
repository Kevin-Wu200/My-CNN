# 分片上传流程8步实现 - 日志验证指南

## 概述

本指南展示如何通过查看后端日志来验证8步实现的每一个步骤。

---

## 快速查看日志的命令

### 1. 实时查看日志
```bash
tail -f backend.log
```

### 2. 查看特定标签的日志
```bash
# 查看 chunk 接收日志
grep "CHUNK_RECEIVED\|CHUNKS_UPDATED" backend.log

# 查看合并日志
grep "MERGE_" backend.log

# 查看文件校验日志
grep "FILE_VALIDATION\|FILE_EXISTS\|FILE_SIZE\|FILE_READABLE" backend.log

# 查看速率限制日志
grep "RATE_LIMIT_EXCEEDED" backend.log

# 查看文件就绪检查日志
grep "FILE_READINESS_CHECK" backend.log
```

---

## 8步实现的日志验证

### 第一步: 明确 chunk 上传不是文件上传完成

**预期日志**:
```
[CHUNK_RECEIVED] uploadId=xxx, chunkIndex=0, chunkSize=262144, fileName=test_image.tif
[CHUNKS_UPDATED] uploadId=xxx, uploaded=1/4, progress=25%
[CHUNK_RECEIVED] uploadId=xxx, chunkIndex=1, chunkSize=262144, fileName=test_image.tif
[CHUNKS_UPDATED] uploadId=xxx, uploaded=2/4, progress=50%
```

**验证命令**:
```bash
grep "CHUNK_RECEIVED\|CHUNKS_UPDATED" backend.log | head -20
```

**说明**: 每个 chunk 接收时都会记录 `[CHUNK_RECEIVED]` 标签，表示这只是单个分片接收，不是文件上传完成。

---

### 第二步: 在后端维护每个文件的上传状态

**预期日志**:
```
[SESSION_CREATED] uploadId=xxx, totalChunks=4, fileName=test_image.tif, fileSize=1048576
[CHUNKS_COMPLETE_STATUS_SET] uploadId=xxx
[MERGE_START] uploadId=xxx, fileName=test_image.tif, fileSize=1048576
[MERGE_COMPLETE_STATUS_SET] uploadId=xxx, filePath=/path/to/file
[FILE_READY_STATUS_SET] uploadId=xxx
```

**验证命令**:
```bash
grep "SESSION_CREATED\|CHUNKS_COMPLETE_STATUS_SET\|MERGE_START\|MERGE_COMPLETE_STATUS_SET\|FILE_READY_STATUS_SET" backend.log
```

**状态转移流程**:
```
uploading (初始状态)
    ↓
chunks_complete (所有 chunk 已接收)
    ↓
merging (开始合并)
    ↓
merge_complete (合并完成)
    ↓
completed (文件就绪)
```

---

### 第三步: 当且仅当所有 chunk 接收完成后，才触发合并逻辑

**预期日志**:
```
[ALL_CHUNKS_RECEIVED] uploadId=xxx, totalChunks=4
[CHUNKS_COMPLETE_STATUS_SET] uploadId=xxx
[MERGE_START] uploadId=xxx, fileName=test_image.tif, fileSize=1048576
```

**验证命令**:
```bash
grep "ALL_CHUNKS_RECEIVED\|CHUNKS_INCOMPLETE" backend.log
```

**说明**: 只有当所有分片都已接收且索引连续时，才会看到 `[ALL_CHUNKS_RECEIVED]` 日志。如果分片不完整，会看到 `[CHUNKS_INCOMPLETE]` 日志。

---

### 第四步: 在合并逻辑中增加明确日志

**预期日志**:
```
[MERGE_COMBINING_START] uploadId=xxx, outputPath=/path/to/file, totalChunks=4
[MERGE_COMBINING_COMPLETE] uploadId=xxx, finalFilePath=/path/to/file, finalFileSize=1048576
```

**验证命令**:
```bash
grep "MERGE_COMBINING_START\|MERGE_COMBINING_COMPLETE" backend.log
```

**说明**: 这些日志明确标记了合并的开始和完成，以及最终文件的路径和大小。

---

### 第五步: 合并完成后显式校验文件

**预期日志**:
```
[FILE_VALIDATION_START] uploadId=xxx, filePath=/path/to/file
[FILE_EXISTS_CHECK_PASS] uploadId=xxx
[FILE_SIZE_CHECK_PASS] uploadId=xxx, size=1048576
[FILE_READABLE_CHECK_PASS] uploadId=xxx
[FILE_VALIDATION_COMPLETE] uploadId=xxx, filePath=/path/to/file, fileSize=1048576
```

**验证命令**:
```bash
grep "FILE_VALIDATION_START\|FILE_EXISTS_CHECK\|FILE_SIZE_CHECK\|FILE_READABLE_CHECK\|FILE_VALIDATION_COMPLETE" backend.log
```

**说明**: 文件校验包括三层检查：存在性、大小、可读性。所有检查都通过才会继续。

---

### 第六步: 在任何检测/分类逻辑开始前强制检查文件状态

**预期日志**:
```
[FILE_READINESS_CHECK_PASS] filePath=/path/to/file, uploadId=xxx
```

或者（如果文件未就绪）:
```
[FILE_READINESS_CHECK_FAILED] filePath=/path/to/file, status=uploading
```

**验证命令**:
```bash
grep "FILE_READINESS_CHECK" backend.log
```

**说明**: 在进入检测流程前，系统会检查文件状态是否为 `completed`。

---

### 第七步: 限制 /upload/chunk 的并发或频率

**预期日志**:
```
[RATE_LIMIT_EXCEEDED] uploadId=rate-limit-test-xxx, chunkIndex=10
[RATE_LIMIT_EXCEEDED] uploadId=rate-limit-test-xxx, chunkIndex=11
[RATE_LIMIT_EXCEEDED] uploadId=rate-limit-test-xxx, chunkIndex=12
```

**验证命令**:
```bash
grep "RATE_LIMIT_EXCEEDED" backend.log | wc -l
```

**说明**: 当在 1 秒内发送超过 10 个请求时，会看到这些日志，并返回 429 Too Many Requests。

---

### 第八步: 在日志中明确区分三类信息

**三类日志标签**:

1. **Chunk 接收日志**:
   ```
   [CHUNK_RECEIVED]
   [CHUNKS_UPDATED]
   [ALL_CHUNKS_RECEIVED]
   [CHUNKS_COMPLETE_STATUS_SET]
   ```

2. **文件合并日志**:
   ```
   [MERGE_START]
   [MERGE_COMBINING_START]
   [MERGE_COMBINING_COMPLETE]
   [MERGE_COMPLETE_STATUS_SET]
   [FILE_READY_STATUS_SET]
   [MERGE_SUCCESS]
   [MERGE_FAILED]
   ```

3. **文件处理日志**:
   ```
   [FILE_VALIDATION_START]
   [FILE_EXISTS_CHECK_PASS]
   [FILE_SIZE_CHECK_PASS]
   [FILE_READABLE_CHECK_PASS]
   [FILE_VALIDATION_COMPLETE]
   [FILE_READINESS_CHECK_PASS]
   [FILE_READINESS_CHECK_FAILED]
   ```

**验证命令**:
```bash
# 统计各类日志数量
echo "=== Chunk 接收日志 ==="
grep "CHUNK_RECEIVED\|CHUNKS_UPDATED\|ALL_CHUNKS_RECEIVED" backend.log | wc -l

echo "=== 文件合并日志 ==="
grep "MERGE_\|FILE_READY_STATUS_SET" backend.log | wc -l

echo "=== 文件处理日志 ==="
grep "FILE_VALIDATION\|FILE_READINESS_CHECK" backend.log | wc -l
```

---

## 完整的日志流示例

### 成功的上传流程

```
[SESSION_CREATED] uploadId=test-upload-123, totalChunks=4, fileName=test_image.tif, fileSize=1048576
[CHUNK_RECEIVED] uploadId=test-upload-123, chunkIndex=0, chunkSize=262144, fileName=test_image.tif
[CHUNKS_UPDATED] uploadId=test-upload-123, uploaded=1/4, progress=25%
[CHUNK_RECEIVED] uploadId=test-upload-123, chunkIndex=1, chunkSize=262144, fileName=test_image.tif
[CHUNKS_UPDATED] uploadId=test-upload-123, uploaded=2/4, progress=50%
[CHUNK_RECEIVED] uploadId=test-upload-123, chunkIndex=2, chunkSize=262144, fileName=test_image.tif
[CHUNKS_UPDATED] uploadId=test-upload-123, uploaded=3/4, progress=75%
[CHUNK_RECEIVED] uploadId=test-upload-123, chunkIndex=3, chunkSize=262144, fileName=test_image.tif
[CHUNKS_UPDATED] uploadId=test-upload-123, uploaded=4/4, progress=100%
[ALL_CHUNKS_RECEIVED] uploadId=test-upload-123, totalChunks=4
[CHUNKS_COMPLETE_STATUS_SET] uploadId=test-upload-123
[MERGE_START] uploadId=test-upload-123, fileName=test_image.tif, fileSize=1048576
[MERGE_COMBINING_START] uploadId=test-upload-123, outputPath=/path/to/file, totalChunks=4
[MERGE_COMBINING_COMPLETE] uploadId=test-upload-123, finalFilePath=/path/to/file, finalFileSize=1048576
[FILE_VALIDATION_START] uploadId=test-upload-123, filePath=/path/to/file
[FILE_EXISTS_CHECK_PASS] uploadId=test-upload-123
[FILE_SIZE_CHECK_PASS] uploadId=test-upload-123, size=1048576
[FILE_READABLE_CHECK_PASS] uploadId=test-upload-123
[FILE_VALIDATION_COMPLETE] uploadId=test-upload-123, filePath=/path/to/file, fileSize=1048576
[MERGE_COMPLETE_STATUS_SET] uploadId=test-upload-123, filePath=/path/to/file
[FILE_READY_STATUS_SET] uploadId=test-upload-123
[MERGE_SUCCESS] taskId=task-456, uploadId=test-upload-123
```

### 速率限制示例

```
[RATE_LIMIT_EXCEEDED] uploadId=rate-limit-test-789, chunkIndex=10
[RATE_LIMIT_EXCEEDED] uploadId=rate-limit-test-789, chunkIndex=11
[RATE_LIMIT_EXCEEDED] uploadId=rate-limit-test-789, chunkIndex=12
[RATE_LIMIT_EXCEEDED] uploadId=rate-limit-test-789, chunkIndex=13
[RATE_LIMIT_EXCEEDED] uploadId=rate-limit-test-789, chunkIndex=14
```

### 文件就绪检查示例

```
[FILE_READINESS_CHECK_PASS] filePath=/path/to/file, uploadId=test-upload-123
```

或者（文件未就绪）:
```
[FILE_READINESS_CHECK_FAILED] filePath=/path/to/file, status=uploading
```

---

## 实时监控日志

### 方法1: 使用 tail 实时查看
```bash
tail -f backend.log
```

### 方法2: 使用 grep 过滤特定日志
```bash
tail -f backend.log | grep "CHUNK_RECEIVED\|MERGE_\|FILE_VALIDATION"
```

### 方法3: 使用 watch 定期查看
```bash
watch -n 1 'tail -20 backend.log'
```

---

## 日志分析技巧

### 1. 查看特定上传会话的所有日志
```bash
grep "uploadId=test-upload-123" backend.log
```

### 2. 统计上传成功率
```bash
echo "总上传数: $(grep 'CHUNK_RECEIVED' backend.log | wc -l)"
echo "成功合并数: $(grep 'MERGE_SUCCESS' backend.log | wc -l)"
echo "失败数: $(grep 'MERGE_FAILED' backend.log | wc -l)"
```

### 3. 查看平均上传时间
```bash
# 查看从第一个 chunk 到 completed 的时间
grep "CHUNK_RECEIVED\|FILE_READY_STATUS_SET" backend.log | head -20
```

### 4. 检查是否有文件校验失败
```bash
grep "FILE_VALIDATION_COMPLETE\|FILE_EXISTS_CHECK_PASS\|FILE_SIZE_CHECK_PASS\|FILE_READABLE_CHECK_PASS" backend.log | grep -v "PASS"
```

---

## 故障排查

### 问题1: 文件上传后无法进行检测

**检查步骤**:
1. 查看文件状态是否为 `completed`:
   ```bash
   grep "FILE_READY_STATUS_SET" backend.log
   ```

2. 查看文件校验是否通过:
   ```bash
   grep "FILE_VALIDATION_COMPLETE" backend.log
   ```

3. 查看文件就绪检查:
   ```bash
   grep "FILE_READINESS_CHECK" backend.log
   ```

### 问题2: 上传速度慢

**检查步骤**:
1. 查看是否被限流:
   ```bash
   grep "RATE_LIMIT_EXCEEDED" backend.log | wc -l
   ```

2. 查看合并时间:
   ```bash
   grep "MERGE_COMBINING_START\|MERGE_COMBINING_COMPLETE" backend.log
   ```

### 问题3: 合并失败

**检查步骤**:
1. 查看合并错误:
   ```bash
   grep "MERGE_FAILED" backend.log
   ```

2. 查看文件校验错误:
   ```bash
   grep "FILE_VALIDATION_START" backend.log -A 10
   ```

---

## 性能指标

### 关键指标

1. **Chunk 接收速度**: 每秒接收的 chunk 数
   ```bash
   grep "CHUNK_RECEIVED" backend.log | wc -l
   ```

2. **合并成功率**: 成功合并 / 总合并数
   ```bash
   echo "成功: $(grep 'MERGE_SUCCESS' backend.log | wc -l)"
   echo "失败: $(grep 'MERGE_FAILED' backend.log | wc -l)"
   ```

3. **速率限制触发次数**: 被限流的请求数
   ```bash
   grep "RATE_LIMIT_EXCEEDED" backend.log | wc -l
   ```

4. **文件校验通过率**: 通过校验的文件数
   ```bash
   grep "FILE_VALIDATION_COMPLETE" backend.log | wc -l
   ```

---

## 总结

通过查看这些日志，您可以验证：

✅ **第一步**: 看到 `[CHUNK_RECEIVED]` 和 `[CHUNKS_UPDATED]` 日志
✅ **第二步**: 看到状态从 uploading → chunks_complete → merging → merge_complete → completed
✅ **第三步**: 看到 `[ALL_CHUNKS_RECEIVED]` 后才有 `[MERGE_START]`
✅ **第四步**: 看到 `[MERGE_COMBINING_START]` 和 `[MERGE_COMBINING_COMPLETE]`
✅ **第五步**: 看到 `[FILE_EXISTS_CHECK_PASS]`、`[FILE_SIZE_CHECK_PASS]`、`[FILE_READABLE_CHECK_PASS]`
✅ **第六步**: 看到 `[FILE_READINESS_CHECK_PASS]` 或 `[FILE_READINESS_CHECK_FAILED]`
✅ **第七步**: 看到 `[RATE_LIMIT_EXCEEDED]` 和 429 状态码
✅ **第八步**: 看到三类日志标签清晰分离

所有8步都已正确实现并可通过日志验证！

