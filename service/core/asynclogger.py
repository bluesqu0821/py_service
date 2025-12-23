# -*- coding: utf-8 -*-
"""
Async Logger Core
비동기 로깅 핵심 기능 - 멀티프로세스 기반
"""

import logging
import logging.handlers
from multiprocessing import Queue, Process
from pathlib import Path
from typing import Optional
import atexit


# ==================== Queue Handler ====================


class AsyncQueueHandler(logging.Handler):
    """비동기 큐 핸들러 - 멀티프로세스 통신용"""

    def __init__(self, queue: Queue):
        super().__init__()
        self.queue = queue

    def emit(self, record: logging.LogRecord):
        """로그 레코드를 큐에 전송"""
        try:
            # 예외 정보 직렬화 (traceback 객체는 pickle 불가)
            if record.exc_info:
                record.exc_text = self.format(record)
                record.exc_info = None

            # 호출 위치 정보를 미리 문자열로 저장
            # (프로세스 간 전달 시 스택 프레임 정보가 손실되므로)
            if not hasattr(record, "_location_formatted"):
                record._location_formatted = True

            # 큐에 레코드 전송 (non-blocking)
            self.queue.put_nowait(record)
        except Exception:
            self.handleError(record)


# ==================== Log Listener Process ====================


def _log_listener_process(
    log_queue: Queue,
    logger_name: str,
    log_dir: Path,
    log_level: int,
    console_output: bool,
    file_output: bool,
    max_bytes: int,
    backup_count: int,
):
    """
    별도 프로세스에서 실행되는 로그 리스너
    큐에서 로그 레코드를 받아 실제 출력 처리
    """
    # 리스너 전용 로거 설정
    listener = logging.getLogger(f"{logger_name}_listener")
    listener.setLevel(log_level)
    listener.handlers.clear()

    # 포맷터 설정
    console_fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s - [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s - [%(pathname)s:%(lineno)d in %(funcName)s()] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 콘솔 핸들러
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(console_fmt)
        listener.addHandler(console_handler)

    # 파일 핸들러
    if file_output:
        log_dir.mkdir(parents=True, exist_ok=True)

        # 일반 로그
        log_file = log_dir / f"{logger_name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(file_fmt)
        listener.addHandler(file_handler)

        # 에러 로그
        error_log = log_dir / f"{logger_name}_error.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_fmt)
        listener.addHandler(error_handler)

    # 로그 레코드 수신 및 처리 루프
    while True:
        try:
            record = log_queue.get()

            # 종료 신호 확인
            if record is None:
                break

            # 로그 레코드 처리
            listener.handle(record)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[로그 리스너 에러] {e}")

    # 종료 전 핸들러 정리
    for handler in listener.handlers:
        handler.close()


# ==================== Async Logger Core ====================


class AsyncLoggerCore:
    """
    비동기 로거 핵심 - 실제 로그 기록 담당
    """

    def __init__(
        self,
        name: str = "app",
        log_dir: str = "logs",
        log_level: int = logging.INFO,
        console_output: bool = True,
        file_output: bool = True,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ):
        """
        비동기 로거 코어 초기화

        Args:
            name: 로거 이름
            log_dir: 로그 저장 디렉토리
            log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            console_output: 콘솔 출력 여부
            file_output: 파일 출력 여부
            max_bytes: 로그 파일 최대 크기
            backup_count: 백업 파일 개수
        """
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_level = log_level
        self.console_output = console_output
        self.file_output = file_output
        self.max_bytes = max_bytes
        self.backup_count = backup_count

        # 멀티프로세스 통신 큐
        self.log_queue: Queue = Queue(-1)

        # 리스너 프로세스
        self.listener_process: Optional[Process] = None
        self._start_listener()

        # 로거 설정
        self.logger = self._setup_logger()

        # 자동 종료 등록
        atexit.register(self.shutdown)

    def _start_listener(self):
        """로그 리스너 프로세스 시작"""
        self.listener_process = Process(
            target=_log_listener_process,
            args=(
                self.log_queue,
                self.name,
                self.log_dir,
                self.log_level,
                self.console_output,
                self.file_output,
                self.max_bytes,
                self.backup_count,
            ),
            daemon=True,
            name=f"LogListener-{self.name}",
        )
        self.listener_process.start()

    def _setup_logger(self) -> logging.Logger:
        """로거 설정 - 큐 핸들러만 사용"""
        logger = logging.getLogger(self.name)
        logger.setLevel(self.log_level)
        logger.handlers.clear()
        logger.propagate = False  # 부모 로거로 전파 방지

        # 큐 핸들러 추가
        queue_handler = AsyncQueueHandler(self.log_queue)
        queue_handler.setLevel(self.log_level)
        logger.addHandler(queue_handler)

        return logger

    # ==================== Logging Methods ====================

    def debug(self, msg: str, *args, **kwargs):
        """DEBUG 레벨 로그"""
        kwargs.setdefault("stacklevel", 2)
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """INFO 레벨 로그"""
        kwargs.setdefault("stacklevel", 2)
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """WARNING 레벨 로그"""
        kwargs.setdefault("stacklevel", 2)
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """ERROR 레벨 로그"""
        kwargs.setdefault("stacklevel", 2)
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        """CRITICAL 레벨 로그"""
        kwargs.setdefault("stacklevel", 2)
        self.logger.critical(msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        """예외 로그 (스택 트레이스 포함)"""
        kwargs.setdefault("stacklevel", 2)
        self.logger.exception(msg, *args, **kwargs)

    # ==================== Utility Methods ====================

    def set_level(self, level: int):
        """로그 레벨 변경"""
        self.log_level = level
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)

    def get_logger(self) -> logging.Logger:
        """내부 로거 객체 반환"""
        return self.logger

    def is_alive(self) -> bool:
        """리스너 프로세스 상태 확인"""
        return self.listener_process is not None and self.listener_process.is_alive()

    def shutdown(self):
        """로그 코어 종료"""
        if self.listener_process and self.listener_process.is_alive():
            # 종료 신호 전송
            try:
                self.log_queue.put(None, timeout=1)
            except:
                pass

            # 프로세스 종료 대기
            self.listener_process.join(timeout=3)

            # 강제 종료
            if self.listener_process.is_alive():
                self.listener_process.terminate()
                self.listener_process.join(timeout=1)

    def __del__(self):
        """소멸자 - 자동 정리"""
        self.shutdown()
