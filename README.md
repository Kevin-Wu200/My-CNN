# 遥感影像病害木检测系统

基于深度学习和传统方法的遥感影像病害木智能检测系统，支持模型训练、有监督检测和无监督检测。

## 功能特性

### 核心功能
- **模型训练流程**：样本上传 → 预处理 → 模型配置 → 训练
- **有监督检测**：基于深度学习的病害木检测，使用 PyTorch 深度学习框架
- **无监督检测**：基于光谱、纹理、空间特征的传统方法检测
- **任务管理**：实时进度监控、历史查询、任务控制（启动/停止）
- **用户管理**：手机号登录、历史记录追踪

### 技术亮点
- **高性能分片上传**：5MB 分片、2 并发上传、智能重试机制、速率限制保护
- **并行处理优化**：自动 CPU 检测、动态工作进程、内存监控保护
- **任务状态管理**：强单例模式、状态持久化、中断类型区分
- **文件清理机制**：自动清理、安全验证、延迟执行
- **遥感图像处理**：1024×1024 统一分块、GDAL 集成、空间参考支持

## 技术栈

### 后端
- **Web 框架**：FastAPI 0.128.0
- **深度学习**：PyTorch 2.8.0, torchvision 0.23.0
- **图像处理**：OpenCV 4.12.0, scikit-image 0.24.0
- **地理信息**：GDAL 3.12.1, rasterio 1.4.3, geopandas 1.0.1
- **数据处理**：numpy 2.0.2, pandas 2.3.3, scipy 1.13.1
- **数据库**：SQLAlchemy 2.0.46
- **系统监控**：psutil 6.0.0

### 前端
- **框架**：Vue 3
- **语言**：TypeScript
- **构建工具**：Vite
- **路由**：Vue Router
- **HTTP 客户端**：Axios
- **并行计算**：Web Worker

## 项目结构

```
深度学习模型/
├── backend/                 # 后端代码
│   ├── api/                # API 接口
│   │   ├── main.py         # FastAPI 主应用
│   │   ├── upload.py       # 文件上传接口
│   │   ├── detection.py    # 检测接口
│   │   ├── training.py     # 训练接口
│   │   └── ...
│   ├── services/           # 业务逻辑服务
│   │   ├── detection.py    # 检测服务
│   │   ├── training.py     # 训练服务
│   │   ├── parallel_processing.py  # 并行处理
│   │   └── ...
│   ├── config/             # 配置文件
│   └── utils/              # 工具函数
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── pages/          # 页面组件
│   │   ├── components/     # 通用组件
│   │   ├── services/       # API 服务
│   │   └── router/         # 路由配置
│   └── package.json
├── storage/                # 存储目录
│   ├── uploads/            # 上传文件
│   ├── training_samples/   # 训练样本
│   ├── detection_images/   # 检测图像
│   └── merged/             # 合并结果
├── docs/                   # 文档
├── tests/                  # 测试文件
└── venv/                   # Python 虚拟环境
```

## 快速开始

### 环境要求
- Python 3.9+
- Node.js 16+
- GDAL 库

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/Kevin-Wu200/My-CNN.git
cd 深度学习模型
```

2. **设置 Python 虚拟环境**
```bash
python setup_env.py
```

3. **安装前端依赖**
```bash
cd frontend
npm install
```

4. **启动服务**
```bash
./start.sh
```

### 访问地址
- 前端地址：http://localhost:5173
- 后端地址：http://localhost:8000
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 使用说明

### 1. 用户登录
使用手机号登录系统

### 2. 模型训练
1. 上传训练样本（支持批量上传）
2. 配置模型参数
3. 开始训练
4. 查看训练进度

### 3. 有监督检测
1. 上传待检测图像
2. 选择训练好的模型
3. 执行检测
4. 查看检测结果和修正标注

### 4. 无监督检测
1. 上传待检测图像
2. 配置检测参数
3. 执行检测
4. 查看检测结果

### 5. 任务管理
- 查看任务历史
- 监控任务进度
- 停止运行中的任务

## 测试

### 基础测试
```bash
python3 test_upload_implementation.py
```

### 高级测试
```bash
python3 test_advanced_scenarios.py
```

### 验证实现
```bash
python3 verify_implementation.py
```

## 文档

- [任务完成总结](docs/任务完成总结.md)
- [上传优化方案](docs/上传优化方案.md)
- [算法说明](docs/算法说明.tex)
- [验证清理机制](docs/验证清理机制.md)

## 核心组件说明

### 后端服务
- **detection.py**：病害木检测核心逻辑
- **training.py**：模型训练流程管理
- **parallel_processing.py**：并行任务处理
- **change_detection.py**：变化检测服务
- **image_chunking.py**：图像分块处理

### 前端页面
- **Login.vue**：用户登录
- **ModelTraining.vue**：模型训练
- **ImageUpload.vue**：图像上传
- **DetectionResult.vue**：检测结果展示
- **TaskProgress.vue**：任务进度监控

## 常见问题

### 端口占用
如果端口 8000 或 5173 被占用，启动脚本会自动清理旧进程。

### 内存不足
系统会自动监控内存使用，如果超过阈值会触发保护机制。

### 文件上传失败
检查网络连接，系统支持断点续传和智能重试。

## 贡献指南

欢迎提交 Issue 和 Pull Request。

## 许可证

本项目采用 MIT 许可证。

## 联系方式

如有问题，请通过1447954419@qq.com | 1447954419w@gmail.com联系。

---

**项目状态**：✅ 生产就绪

**最后更新**：2026-03-18