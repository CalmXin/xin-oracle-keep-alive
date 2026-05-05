#!/usr/bin/env python3
# Oracle Cloud Keep-Alive Script (Python 3.11)
# - Type hints added
# - Uses loguru + httpx
# - Class-based logic, main() entry
# - No CLI args, direct run

import signal
import time
from concurrent.futures import ThreadPoolExecutor
from types import FrameType
from typing import List, Dict, Any

import httpx
import psutil
from loguru import logger

# ===== 配置区 =====
CONFIG: Dict[str, Any] = {
    "cpu_target": 0.15,  # 目标 CPU 使用率 (15%)
    "memory_mb": 80,  # 内存占用 (MB)
    "net_interval_sec": 300,  # 网络请求间隔 (秒)
    "ping_urls": [
        "https://www.google.com",
        "https://www.cloudflare.com",
        "https://httpbin.org/get"
    ]
}


# ==================


class OracleKeepAlive:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.cpu_target: float = config["cpu_target"]
        self.memory_bytes: int = config["memory_mb"] * 1024 * 1024
        self.net_interval: int = config["net_interval_sec"]
        self.ping_urls: List[str] = config["ping_urls"]
        self._stop: bool = False

    def set_stop(self) -> None:
        self._stop = True

    def _cpu_worker(self) -> None:
        logger.info(f"CPU worker started (target: {self.cpu_target * 100:.1f}%)")
        while not self._stop:
            start = time.time()
            total = sum(i * i for i in range(40000))  # 模拟计算
            elapsed = time.time() - start
            if elapsed > 0:
                sleep_time = max(0.01, (elapsed / self.cpu_target) - elapsed)
                time.sleep(sleep_time)
            else:
                time.sleep(0.1)

    def _memory_worker(self) -> None:
        logger.info(f"Memory worker started ({self.memory_bytes / (1024 ** 2):.1f} MB)")
        try:
            buffer: bytearray = bytearray(self.memory_bytes)
            while not self._stop:
                time.sleep(10)
            del buffer
        except MemoryError:
            logger.warning("Memory allocation failed. Skipping memory load.")

    def _network_worker(self) -> None:
        logger.info(f"Network worker started (interval: {self.net_interval}s)")
        client: httpx.Client = httpx.Client(timeout=8.0)
        try:
            while not self._stop:
                success: bool = False
                for url in self.ping_urls:
                    try:
                        resp: httpx.Response = client.get(url)
                        if resp.status_code == 200:
                            logger.debug(f"Ping success: {url}")
                            success = True
                            break
                    except Exception as e:
                        logger.debug(f"Ping failed for {url}: {e}")
                if not success:
                    logger.warning("All ping targets failed this round.")
                # 分段 sleep，支持中途退出
                for _ in range(self.net_interval):
                    if self._stop:
                        break
                    time.sleep(1)
        finally:
            client.close()

    def _monitor_worker(self) -> None:
        while not self._stop:
            try:
                cpu_pct: float = psutil.cpu_percent(interval=1)
                mem_avail: float = psutil.virtual_memory().available / (1024 ** 2)
                logger.info(f"Status - CPU: {cpu_pct:.1f}%, Available Memory: {mem_avail:.1f} MB")
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            time.sleep(60)

    def run(self) -> None:
        logger.info("Oracle Keep-Alive service starting...")
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(self._cpu_worker),
                executor.submit(self._memory_worker),
                executor.submit(self._network_worker),
                executor.submit(self._monitor_worker),
            ]
            try:
                while not self._stop:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.set_stop()

        logger.info("Service stopped.")


# 全局引用用于信号处理
_keepalive_instance: OracleKeepAlive | None = None


def signal_handler(sig: int, frame: FrameType | None) -> None:
    global _keepalive_instance
    if _keepalive_instance is not None:
        _keepalive_instance.set_stop()
    logger.info("Shutdown signal received.")


def main() -> None:
    global _keepalive_instance

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    _keepalive_instance = OracleKeepAlive(CONFIG)
    _keepalive_instance.run()


if __name__ == "__main__":
    main()
