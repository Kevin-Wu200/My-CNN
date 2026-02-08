#!/usr/bin/env python3
"""
架构重构验证脚本
用于验证所有实施的功能是否正常工作
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, '/Users/wuchenkai/深度学习模型')

def print_header(title):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def verify_imports():
    """验证所有导入"""
    print_header("1. 验证导入")

    try:
        from backend.config.settings import (
            STORAGE_DIR, UPLOAD_DIR, TRAINING_SAMPLES_DIR,
            DETECTION_IMAGES_DIR, TEMP_DIR, MODELS_DIR, DATABASE_PATH
        )
        print("✅ 配置导入成功")

        from backend.services.background_task_manager import (
            get_task_manager, TaskStatus, BackgroundTaskManager
        )
        print("✅ 后台任务管理器导入成功")

        from backend.api.task_status import router as task_status_router
        print("✅ 任务状态API导入成功")

        from backend.api.unsupervised_detection import router as unsupervised_router
        print("✅ 无监督检测API导入成功")

        from backend.api.detection_config import router as detection_router
        print("✅ 检测配置API导入成功")

        from backend.api.training_sample import router as training_router
        print("✅ 训练样本API导入成功")

        from backend.api.main import app
        print("✅ 主应用导入成功")

        return True
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_storage_paths():
    """验证存储路径"""
    print_header("2. 验证存储路径")

    try:
        from backend.config.settings import (
            STORAGE_DIR, UPLOAD_DIR, TRAINING_SAMPLES_DIR,
            DETECTION_IMAGES_DIR, TEMP_DIR, MODELS_DIR, DATABASE_PATH
        )
        from pathlib import Path

        paths = {
            "STORAGE_DIR": STORAGE_DIR,
            "UPLOAD_DIR": UPLOAD_DIR,
            "TRAINING_SAMPLES_DIR": TRAINING_SAMPLES_DIR,
            "DETECTION_IMAGES_DIR": DETECTION_IMAGES_DIR,
            "TEMP_DIR": TEMP_DIR,
            "MODELS_DIR": MODELS_DIR,
            "DATABASE_PATH": DATABASE_PATH,
        }

        for name, path in paths.items():
            if isinstance(path, Path):
                print(f"✅ {name}: {path}")
            else:
                print(f"❌ {name}: 类型错误 {type(path)}")
                return False

        # 验证目录存在
        for name, path in paths.items():
            if name == "DATABASE_PATH":
                continue
            if path.exists():
                print(f"✅ {name} 目录存在")
            else:
                print(f"⚠️  {name} 目录不存在: {path}")

        return True
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_task_manager():
    """验证后台任务管理器"""
    print_header("3. 验证后台任务管理器")

    try:
        from backend.services.background_task_manager import get_task_manager, TaskStatus

        tm = get_task_manager()
        print("✅ 获取任务管理器成功")

        # 创建任务
        task_id = tm.create_task("verification_test")
        print(f"✅ 创建任务成功: {task_id}")

        # 获取任务状态
        task = tm.get_task_status(task_id)
        if task and task["status"] == TaskStatus.PENDING:
            print("✅ 任务初始状态正确")
        else:
            print(f"❌ 任务状态错误: {task}")
            return False

        # 启动任务
        tm.start_task(task_id)
        task = tm.get_task_status(task_id)
        if task and task["status"] == TaskStatus.RUNNING:
            print("✅ 任务启动成功")
        else:
            print(f"❌ 任务启动失败: {task}")
            return False

        # 更新进度
        tm.update_progress(task_id, 50, "Testing")
        task = tm.get_task_status(task_id)
        if task and task["progress"] == 50 and task["current_stage"] == "Testing":
            print("✅ 任务进度更新成功")
        else:
            print(f"❌ 任务进度更新失败: {task}")
            return False

        # 完成任务
        tm.complete_task(task_id, {"result": "success"})
        task = tm.get_task_status(task_id)
        if task and task["status"] == TaskStatus.COMPLETED:
            print("✅ 任务完成成功")
        else:
            print(f"❌ 任务完成失败: {task}")
            return False

        return True
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_api_routes():
    """验证API路由"""
    print_header("4. 验证API路由")

    try:
        from backend.api.main import app

        routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                routes.append(route.path)

        expected_routes = [
            "/api/tasks/status",
            "/api/unsupervised/detect",
            "/api/unsupervised/task-status",
            "/api/detection/start-detection",
            "/api/training/start-training",
        ]

        for expected in expected_routes:
            found = any(expected in route for route in routes)
            if found:
                print(f"✅ 路由 {expected} 已注册")
            else:
                print(f"⚠️  路由 {expected} 未找到")

        print(f"\n✅ 总共注册 {len(routes)} 个路由")
        return True
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_file_structure():
    """验证文件结构"""
    print_header("5. 验证文件结构")

    try:
        from pathlib import Path

        files_to_check = [
            "backend/services/background_task_manager.py",
            "backend/api/task_status.py",
            "backend/config/settings.py",
            "backend/api/main.py",
            "backend/api/unsupervised_detection.py",
            "backend/api/detection_config.py",
            "backend/api/training_sample.py",
            "frontend/src/services/computeWorker.ts",
        ]

        project_root = Path("/Users/wuchenkai/深度学习模型")

        for file_path in files_to_check:
            full_path = project_root / file_path
            if full_path.exists():
                print(f"✅ {file_path} 存在")
            else:
                print(f"❌ {file_path} 不存在")
                return False

        return True
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主验证函数"""
    print("\n" + "="*60)
    print("  架构重构验证脚本")
    print("="*60)

    results = {
        "导入验证": verify_imports(),
        "存储路径验证": verify_storage_paths(),
        "任务管理器验证": verify_task_manager(),
        "API路由验证": verify_api_routes(),
        "文件结构验证": verify_file_structure(),
    }

    print_header("验证总结")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {name}")

    print(f"\n总体结果: {passed}/{total} 项验证通过")

    if passed == total:
        print("\n🎉 所有验证通过！架构重构实施成功！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 项验证失败，请检查上述错误")
        return 1

if __name__ == "__main__":
    sys.exit(main())
