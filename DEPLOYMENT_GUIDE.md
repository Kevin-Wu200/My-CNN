# CPU 100% 问题修复 - 部署指南

## 部署前检查清单

### 1. 代码审查
- [ ] 审查所有修改的代码
- [ ] 确认没有引入新的 bug
- [ ] 验证代码风格一致性
- [ ] 检查是否有遗漏的错误处理

### 2. 本地测试
- [ ] 运行 `python backend/tests/verify_fixes.py`
- [ ] 运行 `python backend/tests/integration_test_graceful_shutdown.py`
- [ ] 运行 `python backend/tests/stress_test_parallel_processing.py`
- [ ] 手动测试 Ctrl+C 关闭功能
- [ ] 监控资源使用情况

### 3. 依赖检查
- [ ] 确认 `psutil==6.0.0` 已安装
- [ ] 确认所有其他依赖都已安装
- [ ] 检查是否有版本冲突

### 4. 配置检查
- [ ] 确认 `NUMERICAL_LIBRARY_THREADS = 2` 配置正确
- [ ] 确认日志目录存在且可写
- [ ] 确认存储目录存在且可写

---

## 部署步骤

### 步骤 1: 备份现有代码

```bash
# 创建备份分支
git branch backup-before-cpu-fix

# 或者创建备份目录
cp -r /Users/wuchenkai/深度学习模型 /Users/wuchenkai/深度学习模型.backup
```

### 步骤 2: 拉取最新代码

```bash
cd /Users/wuchenkai/深度学习模型

# 确保在 main 分支
git checkout main

# 拉取最新代码
git pull origin main

# 或者如果已经在本地，确认最新提交
git log --oneline -1
# 应该显示: f3db97b docs: 添加修复完成报告
```

### 步骤 3: 安装依赖

```bash
# 安装新增的 psutil 依赖
pip install psutil==6.0.0

# 或者重新安装所有依赖
pip install -r requirements.txt
```

### 步骤 4: 运行验证测试

```bash
# 验证所有修复
python backend/tests/verify_fixes.py

# 预期输出:
# ✓ 信号处理机制
# ✓ 数值库线程限制
# ✓ 进程池清理机制
# ✓ 资源监控功能
# ✓ 日志记录功能
# 总体: 5/5 项验证通过
```

### 步骤 5: 运行集成测试

```bash
# 集成测试（可能需要 5-10 分钟）
python backend/tests/integration_test_graceful_shutdown.py

# 预期输出:
# ✓ 正常完成时 CPU 使用率回落
# ✓ 进程数量稳定
# ✓ 无额外后台进程残留
# ✓ Ctrl+C 时所有 python 进程立即退出
```

### 步骤 6: 运行压力测试

```bash
# 压力测试（可能需要 10-20 分钟）
python backend/tests/stress_test_parallel_processing.py

# 预期输出:
# ✓ 大量分块处理成功
# ✓ 工作进程崩溃恢复成功
# ✓ 系统恢复能力正常
```

### 步骤 7: 启动服务

```bash
# 启动后端服务
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000

# 或者使用生产配置
python -m uvicorn backend.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --loop uvloop \
  --http httptools
```

### 步骤 8: 监控服务

```bash
# 在另一个终端监控资源使用
watch -n 1 'ps aux | grep python'

# 或者使用 top
top -p $(pgrep -f "uvicorn" | tr '\n' ',')

# 或者使用 htop
htop -p $(pgrep -f "uvicorn" | tr '\n' ',')
```

### 步骤 9: 测试功能

```bash
# 上传影像
curl -X POST "http://localhost:8000/unsupervised/upload-image" \
  -F "file=@/path/to/image.tif"

# 启动检测任务
curl -X POST "http://localhost:8000/unsupervised/detect?image_path=/path/to/image.tif&n_clusters=4&min_area=50"

# 查询任务状态
curl "http://localhost:8000/unsupervised/task-status/{task_id}"

# 监控 CPU 和内存使用
# 预期: CPU 占用 20-30%，内存占用 30-40%
```

### 步骤 10: 测试 Ctrl+C 关闭

```bash
# 在服务运行时按 Ctrl+C
# 预期输出:
# 收到信号 2，开始优雅关闭...
# 停止新任务创建
# 等待现有任务完成...
# 清理所有资源...
# 主进程安全退出

# 验证没有残留进程
ps aux | grep python
# 应该只显示 grep 命令本身，没有 python 进程
```

---

## 生产环境部署

### 使用 systemd 服务

创建 `/etc/systemd/system/disease-detection.service`:

```ini
[Unit]
Description=Unsupervised Disease Detection Service
After=network.target

[Service]
Type=simple
User=wuchenkai
WorkingDirectory=/Users/wuchenkai/深度学习模型
Environment="PATH=/Users/wuchenkai/venv/bin"
ExecStart=/Users/wuchenkai/venv/bin/python -m uvicorn backend.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --loop uvloop \
  --http httptools
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务:

```bash
sudo systemctl daemon-reload
sudo systemctl enable disease-detection
sudo systemctl start disease-detection
sudo systemctl status disease-detection
```

### 使用 Docker

创建 `Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动服务
CMD ["python", "-m", "uvicorn", "backend.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "4", "--loop", "uvloop", "--http", "httptools"]
```

构建和运行:

```bash
# 构建镜像
docker build -t disease-detection:latest .

# 运行容器
docker run -d \
  --name disease-detection \
  -p 8000:8000 \
  -v /path/to/storage:/app/storage \
  -v /path/to/logs:/app/logs \
  disease-detection:latest

# 查看日志
docker logs -f disease-detection

# 停止容器
docker stop disease-detection
```

### 使用 Nginx 反向代理

创建 `/etc/nginx/sites-available/disease-detection`:

```nginx
upstream disease_detection {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name disease-detection.example.com;

    client_max_body_size 100M;

    location / {
        proxy_pass http://disease_detection;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }

    location /docs {
        proxy_pass http://disease_detection/docs;
    }

    location /redoc {
        proxy_pass http://disease_detection/redoc;
    }
}
```

启用站点:

```bash
sudo ln -s /etc/nginx/sites-available/disease-detection /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 部署后验证

### 1. 检查服务状态

```bash
# 检查服务是否运行
systemctl status disease-detection

# 或者检查进程
ps aux | grep uvicorn

# 或者检查端口
netstat -tlnp | grep 8000
```

### 2. 检查日志

```bash
# 查看最新日志
tail -f /Users/wuchenkai/深度学习模型/logs/system_*.log

# 查看特定任务的日志
grep "\[task_id\]" /Users/wuchenkai/深度学习模型/logs/system_*.log

# 查看资源状态日志
grep "\[资源状态\]" /Users/wuchenkai/深度学习模型/logs/system_*.log
```

### 3. 监控性能指标

```bash
# 监控 CPU 和内存
watch -n 1 'ps aux | grep uvicorn | grep -v grep'

# 监控进程数
watch -n 1 'ps aux | grep python | wc -l'

# 监控网络连接
watch -n 1 'netstat -an | grep 8000'
```

### 4. 测试 API 端点

```bash
# 健康检查
curl http://localhost:8000/health

# 获取 API 文档
curl http://localhost:8000/docs

# 测试无监督检测
curl -X POST "http://localhost:8000/unsupervised/detect?image_path=/path/to/image.tif"
```

### 5. 性能基准测试

```bash
# 使用 Apache Bench 进行负载测试
ab -n 100 -c 10 http://localhost:8000/health

# 使用 wrk 进行性能测试
wrk -t4 -c100 -d30s http://localhost:8000/health
```

---

## 回滚计划

如果部署后出现问题，可以按以下步骤回滚：

### 快速回滚

```bash
# 切换到备份分支
git checkout backup-before-cpu-fix

# 重启服务
systemctl restart disease-detection

# 或者恢复备份目录
rm -rf /Users/wuchenkai/深度学习模型
cp -r /Users/wuchenkai/深度学习模型.backup /Users/wuchenkai/深度学习模型
```

### 部分回滚

如果只需要回滚某个特定的修改：

```bash
# 查看提交历史
git log --oneline

# 回滚到特定提交
git revert <commit_hash>

# 或者重置到特定提交
git reset --hard <commit_hash>
```

---

## 故障排查

### 问题 1: 服务无法启动

**症状**: `systemctl start disease-detection` 失败

**排查步骤**:
```bash
# 查看错误日志
journalctl -u disease-detection -n 50

# 手动启动服务查看错误
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000

# 检查依赖是否安装
pip list | grep psutil

# 检查配置文件
cat backend/config/settings.py | grep NUMERICAL_LIBRARY_THREADS
```

### 问题 2: CPU 占用仍然很高

**症状**: CPU 占用仍然 > 50%

**排查步骤**:
```bash
# 检查线程限制是否生效
python -c "import os; print(os.environ.get('OMP_NUM_THREADS'))"

# 检查 PyTorch 线程数
python -c "import torch; print(torch.get_num_threads())"

# 检查进程数和线程数
ps aux | grep python
ps -eLf | grep python | wc -l

# 查看详细的资源使用
top -p $(pgrep -f "uvicorn" | tr '\n' ',')
```

### 问题 3: Ctrl+C 无法关闭服务

**症状**: 按 Ctrl+C 后服务仍在运行

**排查步骤**:
```bash
# 查看信号处理日志
grep "收到信号" /Users/wuchenkai/深度学习模型/logs/system_*.log

# 检查是否有后台任务仍在运行
ps aux | grep python

# 强制杀死进程
pkill -9 -f uvicorn

# 检查是否有孤立进程
ps aux | grep python | grep -v grep
```

### 问题 4: 内存占用过高

**症状**: 内存占用 > 60%

**排查步骤**:
```bash
# 查看内存使用详情
ps aux | grep python | sort -k6 -rn

# 查看资源监控日志
grep "\[资源状态\]" /Users/wuchenkai/深度学习模型/logs/system_*.log | tail -20

# 检查是否有内存泄漏
python backend/tests/stress_test_parallel_processing.py
```

---

## 监控和告警

### 建议的监控指标

1. **CPU 占用率**: 应该在 20-30% 之间
2. **内存占用率**: 应该在 30-40% 之间
3. **进程数**: 应该稳定在 9-10 个
4. **线程数**: 应该在 16-20 个
5. **API 响应时间**: 应该 < 5 秒
6. **错误率**: 应该 < 1%

### 建议的告警规则

```yaml
# Prometheus 告警规则
groups:
  - name: disease_detection
    rules:
      - alert: HighCPUUsage
        expr: process_cpu_usage > 50
        for: 5m
        annotations:
          summary: "CPU 占用过高"

      - alert: HighMemoryUsage
        expr: process_memory_usage > 60
        for: 5m
        annotations:
          summary: "内存占用过高"

      - alert: ServiceDown
        expr: up{job="disease_detection"} == 0
        for: 1m
        annotations:
          summary: "服务已宕机"

      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01
        for: 5m
        annotations:
          summary: "错误率过高"
```

---

## 部署检查清单（最终）

- [ ] 代码审查完成
- [ ] 本地测试通过
- [ ] 依赖安装完成
- [ ] 配置检查完成
- [ ] 备份已创建
- [ ] 验证测试通过
- [ ] 集成测试通过
- [ ] 压力测试通过
- [ ] 服务启动成功
- [ ] API 端点可访问
- [ ] Ctrl+C 关闭正常
- [ ] 资源使用正常
- [ ] 日志记录正常
- [ ] 监控告警配置完成
- [ ] 回滚计划已准备

---

**部署完成后，请监控系统 24-48 小时，确保一切正常运行。**

如有任何问题，请参考故障排查部分或查看相关文档。
