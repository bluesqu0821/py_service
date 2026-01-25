# -*- coding: utf-8 -*-
"""
SocketManager 사용 예제 및 테스트
Singleton 패턴을 사용한 소켓 관리
"""

import time
from service.manager.socketmanager import (
    SocketManager,
    get_socket_manager,
    create_socket_client,
    get_socket_client,
    attach_socket_listener,
    start_socket_client,
    stop_socket_client,
)
from service.core.socket import SocketDataListener, ParsedMessage


# ==================== 리스너 구현 ====================


class ConsoleListener(SocketDataListener):
    """콘솔 출력 리스너"""

    def on_data_received(self, data: ParsedMessage):
        print(f"\n[데이터 수신]")
        print(f"  타입: {data.message_type}")
        print(f"  페이로드: {data.payload}")
        print(f"  크기: {len(data.raw_data)} bytes")

    def on_connection_changed(self, connected: bool):
        status = "연결됨" if connected else "연결 끊김"
        print(f"\n[연결 상태] {status}")

    def on_error(self, error: Exception):
        print(f"\n[에러] {error}")


class DataCollectorListener(SocketDataListener):
    """데이터 수집 리스너"""

    def __init__(self, name: str):
        self.name = name
        self.data_list = []

    def on_data_received(self, data: ParsedMessage):
        self.data_list.append(
            {
                "type": data.message_type,
                "payload": data.payload,
                "timestamp": data.timestamp,
            }
        )
        print(f"[{self.name}] 수집: {len(self.data_list)}개")

    def on_connection_changed(self, connected: bool):
        status = "연결" if connected else "끊김"
        print(f"[{self.name}] 상태: {status}")

    def on_error(self, error: Exception):
        print(f"[{self.name}] 에러: {error}")


# ==================== 테스트 시나리오 ====================


def test_singleton_pattern():
    """Singleton 패턴 테스트"""
    print("\n" + "=" * 50)
    print("테스트 1: Singleton 패턴 확인")
    print("=" * 50)

    # 여러 방법으로 인스턴스 생성
    manager1 = SocketManager()
    manager2 = SocketManager.get_instance()
    manager3 = get_socket_manager()

    # 모두 같은 인스턴스인지 확인
    print(f"manager1 is manager2: {manager1 is manager2}")
    print(f"manager2 is manager3: {manager2 is manager3}")
    print(f"manager1 is manager3: {manager1 is manager3}")

    assert manager1 is manager2 is manager3, "Singleton 패턴 실패!"
    print("✓ Singleton 패턴 동작 확인")


def test_basic_usage():
    """기본 사용법 테스트"""
    print("\n" + "=" * 50)
    print("테스트 2: 기본 사용법")
    print("=" * 50)

    manager = get_socket_manager()

    # 클라이언트 생성
    client = manager.create_client(
        name="test_client",
        host="localhost",
        port=8888,
        auto_reconnect=True,
    )

    # 리스너 등록
    listener = ConsoleListener()
    manager.attach_listener("test_client", listener)

    # 시작
    manager.start_client("test_client")

    # 5초 대기
    print("\n5초 동안 실행...")
    time.sleep(5)

    # 통계 확인
    stats = manager.get_client_stats("test_client")
    print(f"\n[통계]")
    print(f"  연결: {stats['connected']}")
    print(f"  수신: {stats['total_received']}개")
    print(f"  바이트: {stats['total_bytes']}")

    # 중지 및 제거
    manager.stop_client("test_client")
    manager.remove_client("test_client")


def test_multiple_clients():
    """다중 클라이언트 관리 테스트"""
    print("\n" + "=" * 50)
    print("테스트 3: 다중 클라이언트 관리")
    print("=" * 50)

    manager = get_socket_manager()

    # 3개의 클라이언트 생성
    ports = [8888, 8889, 8890]
    for i, port in enumerate(ports):
        name = f"client_{i+1}"
        try:
            client = manager.create_client(
                name=name,
                host="localhost",
                port=port,
                auto_reconnect=True,
                reconnect_interval=3.0,
            )

            # 각 클라이언트에 리스너 등록
            listener = DataCollectorListener(name)
            manager.attach_listener(name, listener)

            # 시작
            manager.start_client(name)

        except Exception as e:
            print(f"{name} 생성 실패: {e}")

    # 클라이언트 목록 확인
    clients = manager.list_clients()
    print(f"\n등록된 클라이언트: {clients}")

    # 10초 동안 실행
    print("\n10초 동안 실행...")
    time.sleep(10)

    # 모든 클라이언트 통계 확인
    all_stats = manager.get_all_stats()
    print(f"\n[전체 통계]")
    for name, stats in all_stats.items():
        print(f"  {name}:")
        print(f"    - 연결: {stats['connected']}")
        print(f"    - 수신: {stats['total_received']}개")
        print(f"    - 바이트: {stats['total_bytes']}")

    # 모두 종료
    manager.shutdown_all()


def test_convenience_functions():
    """편의 함수 테스트"""
    print("\n" + "=" * 50)
    print("테스트 4: 편의 함수 사용")
    print("=" * 50)

    # 편의 함수로 간단하게 사용
    client = create_socket_client(
        name="simple_client",
        host="localhost",
        port=8888,
    )

    # 리스너 등록
    listener = ConsoleListener()
    attach_socket_listener("simple_client", listener)

    # 시작
    start_socket_client("simple_client")

    # 5초 대기
    time.sleep(5)

    # 조회
    client = get_socket_client("simple_client")
    if client:
        print(f"\n연결 상태: {client.is_connected()}")
        print(f"통계: {client.get_stats()}")

    # 중지
    stop_socket_client("simple_client")


def test_error_handling():
    """에러 처리 테스트"""
    print("\n" + "=" * 50)
    print("테스트 5: 에러 처리")
    print("=" * 50)

    manager = get_socket_manager()

    # 중복 생성 시도
    try:
        manager.create_client("duplicate", "localhost", 8888)
        manager.create_client("duplicate", "localhost", 8888)
    except ValueError as e:
        print(f"✓ 중복 생성 방지: {e}")

    # 존재하지 않는 클라이언트 조회
    client = manager.get_client("nonexistent")
    print(f"✓ 존재하지 않는 클라이언트: {client}")

    # 존재하지 않는 클라이언트 시작 시도
    try:
        manager.start_client("nonexistent")
    except KeyError as e:
        print(f"✓ 존재하지 않는 클라이언트 시작 방지: {e}")

    # 정리
    manager.remove_client("duplicate")


# ==================== 클래스 내부 사용 예제 ====================


class MyApplication:
    """애플리케이션 클래스에서 SocketManager 사용 예제"""

    def __init__(self):
        self.manager = get_socket_manager()
        self.client_name = "app_client"

    def setup(self):
        """소켓 설정"""
        # 클라이언트 생성
        self.manager.create_client(
            name=self.client_name,
            host="localhost",
            port=8888,
            auto_reconnect=True,
        )

        # 리스너 등록
        listener = AppListener(self)
        self.manager.attach_listener(self.client_name, listener)

    def start(self):
        """앱 시작"""
        self.manager.start_client(self.client_name)
        print("애플리케이션 시작")

    def stop(self):
        """앱 종료"""
        self.manager.stop_client(self.client_name)
        print("애플리케이션 종료")

    def process_data(self, data: ParsedMessage):
        """데이터 처리"""
        print(f"[앱] 데이터 처리: {data.message_type}")


class AppListener(SocketDataListener):
    """앱 전용 리스너"""

    def __init__(self, app: MyApplication):
        self.app = app

    def on_data_received(self, data: ParsedMessage):
        self.app.process_data(data)

    def on_connection_changed(self, connected: bool):
        status = "연결됨" if connected else "끊김"
        print(f"[앱] 소켓 {status}")

    def on_error(self, error: Exception):
        print(f"[앱] 에러: {error}")


def test_application_usage():
    """애플리케이션 클래스 사용 예제"""
    print("\n" + "=" * 50)
    print("테스트 6: 애플리케이션 클래스 사용")
    print("=" * 50)

    app = MyApplication()
    app.setup()
    app.start()

    time.sleep(5)

    app.stop()


# ==================== 실행 ====================


def main():
    """메인 함수"""
    print("\n" + "=" * 50)
    print("SocketManager 테스트 (Singleton 패턴)")
    print("=" * 50)

    # 테스트 1: Singleton 패턴
    test_singleton_pattern()

    # 테스트 2: 기본 사용법 (서버 필요)
    # test_basic_usage()

    # 테스트 3: 다중 클라이언트 (서버 필요)
    # test_multiple_clients()

    # 테스트 4: 편의 함수 (서버 필요)
    # test_convenience_functions()

    # 테스트 5: 에러 처리
    test_error_handling()

    # 테스트 6: 애플리케이션 클래스 (서버 필요)
    # test_application_usage()

    print("\n테스트 완료!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n프로그램 종료")
