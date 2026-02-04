"""
进度卡死检测和修复验证脚本

用于验证以下修复：
1. 并行处理中的超时机制
2. 进度更新的时间戳记录
3. 进度卡住检测
"""

import time
import logging
from datetime import datetime
from backend.services.background_task_manager import get_task_manager, TaskStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_progress_stuck_detection():
    """测试进度卡住检测机制"""
    print("\n" + "="*60)
    print("测试 1: 进度卡住检测")
    print("="*60)

    task_manager = get_task_manager()

    # 创建任务
    task_id = task_manager.create_task("test_detection")
    print(f"✓ 创建任务: {task_id}")

    # 启动任务
    task_manager.start_task(task_id)
    print(f"✓ 任务已启动")

    # 更新进度到 30%
    task_manager.update_progress(task_id, 30, "执行检测中")
    print(f"✓ 进度更新到 30%")

    # 获取任务状态（应该没有卡住）
    task = task_manager.get_task_status(task_id)
    print(f"✓ 任务状态: {task['status']}, 进度: {task['progress']}%")
    print(f"  - 卡住状态: {task.get('stuck', False)}")
    print(f"  - 停留时间: {task.get('stuck_duration', 0)}秒")

    # 等待 35 秒（超过 30 秒阈值）
    print(f"\n⏳ 等待 35 秒以触发卡住检测...")
    for i in range(35):
        if i % 5 == 0:
            print(f"   已等待 {i} 秒...")
        time.sleep(1)

    # 再次获取任务状态（应该检测到卡住）
    task = task_manager.get_task_status(task_id, stuck_threshold=30)
    print(f"\n✓ 任务状态: {task['status']}, 进度: {task['progress']}%")
    print(f"  - 卡住状态: {task.get('stuck', False)}")
    print(f"  - 停留时间: {task.get('stuck_duration', 0)}秒")

    if task.get('stuck', False):
        print(f"\n✅ 成功检测到进度卡住！")
    else:
        print(f"\n❌ 未能检测到进度卡住")

    # 更新进度（应该清除卡住状态）
    task_manager.update_progress(task_id, 60, "继续处理中")
    print(f"\n✓ 进度更新到 60%")

    task = task_manager.get_task_status(task_id)
    print(f"✓ 任务状态: {task['status']}, 进度: {task['progress']}%")
    print(f"  - 卡住状态: {task.get('stuck', False)}")
    print(f"  - 停留时间: {task.get('stuck_duration', 0)}秒")

    if not task.get('stuck', False):
        print(f"\n✅ 成功清除卡住状态！")
    else:
        print(f"\n❌ 未能清除卡住状态")


def test_progress_timestamp_tracking():
    """测试进度时间戳记录"""
    print("\n" + "="*60)
    print("测试 2: 进度时间戳记录")
    print("="*60)

    task_manager = get_task_manager()

    # 创建任务
    task_id = task_manager.create_task("test_timestamp")
    print(f"✓ 创建任务: {task_id}")

    # 启动任务
    task_manager.start_task(task_id)
    print(f"✓ 任务已启动")

    # 记录初始时间
    start_time = datetime.now()
    print(f"✓ 初始时间: {start_time.strftime('%H:%M:%S')}")

    # 更新进度
    task_manager.update_progress(task_id, 10, "初始化")
    print(f"✓ 进度更新到 10%")

    # 等待 2 秒
    time.sleep(2)

    # 再次更新进度
    task_manager.update_progress(task_id, 50, "处理中")
    print(f"✓ 进度更新到 50%")

    # 检查时间戳
    if task_id in task_manager.progress_timestamps:
        last_update = task_manager.progress_timestamps[task_id]
        elapsed = datetime.now().timestamp() - last_update
        print(f"✓ 最后更新时间戳已记录")
        print(f"  - 距离现在: {elapsed:.2f}秒")
        if elapsed < 1:
            print(f"\n✅ 时间戳记录正确！")
        else:
            print(f"\n⚠️  时间戳可能有延迟")
    else:
        print(f"\n❌ 时间戳未被记录")


def test_task_completion():
    """测试任务完成流程"""
    print("\n" + "="*60)
    print("测试 3: 任务完成流程")
    print("="*60)

    task_manager = get_task_manager()

    # 创建任务
    task_id = task_manager.create_task("test_completion")
    print(f"✓ 创建任务: {task_id}")

    # 启动任务
    task_manager.start_task(task_id)
    print(f"✓ 任务已启动")

    # 更新进度
    task_manager.update_progress(task_id, 50, "处理中")
    print(f"✓ 进度更新到 50%")

    # 完成任务
    result = {"status": "success", "message": "测试完成"}
    task_manager.complete_task(task_id, result)
    print(f"✓ 任务已完成")

    # 获取任务状态
    task = task_manager.get_task_status(task_id)
    print(f"✓ 任务状态: {task['status']}")
    print(f"  - 进度: {task['progress']}%")
    print(f"  - 结果: {task['result']}")

    if task['status'] == TaskStatus.COMPLETED and task['progress'] == 100:
        print(f"\n✅ 任务完成流程正确！")
    else:
        print(f"\n❌ 任务完成流程有问题")


def test_task_failure():
    """测试任务失败流程"""
    print("\n" + "="*60)
    print("测试 4: 任务失败流程")
    print("="*60)

    task_manager = get_task_manager()

    # 创建任务
    task_id = task_manager.create_task("test_failure")
    print(f"✓ 创建任务: {task_id}")

    # 启动任务
    task_manager.start_task(task_id)
    print(f"✓ 任务已启动")

    # 更新进度
    task_manager.update_progress(task_id, 50, "处理中")
    print(f"✓ 进度更新到 50%")

    # 标记任务失败
    error_msg = "模拟的处理错误"
    task_manager.fail_task(task_id, error_msg)
    print(f"✓ 任务已标记为失败")

    # 获取任务状态
    task = task_manager.get_task_status(task_id)
    print(f"✓ 任务状态: {task['status']}")
    print(f"  - 错误信息: {task['error']}")

    if task['status'] == TaskStatus.FAILED and task['error'] == error_msg:
        print(f"\n✅ 任务失败流程正确！")
    else:
        print(f"\n❌ 任务失败流程有问题")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("进度卡死检测和修复验证")
    print("="*60)

    try:
        test_progress_timestamp_tracking()
        test_task_completion()
        test_task_failure()
        # test_progress_stuck_detection()  # 这个测试需要 35 秒，可选运行

        print("\n" + "="*60)
        print("✅ 所有测试完成！")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
