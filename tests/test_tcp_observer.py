#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
서브프로세스 TCP 클라이언트 + 옵저버 패턴 테스트
"""

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
import json
from service.manager.socketmanager import (
    SubprocessTCPClient,
    SocketObserver,
    SocketDataListener,
    ParsedMessage,
)


# ==================== 리스너 구현 예제 ====================


class ConsoleLogger(SocketDataListener):
    """콘솔에 로그 출력하는 리스너"""

    def on_data_received(self, data: ParsedMessage):
        print(f"\n[ConsoleLogger] 데이터 수신:")
        print(f"  타입: {data.message_type}")
        print(f"  페이로드: {data.payload}")
        print(f"  크기: {len(data.raw_data)} bytes")
        print(f"  시간: {time.strftime('%H:%M:%S', time.localtime(data.timestamp))}")

    def on_connection_changed(self, connected: bool):
        status = "연결됨" if connected else "연결 끊김"
        print(f"\n[ConsoleLogger] 연결 상태: {status}")

    def on_error(self, error: Exception):
        print(f"\n[ConsoleLogger] 에러: {error}")


class DataCollector(SocketDataListener):
    """데이터를 수집하는 리스너"""

    def __init__(self):
        self.collected_data = []
        self.connection_count = 0

    def on_data_received(self, data: ParsedMessage):
        self.collected_data.append(data)
        print(f"[DataCollector] 수집된 데이터: {len(self.collected_data)}개")

    def on_connection_changed(self, connected: bool):
        if connected:
            self.connection_count += 1
        print(f"[DataCollector] 연결 횟수: {self.connection_count}")

    def on_error(self, error: Exception):
        print(f"[DataCollector] 에러 기록: {error}")

    def get_summary(self):
        return {
            "total_messages": len(self.collected_data),
            "connection_count": self.connection_count,
            "message_types": list(set(d.message_type for d in self.collected_data)),
        }


class JsonFilter(SocketDataListener):
    """JSON 타입 메시지만 처리하는 리스너"""

    def on_data_received(self, data: ParsedMessage):
        if data.message_type == "unknown" and isinstance(data.payload, dict):
            print(f"\n[JsonFilter] JSON 메시지 감지:")
            print(f"  {json.dumps(data.payload, indent=2, ensure_ascii=False)}")

    def on_connection_changed(self, connected: bool):
        pass  # 연결 상태는 무시

    def on_error(self, error: Exception):
        print(f"[JsonFilter] 에러: {error}")


# ==================== 테스트 함수 ====================


def test_tcp_client_with_observer():
    """TCP 클라이언트 + 옵저버 패턴 테스트"""
    print("=== 서브프로세스 TCP 클라이언트 + 옵저버 패턴 테스트 ===\n")

    # 옵저버 생성
    observer = SocketObserver()

    # 리스너 생성 및 등록
    console_logger = ConsoleLogger()
    data_collector = DataCollector()
    json_filter = JsonFilter()

    print("리스너 등록 중...")
    observer.attach(console_logger)
    observer.attach(data_collector)
    observer.attach(json_filter)
    print(f"등록된 리스너: {observer.listener_count()}개\n")

    # TCP 클라이언트 생성 (로컬 에코 서버 필요)
    client = SubprocessTCPClient(
        host="127.0.0.1",
        port=8888,
        observer=observer,
        auto_reconnect=True,
        reconnect_interval=3.0,
    )

    print("TCP 클라이언트 시작...")
    print("에코 서버가 필요합니다:")
    print("  터미널에서: nc -l 8888")
    print("  또는: python -m http.server 8888")
    print("\n종료: Ctrl+C\n")

    client.start()

    try:
        # 10초 동안 실행
        for i in range(10):
            time.sleep(1)
            stats = client.get_stats()
            print(
                f"\r[통계] 연결: {stats['connected']}, "
                f"수신: {stats['total_received']}개, "
                f"바이트: {stats['total_bytes']}",
                end="",
                flush=True,
            )

    except KeyboardInterrupt:
        print("\n\n사용자 중단")

    finally:
        # 리스너 제거 테스트
        print("\n\n리스너 제거 중...")
        observer.detach(json_filter)
        print(f"남은 리스너: {observer.listener_count()}개")

        # 데이터 수집 결과
        print(f"\n수집된 데이터 요약:")
        summary = data_collector.get_summary()
        for key, value in summary.items():
            print(f"  {key}: {value}")

        # 클라이언트 종료
        client.stop()

    print("\n테스트 종료")


def test_with_mock_server():
    """Mock 서버와 함께 테스트"""
    import socket as s
    import threading

    def mock_server():
        """간단한 Mock TCP 서버"""
        server = s.socket(s.AF_INET, s.SOCK_STREAM)
        server.setsockopt(s.SOL_SOCKET, s.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 8889))
        server.listen(1)
        print("[Mock서버] 포트 8889에서 대기 중...")

        try:
            conn, addr = server.accept()
            print(f"[Mock서버] 클라이언트 연결: {addr}")

            # JSON 메시지 전송
            for i in range(5):
                message = json.dumps(
                    {"type": "test", "id": i + 1, "data": f"테스트 메시지 #{i+1}"}
                )
                conn.sendall(message.encode() + b"\n")
                time.sleep(1)

            # 텍스트 메시지 전송
            conn.sendall(b"Plain text message\n")
            time.sleep(1)

            conn.close()
        except Exception as e:
            print(f"[Mock서버] 에러: {e}")
        finally:
            server.close()

    print("=== Mock 서버와 함께 테스트 ===\n")

    # Mock 서버 시작
    server_thread = threading.Thread(target=mock_server, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    # 옵저버 및 리스너
    observer = SocketObserver()
    observer.attach(ConsoleLogger())
    observer.attach(DataCollector())

    # 클라이언트 시작
    client = SubprocessTCPClient(
        host="127.0.0.1",
        port=8889,
        observer=observer,
        auto_reconnect=False,
    )
    client.start()

    # 10초 대기
    time.sleep(10)

    # 종료
    client.stop()
    print("\nMock 서버 테스트 종료")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "mock":
        test_with_mock_server()
    else:
        test_tcp_client_with_observer()
