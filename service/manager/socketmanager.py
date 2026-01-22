# -*- coding: utf-8 -*-
"""
Subprocess-based TCP Socket Manager with Observer Pattern
서브프로세스 기반 TCP 소켓 통신 + 옵저버 패턴
"""

import socket
import threading
import queue
from typing import Optional, Callable, Tuple, List, Any, Dict
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import time
import atexit
from multiprocessing import Process, Queue as MPQueue, Event as MPEvent
import json
import struct


@dataclass
class SocketMessage:
    """수신된 소켓 메시지"""

    data: bytes
    address: Tuple[str, int]
    timestamp: float


@dataclass
class ParsedMessage:
    """파싱된 메시지 데이터"""

    message_type: str
    payload: Any
    raw_data: bytes
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


# ==================== Observer Pattern ====================


class SocketDataListener(ABC):
    """소켓 데이터 리스너 인터페이스"""

    @abstractmethod
    def on_data_received(self, data: "ParsedMessage"):
        """데이터 수신 콜백"""
        pass

    @abstractmethod
    def on_connection_changed(self, connected: bool):
        """연결 상태 변경 콜백"""
        pass

    @abstractmethod
    def on_error(self, error: Exception):
        """에러 발생 콜백"""
        pass


class SocketObserver:
    """옵저버 패턴 구현 - 리스너 관리"""

    def __init__(self):
        self._listeners: List[SocketDataListener] = []
        self._lock = threading.Lock()

    def attach(self, listener: SocketDataListener):
        """리스너 등록"""
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)
                print(f"리스너 등록: {listener.__class__.__name__}")

    def detach(self, listener: SocketDataListener):
        """리스너 제거"""
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)
                print(f"리스너 제거: {listener.__class__.__name__}")

    def notify_data(self, data: "ParsedMessage"):
        """모든 리스너에게 데이터 전달"""
        with self._lock:
            listeners = self._listeners.copy()

        for listener in listeners:
            try:
                listener.on_data_received(data)
            except Exception as e:
                print(f"리스너 에러 ({listener.__class__.__name__}): {e}")
                try:
                    listener.on_error(e)
                except:
                    pass

    def notify_connection(self, connected: bool):
        """연결 상태 변경 알림"""
        with self._lock:
            listeners = self._listeners.copy()

        for listener in listeners:
            try:
                listener.on_connection_changed(connected)
            except Exception as e:
                print(f"연결 상태 알림 에러 ({listener.__class__.__name__}): {e}")

    def notify_error(self, error: Exception):
        """에러 알림"""
        with self._lock:
            listeners = self._listeners.copy()

        for listener in listeners:
            try:
                listener.on_error(error)
            except Exception as e:
                print(f"에러 알림 실패 ({listener.__class__.__name__}): {e}")

    def listener_count(self) -> int:
        """등록된 리스너 수"""
        with self._lock:
            return len(self._listeners)


# ==================== Data Parser ====================


class DataParser:
    """데이터 파서 - 프로토콜에 맞게 커스터마이징 가능"""

    @staticmethod
    def parse(data: bytes) -> "ParsedMessage":
        """
        데이터 파싱 (기본 구현 - JSON 기반)

        프로토콜 형식:
        [4 bytes: length][1 byte: type][N bytes: payload]
        """
        try:
            # 간단한 JSON 파싱 시도
            try:
                decoded = data.decode("utf-8")
                payload = json.loads(decoded)
                msg_type = payload.get("type", "unknown")

                return ParsedMessage(
                    message_type=msg_type,
                    payload=payload,
                    raw_data=data,
                    timestamp=time.time(),
                )
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

            # 바이너리 프로토콜 파싱
            if len(data) >= 5:
                length = struct.unpack(">I", data[:4])[0]
                msg_type = chr(data[4])
                payload_data = data[5 : 5 + length]

                # 페이로드 파싱 시도
                try:
                    payload = json.loads(payload_data.decode("utf-8"))
                except:
                    payload = payload_data

                return ParsedMessage(
                    message_type=msg_type,
                    payload=payload,
                    raw_data=data,
                    timestamp=time.time(),
                    metadata={"protocol": "binary", "length": length},
                )

            # 단순 텍스트
            return ParsedMessage(
                message_type="text",
                payload=data.decode("utf-8", errors="ignore"),
                raw_data=data,
                timestamp=time.time(),
            )

        except Exception as e:
            # 파싱 실패 시 raw 데이터로 처리
            return ParsedMessage(
                message_type="raw",
                payload=data,
                raw_data=data,
                timestamp=time.time(),
                metadata={"error": str(e)},
            )


# ==================== Subprocess TCP Client ====================


class SubprocessTCPClient:
    """서브프로세스 기반 TCP 클라이언트"""

    def __init__(
        self,
        host: str,
        port: int,
        observer: SocketObserver,
        auto_reconnect: bool = True,
        reconnect_interval: float = 5.0,
        buffer_size: int = 4096,
    ):
        """
        서브프로세스 TCP 클라이언트 초기화

        Args:
            host: 연결할 서버 주소
            port: 포트 번호
            observer: 옵저버 객체
            auto_reconnect: 자동 재연결 여부
            reconnect_interval: 재연결 시도 간격 (초)
            buffer_size: 수신 버퍼 크기
        """
        self.host = host
        self.port = port
        self.observer = observer
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnect_interval
        self.buffer_size = buffer_size

        # 프로세스 간 통신
        self.data_queue = MPQueue()
        self.command_queue = MPQueue()
        self.stop_event = MPEvent()  # 즉시 종료 신호

        # 서브프로세스
        self.process: Optional[Process] = None
        self.running = False

        # 파서
        self.parser = DataParser()

        # 통계
        self.stats = {
            "connected": False,
            "total_received": 0,
            "total_bytes": 0,
            "last_received": None,
        }

        # 데이터 처리 스레드
        self.processor_thread: Optional[threading.Thread] = None
        self.thread_stop_event = threading.Event()  # 스레드 종료 신호

        atexit.register(self.stop)

    def start(self):
        """클라이언트 시작"""
        if self.running:
            print("이미 실행 중입니다.")
            return

        self.running = True

        # stop event 초기화
        self.stop_event.clear()
        self.thread_stop_event.clear()

        # 서브프로세스 시작
        self.process = Process(
            target=self._tcp_loop,
            args=(
                self.host,
                self.port,
                self.data_queue,
                self.command_queue,
                self.stop_event,
                self.auto_reconnect,
                self.reconnect_interval,
                self.buffer_size,
            ),
            daemon=True,
        )
        self.process.start()
        print(f"TCP 클라이언트 프로세스 시작: {self.host}:{self.port}")

        # 데이터 처리 스레드 시작
        self.processor_thread = threading.Thread(
            target=self._process_data, daemon=True, name="DataProcessor"
        )
        self.processor_thread.start()
        print("데이터 처리 스레드 시작")

    @staticmethod
    def _tcp_loop(
        host,
        port,
        data_queue,
        command_queue,
        stop_event,
        auto_reconnect,
        reconnect_interval,
        buffer_size,
    ):
        """TCP 연결 및 수신 루프 (서브프로세스에서 실행)"""
        sock = None

        while not stop_event.is_set():
            try:
                # 연결 시도
                print(f"[프로세스] {host}:{port} 연결 시도...")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect((host, port))
                sock.settimeout(0.1)  # 짧은 타임아웃으로 빠른 종료

                # 연결 성공 알림
                data_queue.put(("connection", True))
                print(f"[프로세스] 연결 성공: {host}:{port}")

                # 수신 루프
                while not stop_event.is_set():
                    # 명령 확인
                    try:
                        cmd = command_queue.get_nowait()
                        if cmd == "stop":
                            break
                        elif cmd == "disconnect":
                            print("[프로세스] 연결 종료 명령 수신")
                            break
                    except:
                        pass

                    # 데이터 수신
                    try:
                        data = sock.recv(buffer_size)
                        if not data:
                            print("[프로세스] 서버 연결 종료")
                            break

                        # 데이터 전송
                        data_queue.put(("data", data))

                    except socket.timeout:
                        continue
                    except Exception as e:
                        print(f"[프로세스] 수신 에러: {e}")
                        break

            except Exception as e:
                print(f"[프로세스] 연결 에러: {e}")
                data_queue.put(("connection", False))
                data_queue.put(("error", str(e)))

            finally:
                # 소켓 정리
                if sock:
                    try:
                        sock.close()
                    except:
                        pass
                    sock = None

                # 연결 끊김 알림
                data_queue.put(("connection", False))

            # 재연결 시도
            if not stop_event.is_set() and auto_reconnect:
                print(f"[프로세스] {reconnect_interval}초 후 재연결 시도...")
                # 재연결 대기 중에도 stop_event 확인
                for _ in range(int(reconnect_interval * 10)):
                    if stop_event.is_set():
                        break
                    time.sleep(0.1)
            else:
                break

        print("[프로세스] TCP 루프 종료")

    def _process_data(self):
        """데이터 처리 루프 (별도 스레드)"""
        while not self.thread_stop_event.is_set():
            try:
                # 큐에서 데이터 가져오기 (짧은 타임아웃)
                msg_type, data = self.data_queue.get(timeout=0.1)

                if msg_type == "data":
                    # 데이터 파싱
                    parsed = self.parser.parse(data)

                    # 통계 업데이트
                    self.stats["total_received"] += 1
                    self.stats["total_bytes"] += len(data)
                    self.stats["last_received"] = time.time()

                    # 옵저버에게 알림
                    self.observer.notify_data(parsed)

                elif msg_type == "connection":
                    connected = data
                    self.stats["connected"] = connected
                    self.observer.notify_connection(connected)

                elif msg_type == "error":
                    error = Exception(data)
                    self.observer.notify_error(error)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"데이터 처리 에러: {e}")

        print("데이터 처리 스레드 종료")

    def send(self, data: bytes):
        """데이터 전송 (현재는 수신 전용, 필요시 구현 가능)"""
        # TODO: 송신 기능 구현
        pass

    def disconnect(self):
        """연결 종료 (재연결 중지)"""
        self.command_queue.put("disconnect")

    def stop(self):
        """클라이언트 중지"""
        if not self.running:
            return

        print("TCP 클라이언트 중지 중...")
        self.running = False

        # 즉시 종료 신호 전송
        self.stop_event.set()
        self.thread_stop_event.set()

        # 프로세스에 종료 명령 (추가 보장)
        try:
            self.command_queue.put_nowait("stop")
        except:
            pass

        # 스레드 먼저 종료 대기 (더 빠름)
        if self.processor_thread and self.processor_thread.is_alive():
            self.processor_thread.join(timeout=0.5)  # 0.5초로 단축

        # 프로세스 종료 대기
        if self.process and self.process.is_alive():
            self.process.join(timeout=0.5)  # 0.5초로 단축
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=0.2)  # terminate 후 짧은 대기

        print("TCP 클라이언트 중지됨")

    def get_stats(self) -> Dict:
        """통계 정보 반환"""
        return self.stats.copy()
