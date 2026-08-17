"""
Enterprise-RAG-Agent 可靠性组件（Week7 Day4 手写核心）
=====================================================

三大硬技能 + 加分项：
  ① retry_with_backoff     —— 指数退避 + 随机抖动（jitter）重试
  ② TaskQueue              —— asyncio.Queue 并发任务队列（多用户排队不互相阻塞）
  ③ run_with_timeout       —— 30s 超时熔断降级（不挂死调用方）
  ④ CircuitBreaker（加分） —— 熔断器：连续失败 N 次打开 → 冷却 → 半开探测 → 关闭

如何挂到现有 RAG Agent（Day 6 整合时用）：
  1) 重试 LLM 调用：
       chat_safe = lambda p: retry_with_backoff(lambda: chat(p), max_retries=3)
  2) 给 RAG 回答加超时降级（FastAPI 同步接口）：
       result = run_with_timeout_sync(agent.answer, timeout=30, fallback="系统繁忙，请稍后再试。")
  3) async 接口：
       result = await run_with_timeout(agent_executor.arun(messages), timeout=30, fallback="...")
  4) 多用户请求排队：
       q = TaskQueue(maxsize=10); await q.submit(agent.answer, query); await q.close()
  5) 熔断保护 LLM：
       cb = CircuitBreaker(failure_threshold=3, cooldown=5.0)
       result = cb.call(lambda: retry_with_backoff(lambda: chat(p)))
"""

import asyncio
import random
import sys
import threading
import time


# ---------------------------------------------------------------------------
# ① 指数退避重试（面试手撕高频题）
# ---------------------------------------------------------------------------
def retry_with_backoff(
    func,
    max_retries=3,
    base_delay=1.0,
    retryable_exceptions=None,
    sleep_func=None,
):
    """
    同步重试包装器：LLM/网络偶发失败自动重试，退避 1s→2s→4s + 随机抖动。

    面试点（jitter 的作用）：
      若所有请求失败后按相同退避时间同时重试，会在同一时刻再次同时打向服务，
      形成"惊群/雪崩"（thundering herd）。叠加随机抖动可以错开各请求的重试时刻，
      让重试流量均匀散开，提高恢复成功率、降低二次峰值。

    参数：
      func                  被包装的可调用对象（无参或部分应用后的 lambda）
      max_retries           最大尝试次数（含首次），默认 3
      base_delay            首次退避基数，默认 1.0，delay = base * 2**attempt
      retryable_exceptions  值得重试的异常类型（元组），默认 Exception（全重试）
      sleep_func            睡眠函数，默认 time.sleep；测试可注入 mock 收集 delay
    返回：
      func() 的成功返回值
    异常：
      最后一次尝试仍失败时直接抛出原始异常，交给上层降级（如 run_with_timeout）
    """
    retryable = retryable_exceptions or (Exception,)
    if isinstance(retryable, type):
        retryable = (retryable,)
    sleep = sleep_func or time.sleep

    for attempt in range(max_retries):
        try:
            return func()
        except retryable as e:
            if attempt == max_retries - 1:
                raise  # 最后一次失败：直接抛给上层降级
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            sleep(delay)


# ---------------------------------------------------------------------------
# ② 并发任务队列（多用户请求排队处理，不再互相阻塞）
# ---------------------------------------------------------------------------
class TaskQueue:
    """
    基于 asyncio.Queue(maxsize=10) 的并发任务队列。

    面试点：
      用 asyncio.Queue 做生产-消费者模型：多用户 submit() 任务排队，
      后台单 worker 逐个消费执行，天然串行不互相争抢；
      配合 task_done()/join() 可精确等待"队列排空"，实现优雅关闭。
    """

    _SENTINEL = object()  # 哨兵：通知 worker 退出

    def __init__(self, maxsize=10):
        self.queue = asyncio.Queue(maxsize=maxsize)
        self.maxsize = maxsize
        self._closed = False
        self.worker = asyncio.create_task(self._worker())

    async def submit(self, fn, *args):
        """生产：提交一个任务 (fn, args)，等待有空位则入队。"""
        if self._closed:
            raise RuntimeError("TaskQueue 已关闭，无法再提交任务")
        await self.queue.put((fn, args))

    async def _worker(self):
        """消费：从队列取出任务逐个执行，出错不崩 worker，记录后继续。"""
        while True:
            item = await self.queue.get()
            if item is self._SENTINEL:
                self.queue.task_done()
                break
            fn, args = item
            try:
                await fn(*args)
            except Exception as e:  # noqa: BLE001 —— 任务失败不能拖垮 worker
                print(f"[TaskQueue] 任务执行失败: {e}", file=sys.stderr)
            finally:
                self.queue.task_done()

    async def close(self):
        """优雅关闭：放哨兵让 worker 退出，并等待 worker 结束。"""
        if self._closed:
            return
        self._closed = True
        await self.queue.put(self._SENTINEL)
        try:
            await self.worker
        except asyncio.CancelledError:
            pass

    async def join(self):
        """等待队列中所有已提交任务执行完毕（与 asyncio.Queue.join 语义一致）。"""
        await self.queue.join()


# ---------------------------------------------------------------------------
# ③ 超时熔断降级（超过 timeout 秒返回降级话术，不挂死调用方）
# ---------------------------------------------------------------------------
async def run_with_timeout(coro, timeout=30, fallback="系统繁忙，请稍后再试。"):
    """
    async 超时熔断：await 一个协程，超过 timeout 秒返回降级话术。

    面试点：
      asyncio.wait_for 会在超时后取消内部协程并抛出 TimeoutError，
      这里捕获后返回 fallback，保证调用方绝不挂死（快速失败）。
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return fallback


def run_with_timeout_sync(func, timeout=30, fallback="系统繁忙，请稍后再试。"):
    """
    同步版超时熔断：在守护线程里执行同步 func，最多等待 timeout 秒。

    用途：
      FastAPI 同步接口里给 RAGAgent.answer() 这类同步调用加超时保护；
      超时后返回 fallback，后台线程继续跑（daemon）但不再阻塞调用方。
    """
    box = {"ok": False, "value": None, "error": None}

    def runner():
        try:
            box["value"] = func()
            box["ok"] = True
        except Exception as e:  # noqa: BLE001
            box["error"] = e

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join(timeout)

    if t.is_alive():
        return fallback  # 超时：不挂死，直接降级
    if box["ok"]:
        return box["value"]
    raise box["error"]  # 未超时但底层抛错：如实上抛


# ---------------------------------------------------------------------------
# ④ 熔断器（加分项：企业级可靠性标配）
# ---------------------------------------------------------------------------
class CircuitBreaker:
    """
    熔断器：连续失败 N 次后打开，直接快速失败不调底层；冷却后进入半开探测。

    状态机：
      closed   —— 正常。连续失败达到 failure_threshold → open
      open     —— 熔断。直接返回 fallback（不调底层），冷却时间到 → half_open
      half_open —— 半开。放一个探测请求：成功 → closed（复位）；失败 → open

    面试点：
      重试处理"偶发失败"，熔断处理"持续故障"。熔断打开期间不消耗真实调用，
      冷却后小流量探测，防止下游被持续打爆，比单纯重试更保护系统。
    """

    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold=3,
        cooldown=5.0,
        fallback="服务暂时不可用，请稍后再试。",
        on_state_change=None,
    ):
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown
        self.fallback = fallback
        self._on_state_change = on_state_change  # 可选：状态转换回调 (old, new)，便于观测/告警
        self._failures = 0
        self._state = self.STATE_CLOSED
        self._opened_at = 0.0
        self._last_error = None

    def _set_state(self, new_state):
        """切换状态，并触发 on_state_change 回调（仅真实变化时）。"""
        if new_state != self._state:
            old = self._state
            self._state = new_state
            if self._on_state_change is not None:
                self._on_state_change(old, new_state)

    @property
    def state(self):
        """当前状态：closed / open / half_open。"""
        return self._state

    @property
    def failures(self):
        """当前连续失败计数。"""
        return self._failures

    def call(self, func, *args, **kwargs):
        """执行 func，自动做熔断判断。返回 func 结果或 fallback。"""
        if self._state == self.STATE_OPEN:
            if time.time() - self._opened_at < self.cooldown:
                # 冷却未结束：快速失败，不调底层
                self._last_error = RuntimeError(
                    f"CircuitBreaker OPEN，快速失败（已连续失败 {self._failures} 次）"
                )
                return self.fallback
            # 冷却结束：进入半开，放一个探测请求
            self._set_state(self.STATE_HALF_OPEN)

        try:
            result = func(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            self._last_error = e
            self._failures += 1
            if self._state == self.STATE_HALF_OPEN:
                # 半开探测失败：立即回 open，重新计时冷却
                self._set_state(self.STATE_OPEN)
                self._opened_at = time.time()
            elif self._failures >= self.failure_threshold:
                self._set_state(self.STATE_OPEN)
                self._opened_at = time.time()
            raise e  # 底层失败：如实上抛，交给上层重试/降级
        else:
            # 成功：复位
            self._failures = 0
            self._set_state(self.STATE_CLOSED)
            return result


# ---------------------------------------------------------------------------
# 验证入口：venv\Scripts\python.exe -m app.agent.reliability
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Windows GBK 控制台打印中文前先切 UTF-8
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

    def first_line(doc):
        """取 docstring 首个非空行作为一句话描述。"""
        for line in (doc or "").splitlines():
            if line.strip():
                return line.strip()
        return "(无描述)"

    print("=" * 56)
    print("app/agent/reliability.py 组件加载验证")
    print("=" * 56)
    print(f"  retry_with_backoff   : {first_line(retry_with_backoff.__doc__)}")
    print(f"  TaskQueue            : {first_line(TaskQueue.__doc__)}")
    print(f"  run_with_timeout     : {first_line(run_with_timeout.__doc__)}")
    print(f"  run_with_timeout_sync: {first_line(run_with_timeout_sync.__doc__)}")
    print(f"  CircuitBreaker       : {first_line(CircuitBreaker.__doc__)}")
    print("-" * 56)
    print("说明：完整功能验证请运行 → venv\\Scripts\\python.exe test_reliability.py")
