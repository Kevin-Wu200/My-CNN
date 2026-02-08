# API接口文档

## 基础信息

- **Base URL**: `http://localhost:8000`
- **API文档**: `http://localhost:8000/docs`
- **内容类型**: `application/json`（除文件上传外）

## 通用响应格式

### 成功响应
```json
{
  "status": "success",
  "data": { ... },
  "message": "操作成功"
}
```

### 错误响应
```json
{
  "status": "error",
  "error": "错误信息",
  "detail": "详细错误描述"
}
```

## 1. 健康检查接口

### 1.1 健康检查

**接口**: `GET /health`

**描述**: 检查服务健康状态

**响应示例**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00"
}
```

### 1.2 根路由

**接口**: `GET /`

**描述**: 获取API基本信息

**响应示例**:
```json
{
  "message": "遥感影像病害木检测系统API",
  "version": "1.0.0",
  "docs": "/docs"
}
```

## 2. 文件上传接口

### 2.1 上传分片

**接口**: `POST /api/upload/chunk`

**描述**: 上传单个文件分片

**请求参数**:
- `uploadId` (string, required): 上传会话ID
- `chunkIndex` (integer, required): 分片索引（从0开始）
- `totalChunks` (integer, required): 总分片数
- `file` (file, required): 分片文件数据

**Content-Type**: `multipart/form-data`

**响应示例**:
```json
{
  "status": "success",
  "message": "分片上传成功",
  "data": {
    "uploadId": "uuid-string",
    "chunkIndex": 0,
    "uploadedChunks": 1,
    "totalChunks": 10,
    "progress": 10.0
  }
}
```

### 2.2 完成上传

**接口**: `POST /api/upload/complete`

**描述**: 通知服务器所有分片已上传，触发文件合并

**请求体**:
```json
{
  "uploadId": "uuid-string",
  "fileName": "image.tif",
  "fileSize": 1048576,
  "totalChunks": 10
}
```

**响应示例**:
```json
{
  "status": "success",
  "message": "文件合并中",
  "data": {
    "uploadId": "uuid-string",
    "status": "merging"
  }
}
```

### 2.3 查询上传状态

**接口**: `GET /api/upload/status/{uploadId}`

**描述**: 查询上传会话状态和进度

**路径参数**:
- `uploadId` (string, required): 上传会话ID

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "uploadId": "uuid-string",
    "fileName": "image.tif",
    "fileSize": 1048576,
    "uploadedChunks": 10,
    "totalChunks": 10,
    "status": "completed",
    "progress": 100.0,
    "filePath": "/path/to/merged/file.tif",
    "createdAt": "2024-01-01T12:00:00",
    "updatedAt": "2024-01-01T12:05:00"
  }
}
```

**状态说明**:
- `uploading`: 正在上传分片
- `chunks_complete`: 所有分片上传完成
- `merging`: 正在合并文件
- `merge_complete`: 文件合并完成
- `completed`: 上传完成
- `failed`: 上传失败

## 3. 无监督检测接口

### 3.1 上传检测影像

**接口**: `POST /api/unsupervised/upload-image`

**描述**: 上传待检测的遥感影像

**请求参数**:
- `file` (file, required): 影像文件（.tif或.img格式）

**Content-Type**: `multipart/form-data`

**响应示例**:
```json
{
  "status": "success",
  "message": "影像上传成功",
  "data": {
    "filePath": "/path/to/image.tif",
    "fileName": "image.tif",
    "fileSize": 1048576
  }
}
```

### 3.2 启动无监督检测

**接口**: `POST /api/unsupervised/detect`

**描述**: 启动无监督病害木检测任务

**请求体**:
```json
{
  "filePath": "/path/to/image.tif",
  "n_clusters": 5,
  "min_area": 100
}
```

**参数说明**:
- `filePath` (string, required): 影像文件路径
- `n_clusters` (integer, optional): 聚类数量，默认5
- `min_area` (float, optional): 最小面积（平方米），默认100

**响应示例**:
```json
{
  "status": "success",
  "message": "检测任务已启动",
  "data": {
    "taskId": "task-uuid",
    "status": "running"
  }
}
```

### 3.3 查询检测任务状态

**接口**: `GET /api/unsupervised/task-status/{taskId}`

**描述**: 查询无监督检测任务的状态和进度

**路径参数**:
- `taskId` (string, required): 任务ID

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "taskId": "task-uuid",
    "status": "running",
    "progress": 45.5,
    "message": "正在处理第5个瓦片，共10个",
    "result": null,
    "createdAt": "2024-01-01T12:00:00",
    "updatedAt": "2024-01-01T12:02:00"
  }
}
```

**任务完成后的响应**:
```json
{
  "status": "success",
  "data": {
    "taskId": "task-uuid",
    "status": "completed",
    "progress": 100.0,
    "message": "检测完成",
    "result": {
      "geojson": { ... },
      "statistics": {
        "totalArea": 1000.5,
        "diseaseArea": 150.2,
        "diseaseRate": 15.02,
        "patchCount": 25
      },
      "outputPath": "/path/to/result.geojson"
    },
    "createdAt": "2024-01-01T12:00:00",
    "completedAt": "2024-01-01T12:10:00"
  }
}
```

**任务状态说明**:
- `pending`: 等待执行
- `running`: 正在执行
- `completed`: 执行完成
- `failed`: 执行失败
- `cancelled`: 已取消

### 3.4 取消检测任务

**接口**: `POST /api/unsupervised/cancel/{taskId}`

**描述**: 取消正在运行的检测任务

**路径参数**:
- `taskId` (string, required): 任务ID

**响应示例**:
```json
{
  "status": "success",
  "message": "任务已取消",
  "data": {
    "taskId": "task-uuid",
    "status": "cancelled"
  }
}
```

## 4. 监督检测接口

### 4.1 获取可用模型列表

**接口**: `GET /api/detection/models`

**描述**: 获取所有已训练的可用模型

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "models": [
      {
        "modelId": "model-uuid-1",
        "modelName": "VGG16_2024-01-01",
        "backbone": "vgg16",
        "accuracy": 0.95,
        "createdAt": "2024-01-01T12:00:00"
      },
      {
        "modelId": "model-uuid-2",
        "modelName": "ResNet50_2024-01-02",
        "backbone": "resnet50",
        "accuracy": 0.97,
        "createdAt": "2024-01-02T12:00:00"
      }
    ]
  }
}
```

### 4.2 启动监督检测

**接口**: `POST /api/detection/detect`

**描述**: 使用训练好的模型进行病害木检测

**请求体**:
```json
{
  "modelId": "model-uuid",
  "filePath": "/path/to/image.tif",
  "confidence_threshold": 0.8
}
```

**参数说明**:
- `modelId` (string, required): 模型ID
- `filePath` (string, required): 影像文件路径
- `confidence_threshold` (float, optional): 置信度阈值，默认0.8

**响应示例**:
```json
{
  "status": "success",
  "message": "检测任务已启动",
  "data": {
    "taskId": "task-uuid",
    "status": "running"
  }
}
```

## 5. 训练样本接口

### 5.1 上传训练样本

**接口**: `POST /api/training-sample/upload`

**描述**: 上传训练样本影像

**请求参数**:
- `file` (file, required): 样本文件
- `label` (string, required): 样本标签（disease/healthy）
- `description` (string, optional): 样本描述

**Content-Type**: `multipart/form-data`

**响应示例**:
```json
{
  "status": "success",
  "message": "样本上传成功",
  "data": {
    "sampleId": "sample-uuid",
    "fileName": "sample.tif",
    "label": "disease",
    "filePath": "/path/to/sample.tif"
  }
}
```

### 5.2 获取样本列表

**接口**: `GET /api/training-sample/list`

**描述**: 获取所有训练样本列表

**查询参数**:
- `label` (string, optional): 按标签筛选
- `page` (integer, optional): 页码，默认1
- `pageSize` (integer, optional): 每页数量，默认20

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "samples": [
      {
        "sampleId": "sample-uuid-1",
        "fileName": "sample1.tif",
        "label": "disease",
        "fileSize": 1048576,
        "createdAt": "2024-01-01T12:00:00"
      }
    ],
    "total": 100,
    "page": 1,
    "pageSize": 20
  }
}
```

### 5.3 删除训练样本

**接口**: `DELETE /api/training-sample/{sampleId}`

**描述**: 删除指定的训练样本

**路径参数**:
- `sampleId` (string, required): 样本ID

**响应示例**:
```json
{
  "status": "success",
  "message": "样本已删除"
}
```

## 6. 模型训练接口

### 6.1 启动模型训练

**接口**: `POST /api/training/start`

**描述**: 启动模型训练任务

**请求体**:
```json
{
  "modelName": "VGG16_Custom",
  "backbone": "vgg16",
  "epochs": 100,
  "batchSize": 32,
  "learningRate": 0.001,
  "sampleIds": ["sample-uuid-1", "sample-uuid-2"]
}
```

**参数说明**:
- `modelName` (string, required): 模型名称
- `backbone` (string, required): 主干网络（vgg11/vgg16/resnet18/resnet50等）
- `epochs` (integer, optional): 训练轮数，默认100
- `batchSize` (integer, optional): 批次大小，默认32
- `learningRate` (float, optional): 学习率，默认0.001
- `sampleIds` (array, optional): 指定样本ID列表，不指定则使用所有样本

**响应示例**:
```json
{
  "status": "success",
  "message": "训练任务已启动",
  "data": {
    "taskId": "task-uuid",
    "status": "running"
  }
}
```

### 6.2 查询训练任务状态

**接口**: `GET /api/training/task-status/{taskId}`

**描述**: 查询模型训练任务的状态和进度

**路径参数**:
- `taskId` (string, required): 任务ID

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "taskId": "task-uuid",
    "status": "running",
    "progress": 50.0,
    "currentEpoch": 50,
    "totalEpochs": 100,
    "metrics": {
      "loss": 0.25,
      "accuracy": 0.92,
      "valLoss": 0.30,
      "valAccuracy": 0.90
    },
    "createdAt": "2024-01-01T12:00:00",
    "updatedAt": "2024-01-01T13:00:00"
  }
}
```

### 6.3 停止训练任务

**接口**: `POST /api/training/stop/{taskId}`

**描述**: 停止正在运行的训练任务

**路径参数**:
- `taskId` (string, required): 任务ID

**响应示例**:
```json
{
  "status": "success",
  "message": "训练任务已停止",
  "data": {
    "taskId": "task-uuid",
    "status": "stopped"
  }
}
```

## 7. 任务管理接口

### 7.1 获取任务列表

**接口**: `GET /api/task/list`

**描述**: 获取所有任务列表

**查询参数**:
- `type` (string, optional): 任务类型（detection/training/unsupervised）
- `status` (string, optional): 任务状态
- `page` (integer, optional): 页码
- `pageSize` (integer, optional): 每页数量

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "tasks": [
      {
        "taskId": "task-uuid",
        "type": "unsupervised",
        "status": "completed",
        "progress": 100.0,
        "createdAt": "2024-01-01T12:00:00",
        "completedAt": "2024-01-01T12:10:00"
      }
    ],
    "total": 50,
    "page": 1,
    "pageSize": 20
  }
}
```

### 7.2 获取任务详情

**接口**: `GET /api/task/status/{taskId}`

**描述**: 获取指定任务的详细信息

**路径参数**:
- `taskId` (string, required): 任务ID

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "taskId": "task-uuid",
    "type": "unsupervised",
    "status": "completed",
    "progress": 100.0,
    "message": "检测完成",
    "result": { ... },
    "createdAt": "2024-01-01T12:00:00",
    "completedAt": "2024-01-01T12:10:00"
  }
}
```

### 7.3 删除任务

**接口**: `DELETE /api/task/{taskId}`

**描述**: 删除指定任务及其结果

**路径参数**:
- `taskId` (string, required): 任务ID

**响应示例**:
```json
{
  "status": "success",
  "message": "任务已删除"
}
```

## 错误码说明

| 错误码 | 说明 |
|--------|------|
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 409 | 资源冲突（如任务已存在） |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 |

## 速率限制

- 上传接口：50请求/秒
- 其他接口：100请求/秒

超过限制将返回429状态码。

## 使用示例

### Python示例

```python
import requests

# 1. 上传影像
files = {'file': open('image.tif', 'rb')}
response = requests.post(
    'http://localhost:8000/api/unsupervised/upload-image',
    files=files
)
file_path = response.json()['data']['filePath']

# 2. 启动检测
data = {
    'filePath': file_path,
    'n_clusters': 5,
    'min_area': 100
}
response = requests.post(
    'http://localhost:8000/api/unsupervised/detect',
    json=data
)
task_id = response.json()['data']['taskId']

# 3. 轮询任务状态
import time
while True:
    response = requests.get(
        f'http://localhost:8000/api/unsupervised/task-status/{task_id}'
    )
    task = response.json()['data']
    print(f"进度: {task['progress']}%")

    if task['status'] in ['completed', 'failed', 'cancelled']:
        break

    time.sleep(2)

# 4. 获取结果
if task['status'] == 'completed':
    result = task['result']
    print(f"检测完成，病害率: {result['statistics']['diseaseRate']}%")
```

### JavaScript示例

```javascript
// 1. 上传影像
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const uploadResponse = await fetch(
  'http://localhost:8000/api/unsupervised/upload-image',
  {
    method: 'POST',
    body: formData
  }
);
const { filePath } = (await uploadResponse.json()).data;

// 2. 启动检测
const detectResponse = await fetch(
  'http://localhost:8000/api/unsupervised/detect',
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filePath,
      n_clusters: 5,
      min_area: 100
    })
  }
);
const { taskId } = (await detectResponse.json()).data;

// 3. 轮询任务状态
const pollStatus = async () => {
  const response = await fetch(
    `http://localhost:8000/api/unsupervised/task-status/${taskId}`
  );
  const { data } = await response.json();

  console.log(`进度: ${data.progress}%`);

  if (data.status === 'completed') {
    console.log('检测完成', data.result);
  } else if (data.status === 'running') {
    setTimeout(pollStatus, 2000);
  }
};

pollStatus();
```
