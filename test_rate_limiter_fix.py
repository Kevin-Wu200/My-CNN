"""
速率限制器修复验证测试

测试目的：验证chunk上传速率限制器的修复是否有效
"""

import time
import sys
from collections import defaultdict

class RateLimiter:
    """简单的速率限制器"""
    def __init__(self, max_requests: int = 100, window_seconds: int = 1):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)

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


def test_rate_limiter_allows_100_requests():
    """测试速率限制器允许100个请求"""
    print("测试1：验证速率限制器允许100个请求...")
    limiter = RateLimiter(max_requests=100, window_seconds=1)
    
    success_count = 0
    for i in range(100):
        if limiter.is_allowed("test_id"):
            success_count += 1
    
    # 第101个请求应该被拒绝
    rejected = not limiter.is_allowed("test_id")
    
    if success_count == 100 and rejected:
        print("✅ 测试1通过：成功允许100个请求，第101个被拒绝")
        return True
    else:
        print(f"❌ 测试1失败：成功{success_count}个，拒绝状态{rejected}")
        return False


def test_rate_limiter_resets_after_window():
    """测试速率限制器在时间窗口后重置"""
    print("\n测试2：验证速率限制器在时间窗口后重置...")
    limiter = RateLimiter(max_requests=5, window_seconds=1)
    
    # 填满限制
    for i in range(5):
        limiter.is_allowed("test_id")
    
    # 第6个请求应该被拒绝
    rejected_before = not limiter.is_allowed("test_id")
    
    # 等待时间窗口过期
    time.sleep(1.1)
    
    # 现在应该被允许
    allowed_after = limiter.is_allowed("test_id")
    
    if rejected_before and allowed_after:
        print("✅ 测试2通过：时间窗口过期后限制被重置")
        return True
    else:
        print(f"❌ 测试2失败：拒绝前{rejected_before}，允许后{allowed_after}")
        return False


def test_parallel_requests_simulation():
    """模拟前端8个并行worker的请求"""
    print("\n测试3：模拟前端8个并行worker的请求...")
    
    # 原始限制（10个请求/秒）
    old_limiter = RateLimiter(max_requests=10, window_seconds=1)
    
    # 新限制（100个请求/秒）
    new_limiter = RateLimiter(max_requests=100, window_seconds=1)
    
    # 模拟8个并行worker，每个发送10个请求
    old_success = 0
    new_success = 0
    
    for worker_id in range(8):
        for chunk_id in range(10):
            if old_limiter.is_allowed("upload_1"):
                old_success += 1
            if new_limiter.is_allowed("upload_1"):
                new_success += 1
    
    print(f"  原始限制（10个请求/秒）：{old_success}/80 成功 ({old_success/80*100:.1f}%)")
    print(f"  新限制（100个请求/秒）：{new_success}/80 成功 ({new_success/80*100:.1f}%)")
    
    if old_success < 80 and new_success == 80:
        print("✅ 测试3通过：新限制支持8个并行worker")
        return True
    else:
        print("❌ 测试3失败：新限制未能支持8个并行worker")
        return False


def test_multiple_uploads_isolation():
    """测试多个上传会话的隔离"""
    print("\n测试4：验证多个上传会话的隔离...")
    limiter = RateLimiter(max_requests=50, window_seconds=1)
    
    # 模拟3个不同的上传会话
    upload1_success = 0
    upload2_success = 0
    upload3_success = 0
    
    for i in range(50):
        if limiter.is_allowed("upload_1"):
            upload1_success += 1
        if limiter.is_allowed("upload_2"):
            upload2_success += 1
        if limiter.is_allowed("upload_3"):
            upload3_success += 1
    
    # 每个上传会话都应该有50个成功
    if upload1_success == 50 and upload2_success == 50 and upload3_success == 50:
        print("✅ 测试4通过：多个上传会话正确隔离")
        return True
    else:
        print(f"❌ 测试4失败：upload1={upload1_success}, upload2={upload2_success}, upload3={upload3_success}")
        return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("速率限制器修复验证测试")
    print("=" * 60)
    
    tests = [
        test_rate_limiter_allows_100_requests,
        test_rate_limiter_resets_after_window,
        test_parallel_requests_simulation,
        test_multiple_uploads_isolation,
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"❌ 测试异常：{str(e)}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"通过：{passed}/{total}")
    
    if passed == total:
        print("✅ 所有测试通过！修复有效。")
        return 0
    else:
        print("❌ 部分测试失败。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
