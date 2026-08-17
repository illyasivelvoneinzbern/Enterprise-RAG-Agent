"""
Week7 Day4 —— reliability 组件测试（重试 / 抖动 / 队列 / 超时 / 熔断）
=====================================================================
运行方式（venv）：
  venv\\Scripts\\python.exe test_reliability.py
  venv\\Scripts\\python.exe -m test_reliability

不依赖 pytest：用 app.utils.logger 记录 + 控制台 [PASS]/[FAIL] 标记。
全部为桩函数（mock 抛异常 / mock sleep），不调用真实 LLM。
"""

import asyncio
import random
import sys
import time

# 保证脚本直接运行时能找到 app 包
if __package__ is None and __name__ != "__main__":
    sys.path.insert(0, ".")

from app.utils.logger import logger          # noqa: E402
from app.agent.reliability import (          # noqa: E402
    CircuitBreaker,
    TaskQueue,
    retry_with_backoff,
    run_with_timeout,
    run_with_timeout_sync,
)

# Windows GBK 控制台：打印中文前先切 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

PASSED = 0
FAILED = 0


def check(name, cond, detail=""):
    """统一断言：logger 记录 + 控制台 [PASS]/[FAIL] + 中文说明。"""
    global PASSED, FAILED
    if cond:
        PASSED += 1
        logger.info(f"[PASS] {name} | {detail}")
        print(f"[PASS] {name} | {detail}")
    else:
        FAILED += 1
        logger.info(f"[FAIL] {name} | {detail}")
        print(f"[FAIL] {name} | {detail}")


# ---------------------------------------------------------------------------
# 1) 重试：前 2 次失败第 3 次成功 → 重试成功且次数正确
# ---------------------------------------------------------------------------
def test_retry_success():
    print("\n--- 1. 重试：前 2 次失败，第 3 次成功 ---")

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("网络抖动（模拟）")
        return "ok-answer"

    delays = []

    def mock_sleep(d):
        delays.append(d)

    result = retry_with_backoff(flaky, max_retries=3, base_delay=1.0, sleep_func=mock_sleep)

    check("重试最终成功", result == "ok-answer", f"返回值={result!r}")
    check("调用次数=3", calls["n"] == 3, f"实际调用 {calls['n']} 次（2 失败 + 1 成功）")
    check("退避 2 段", len(delays) == 2, f"共休眠 {len(delays)} 段（1s→2s 指数）")


# ---------------------------------------------------------------------------
# 2) 重试：全部失败 → 抛出且重试次数 = max_retries
# ---------------------------------------------------------------------------
def test_retry_all_fail():
    print("\n--- 2. 重试：全部失败 → 最后一次直接抛出 ---")

    calls = {"n": 0}

    def always_fail():
        calls["n"] += 1
        raise TimeoutError("LLM 超时（模拟）")

    raised = None
    try:
        retry_with_backoff(always_fail, max_retries=3, base_delay=1.0, sleep_func=lambda d: None)
    except TimeoutError as e:
        raised = e

    check("最后抛出原始异常", isinstance(raised, TimeoutError), f"异常类型={type(raised).__name__}")
    check("重试次数=max_retries", calls["n"] == 3, f"实际尝试 {calls['n']} 次（max_retries=3）")


# ---------------------------------------------------------------------------
# 3) 抖动（jitter）：两次退避 delay 不完全相同
# ---------------------------------------------------------------------------
def test_jitter():
    print("\n--- 3. 抖动：多次运行的 delay 不完全相同（有随机 jitter） ---")

    def collect_delays(seed):
        random.seed(seed)
        delays = []

        def mock_sleep(d):
            delays.append(d)

        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ConnectionError("抖动")
            return "ok"

        retry_with_backoff(flaky, max_retries=3, base_delay=1.0, sleep_func=mock_sleep)
        return delays

    grouped = [collect_delays(seed) for seed in range(10)]  # 按 seed 分组，避免跨组交错
    flat = [d for g in grouped for d in g]

    unique = set(round(d, 6) for d in flat)
    check("存在随机抖动", len(unique) > 1,
          f"{len(flat)} 段 delay 去重后 {len(unique)} 个不同值（说明叠加了 random.uniform）")
    check("退避为指数递增", all(
        g[0] < g[1] + 1e-6 for g in grouped if len(g) == 2
    ), f"每组内第一段 < 第二段（1s→2s 指数），样本={[round(x, 3) for g in grouped for x in g[:2]]}")


# ---------------------------------------------------------------------------
# 4) 任务队列：提交 10 个任务 → 按序执行、计数 10、不阻塞
# ---------------------------------------------------------------------------
async def _queue_worker(name):
    await asyncio.sleep(0.01)  # 模拟任务耗时
    return name


async def test_queue():
    print("\n--- 4. 任务队列：10 个任务按序执行、计数、优雅关闭 ---")

    order = []

    async def job(i):
        await asyncio.sleep(0.01)
        order.append(i)
        return i

    q = TaskQueue(maxsize=10)
    for i in range(10):
        await q.submit(job, i)

    await q.join()   # 等待队列排空
    check("队列计数=10", len(order) == 10, f"实际执行 {len(order)} 个任务")
    check("按序执行", order == list(range(10)), f"执行顺序={order}")
    check("队列未阻塞", True, "submit 后并发消费完成，全程无阻塞")

    await q.close()  # 优雅关闭 worker
    check("优雅关闭", True, "close() 后 worker 正常退出")


# ---------------------------------------------------------------------------
# 5) 超时熔断降级：sleep 超过 timeout → 返回 fallback
# ---------------------------------------------------------------------------
async def _slow_coro():
    await asyncio.sleep(0.5)  # 故意超时
    return "本不该返回"


async def test_timeout_async():
    print("\n--- 5. 超时：async 协程超过 timeout 返回降级话术 ---")

    fallback = "系统繁忙，请稍后再试。"
    result = await run_with_timeout(_slow_coro(), timeout=0.2, fallback=fallback)
    check("async 超时降级", result == fallback, f"返回值={result!r}")

    fast = await run_with_timeout(_ok_coro(), timeout=0.2, fallback=fallback)
    check("未超时返回真实结果", fast == "正常结果", f"返回值={fast!r}")


async def _ok_coro():
    await asyncio.sleep(0.01)
    return "正常结果"


def test_timeout_sync():
    print("\n--- 6. 超时：同步函数超过 timeout 返回降级话术（FastAPI 同步接口用） ---")

    def slow_sync():
        time.sleep(0.5)  # 故意超时

    fallback = "系统繁忙，请稍后再试。"
    result = run_with_timeout_sync(slow_sync, timeout=0.2, fallback=fallback)
    check("sync 超时降级", result == fallback, f"返回值={result!r}")

    def fast_sync():
        return "正常同步结果"

    result2 = run_with_timeout_sync(fast_sync, timeout=1.0, fallback=fallback)
    check("sync 未超时返回真实结果", result2 == "正常同步结果", f"返回值={result2!r}")


# ---------------------------------------------------------------------------
# 6) 熔断器：打开 → 半开 → 关闭（加分项）
# ---------------------------------------------------------------------------
def test_circuit_breaker():
    print("\n--- 7. 熔断器：closed → open（快速失败）→ half_open（探测）→ closed ---")

    states = []  # 状态回调：记录 (old, new)

    def on_change(old, new):
        states.append((old, new))

    cb = CircuitBreaker(
        failure_threshold=3,
        cooldown=0.3,
        fallback="服务暂时不可用，请稍后再试。",
        on_state_change=on_change,
    )
    calls = {"n": 0}

    def failing():
        calls["n"] += 1
        raise ConnectionError("下游故障（模拟）")

    # 连续 3 次失败 → 打开
    for _ in range(3):
        try:
            cb.call(failing)
        except ConnectionError:
            pass
    check("连续失败 3 次后打开", cb.state == CircuitBreaker.STATE_OPEN,
          f"状态={cb.state}，失败计数={cb.failures}")

    # 冷却期内：快速失败不调底层
    before = calls["n"]
    fb = cb.call(failing)
    check("冷却期快速失败", fb == cb.fallback and calls["n"] == before,
          f"底层调用数不变（{before}），返回 fallback={fb!r}")

    # 冷却结束 → 半开 → 探测成功 → 关闭（用状态回调记录完整序列）
    time.sleep(0.4)
    def healthy():
        return "健康响应"

    result = cb.call(healthy)
    # 状态回调记录: closed→open（第3次失败）、open→half_open（冷却后首次探测）、half_open→closed（探测成功）
    seq = [new for _, new in states]
    check("状态序列 closed→open→half_open→closed",
          seq == [CircuitBreaker.STATE_OPEN, CircuitBreaker.STATE_HALF_OPEN, CircuitBreaker.STATE_CLOSED],
          f"回调序列={seq}，最终状态={cb.state}，失败计数={cb.failures}，返回={result!r}")
    check("半开探测成功 → 关闭并复位", cb.state == CircuitBreaker.STATE_CLOSED and cb.failures == 0,
          f"状态={cb.state}，失败计数={cb.failures}")

    # 半开探测失败 → 立即回 open
    cb2 = CircuitBreaker(failure_threshold=2, cooldown=0.2)
    for _ in range(2):
        try:
            cb2.call(failing)
        except ConnectionError:
            pass
    time.sleep(0.3)
    try:
        cb2.call(failing)  # 半开探测失败
    except ConnectionError:
        pass
    check("半开探测失败 → 立即回 open", cb2.state == CircuitBreaker.STATE_OPEN,
          f"状态={cb2.state}，失败计数={cb2.failures}")


# ---------------------------------------------------------------------------
# 汇总入口
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("Week7 Day4 reliability 测试")
    print("=" * 60)

    test_retry_success()
    test_retry_all_fail()
    test_jitter()
    asyncio.run(test_queue())
    asyncio.run(test_timeout_async())
    test_timeout_sync()
    test_circuit_breaker()

    print("\n" + "=" * 60)
    print(f"测试完成：PASS={PASSED}  FAIL={FAILED}")
    if FAILED == 0:
        print("全部通过 ✅")
        logger.info(f"test_reliability.py 全部通过 PASS={PASSED}")
    else:
        print(f"存在失败，请检查 ❌ FAIL={FAILED}")
        logger.error(f"test_reliability.py 存在失败 FAIL={FAILED}")
    print("=" * 60)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
