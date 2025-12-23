# -*- coding: utf-8 -*-
"""
Log Manager - 로거 인스턴스 관리
핸들러 등록/해제 및 전역 로거 관리
"""

import logging
import threading
from typing import Dict, Optional
import atexit

from service.core.asynclogger import AsyncLoggerCore


# ==================== Global Logger Registry ====================

_global_loggers: Dict[str, AsyncLoggerCore] = {}
_registry_lock = threading.Lock()


# ==================== Logger Manager ====================


class LoggerManager:
    """
    로거 매니저 - 로거 인스턴스 생성 및 관리
    싱글톤 패턴으로 전역 로거 관리
    """

    @staticmethod
    def get_logger(
        name: str = "app",
        log_dir: str = "logs",
        log_level: int = logging.INFO,
        console_output: bool = True,
        file_output: bool = True,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        reuse: bool = True,
    ) -> AsyncLoggerCore:
        """
        로거 인스턴스 생성 또는 반환

        Args:
            name: 로거 이름
            log_dir: 로그 디렉토리
            log_level: 로그 레벨
            console_output: 콘솔 출력 여부
            file_output: 파일 출력 여부
            max_bytes: 파일 최대 크기
            backup_count: 백업 파일 수
            reuse: 기존 로거 재사용 여부 (False면 항상 새로 생성)

        Returns:
            AsyncLoggerCore: 비동기 로거 인스턴스
        """
        with _registry_lock:
            # 기존 로거 재사용
            if reuse and name in _global_loggers:
                return _global_loggers[name]

            # 새 로거 생성
            logger = AsyncLoggerCore(
                name=name,
                log_dir=log_dir,
                log_level=log_level,
                console_output=console_output,
                file_output=file_output,
                max_bytes=max_bytes,
                backup_count=backup_count,
            )

            _global_loggers[name] = logger
            return logger

    @staticmethod
    def register_logger(name: str, logger: AsyncLoggerCore):
        """
        로거 인스턴스 수동 등록

        Args:
            name: 로거 이름
            logger: 로거 인스턴스
        """
        with _registry_lock:
            if name in _global_loggers:
                # 기존 로거 종료
                _global_loggers[name].shutdown()

            _global_loggers[name] = logger

    @staticmethod
    def unregister_logger(name: str) -> bool:
        """
        로거 인스턴스 해제

        Args:
            name: 로거 이름

        Returns:
            bool: 성공 여부
        """
        with _registry_lock:
            if name in _global_loggers:
                logger = _global_loggers.pop(name)
                logger.shutdown()
                return True
            return False

    @staticmethod
    def get_registered_loggers() -> Dict[str, AsyncLoggerCore]:
        """
        등록된 모든 로거 반환

        Returns:
            Dict[str, AsyncLoggerCore]: 로거 이름과 인스턴스 매핑
        """
        with _registry_lock:
            return _global_loggers.copy()

    @staticmethod
    def has_logger(name: str) -> bool:
        """
        로거 존재 여부 확인

        Args:
            name: 로거 이름

        Returns:
            bool: 존재 여부
        """
        with _registry_lock:
            return name in _global_loggers

    @staticmethod
    def shutdown_logger(name: str) -> bool:
        """
        특정 로거 종료 (레지스트리에서는 유지)

        Args:
            name: 로거 이름

        Returns:
            bool: 성공 여부
        """
        with _registry_lock:
            if name in _global_loggers:
                _global_loggers[name].shutdown()
                return True
            return False

    @staticmethod
    def shutdown_all_loggers():
        """모든 로거 종료 및 해제"""
        with _registry_lock:
            for logger in _global_loggers.values():
                logger.shutdown()
            _global_loggers.clear()

    @staticmethod
    def get_logger_stats() -> Dict[str, Dict]:
        """
        모든 로거의 상태 정보 반환

        Returns:
            Dict[str, Dict]: 로거별 상태 정보
        """
        with _registry_lock:
            stats = {}
            for name, logger in _global_loggers.items():
                stats[name] = {
                    "name": logger.name,
                    "log_dir": str(logger.log_dir),
                    "log_level": logging.getLevelName(logger.log_level),
                    "console_output": logger.console_output,
                    "file_output": logger.file_output,
                    "is_alive": logger.is_alive(),
                }
            return stats


# ==================== Convenience Functions ====================


def get_logger(
    name: str = "app",
    log_dir: str = "logs",
    log_level: int = logging.INFO,
    console_output: bool = True,
    file_output: bool = True,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    reuse: bool = True,
) -> AsyncLoggerCore:
    """
    편의 함수: 로거 인스턴스 생성 또는 반환
    LoggerManager.get_logger()의 래퍼
    """
    return LoggerManager.get_logger(
        name=name,
        log_dir=log_dir,
        log_level=log_level,
        console_output=console_output,
        file_output=file_output,
        max_bytes=max_bytes,
        backup_count=backup_count,
        reuse=reuse,
    )


def register_logger(name: str, logger: AsyncLoggerCore):
    """편의 함수: 로거 등록"""
    LoggerManager.register_logger(name, logger)


def unregister_logger(name: str) -> bool:
    """편의 함수: 로거 해제"""
    return LoggerManager.unregister_logger(name)


def shutdown_all_loggers():
    """편의 함수: 모든 로거 종료"""
    LoggerManager.shutdown_all_loggers()


# 프로그램 종료 시 자동 정리
atexit.register(shutdown_all_loggers)


# ==================== Usage Example ====================

if __name__ == "__main__":
    import time

    print("=== 로거 매니저 테스트 ===\n")

    # 1. 로거 생성
    print("1. 로거 생성...")
    log1 = get_logger("app1")
    log2 = get_logger("app2", log_dir="logs/app2")

    log1.info("app1 로그")
    log2.info("app2 로그")

    # 2. 로거 상태 확인
    print("\n2. 로거 상태:")
    stats = LoggerManager.get_logger_stats()
    for name, stat in stats.items():
        print(f"  {name}: {stat}")

    # 3. 로거 재사용 테스트
    print("\n3. 로거 재사용 테스트...")
    log1_reused = get_logger("app1")  # 같은 인스턴스 반환
    print(f"  같은 인스턴스: {log1 is log1_reused}")

    # 4. 로거 해제
    print("\n4. 로거 해제...")
    unregister_logger("app2")
    print(f"  app2 존재: {LoggerManager.has_logger('app2')}")

    # 5. 수동 등록
    print("\n5. 수동 로거 등록...")
    from service.core.asynclogger import AsyncLoggerCore

    custom_log = AsyncLoggerCore("custom", log_dir="logs/custom")
    register_logger("custom", custom_log)
    custom_log.info("커스텀 로거 테스트")

    # 로그 처리 대기
    time.sleep(1)

    print("\n✅ 테스트 완료!")
