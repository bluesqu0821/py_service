# -*- coding: utf-8 -*-
"""
Socket Manager with Singleton Pattern
소켓 매니저 - Singleton 패턴으로 소켓 인스턴스 관리
"""

import threading
import atexit
from typing import Optional, Dict
from service.core.socket import (
    TCPClient,
    SocketObserver,
    SocketDataListener,
    ParsedMessage,
)


class SocketManager:
    """
    소켓 매니저 (Singleton)
    TCP 클라이언트 인스턴스를 중앙에서 관리
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton 패턴 구현"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """초기화 (한 번만 실행)"""
        if self._initialized:
            return

        # 소켓 인스턴스 저장소
        self._clients: Dict[str, TCPClient] = {}
        self._observers: Dict[str, SocketObserver] = {}
        self._clients_lock = threading.Lock()

        # 초기화 완료
        self._initialized = True

        # 프로그램 종료 시 자동 정리
        atexit.register(self.shutdown_all)

    @classmethod
    def get_instance(cls) -> "SocketManager":
        """싱글톤 인스턴스 반환"""
        if cls._instance is None:
            cls()
        return cls._instance

    def create_client(
        self,
        name: str,
        host: str,
        port: int,
        auto_reconnect: bool = True,
        reconnect_interval: float = 5.0,
        buffer_size: int = 4096,
    ) -> TCPClient:
        """
        TCP 클라이언트 생성

        Args:
            name: 클라이언트 식별 이름
            host: 서버 주소
            port: 포트 번호
            auto_reconnect: 자동 재연결 여부
            reconnect_interval: 재연결 간격
            buffer_size: 수신 버퍼 크기

        Returns:
            TCPClient 인스턴스

        Raises:
            ValueError: 동일한 이름의 클라이언트가 이미 존재하는 경우
        """
        with self._clients_lock:
            if name in self._clients:
                raise ValueError(f"클라이언트 '{name}'이(가) 이미 존재합니다.")

            # Observer 생성
            observer = SocketObserver()
            self._observers[name] = observer

            # TCP 클라이언트 생성
            client = TCPClient(
                host=host,
                port=port,
                observer=observer,
                auto_reconnect=auto_reconnect,
                reconnect_interval=reconnect_interval,
                buffer_size=buffer_size,
            )

            self._clients[name] = client
            print(f"소켓 클라이언트 생성: {name} ({host}:{port})")

            return client

    def get_client(self, name: str) -> Optional[TCPClient]:
        """
        클라이언트 조회

        Args:
            name: 클라이언트 이름

        Returns:
            TCPClient 인스턴스 또는 None
        """
        with self._clients_lock:
            return self._clients.get(name)

    def get_observer(self, name: str) -> Optional[SocketObserver]:
        """
        Observer 조회

        Args:
            name: 클라이언트 이름

        Returns:
            SocketObserver 인스턴스 또는 None
        """
        with self._clients_lock:
            return self._observers.get(name)

    def attach_listener(self, name: str, listener: SocketDataListener):
        """
        클라이언트에 리스너 등록

        Args:
            name: 클라이언트 이름
            listener: 리스너 인스턴스

        Raises:
            KeyError: 클라이언트가 존재하지 않는 경우
        """
        observer = self.get_observer(name)
        if observer is None:
            raise KeyError(f"클라이언트 '{name}'을(를) 찾을 수 없습니다.")

        observer.attach(listener)

    def detach_listener(self, name: str, listener: SocketDataListener):
        """
        클라이언트에서 리스너 제거

        Args:
            name: 클라이언트 이름
            listener: 리스너 인스턴스

        Raises:
            KeyError: 클라이언트가 존재하지 않는 경우
        """
        observer = self.get_observer(name)
        if observer is None:
            raise KeyError(f"클라이언트 '{name}'을(를) 찾을 수 없습니다.")

        observer.detach(listener)

    def start_client(self, name: str):
        """
        클라이언트 시작

        Args:
            name: 클라이언트 이름

        Raises:
            KeyError: 클라이언트가 존재하지 않는 경우
        """
        client = self.get_client(name)
        if client is None:
            raise KeyError(f"클라이언트 '{name}'을(를) 찾을 수 없습니다.")

        client.start()

    def stop_client(self, name: str):
        """
        클라이언트 중지

        Args:
            name: 클라이언트 이름

        Raises:
            KeyError: 클라이언트가 존재하지 않는 경우
        """
        client = self.get_client(name)
        if client is None:
            raise KeyError(f"클라이언트 '{name}'을(를) 찾을 수 없습니다.")

        client.stop()

    def remove_client(self, name: str):
        """
        클라이언트 제거 (중지 후 삭제)

        Args:
            name: 클라이언트 이름
        """
        with self._clients_lock:
            client = self._clients.get(name)
            if client:
                # 중지
                try:
                    client.stop()
                except:
                    pass

                # 삭제
                del self._clients[name]
                if name in self._observers:
                    del self._observers[name]

                print(f"소켓 클라이언트 제거: {name}")

    def get_client_stats(self, name: str) -> Optional[Dict]:
        """
        클라이언트 통계 조회

        Args:
            name: 클라이언트 이름

        Returns:
            통계 딕셔너리 또는 None
        """
        client = self.get_client(name)
        if client is None:
            return None

        return client.get_stats()

    def is_connected(self, name: str) -> bool:
        """
        클라이언트 연결 상태 확인

        Args:
            name: 클라이언트 이름

        Returns:
            연결 여부
        """
        client = self.get_client(name)
        if client is None:
            return False

        return client.is_connected()

    def list_clients(self) -> list[str]:
        """
        모든 클라이언트 이름 목록 반환

        Returns:
            클라이언트 이름 리스트
        """
        with self._clients_lock:
            return list(self._clients.keys())

    def get_all_stats(self) -> Dict[str, Dict]:
        """
        모든 클라이언트의 통계 반환

        Returns:
            {클라이언트명: 통계} 딕셔너리
        """
        with self._clients_lock:
            return {name: client.get_stats() for name, client in self._clients.items()}

    def shutdown_all(self):
        """모든 클라이언트 종료"""
        print("모든 소켓 클라이언트 종료 중...")

        with self._clients_lock:
            for name, client in list(self._clients.items()):
                try:
                    print(f"  - {name} 종료 중...")
                    client.stop()
                except Exception as e:
                    print(f"  - {name} 종료 실패: {e}")

            self._clients.clear()
            self._observers.clear()

        print("모든 소켓 클라이언트 종료 완료")


# ==================== 편의 함수 ====================


def get_socket_manager() -> SocketManager:
    """소켓 매니저 인스턴스 반환 (싱글톤)"""
    return SocketManager.get_instance()


def create_socket_client(
    name: str,
    host: str,
    port: int,
    auto_reconnect: bool = True,
    reconnect_interval: float = 5.0,
    buffer_size: int = 4096,
) -> TCPClient:
    """
    소켓 클라이언트 생성 (편의 함수)

    Args:
        name: 클라이언트 식별 이름
        host: 서버 주소
        port: 포트 번호
        auto_reconnect: 자동 재연결 여부
        reconnect_interval: 재연결 간격
        buffer_size: 수신 버퍼 크기

    Returns:
        TCPClient 인스턴스
    """
    manager = get_socket_manager()
    return manager.create_client(
        name=name,
        host=host,
        port=port,
        auto_reconnect=auto_reconnect,
        reconnect_interval=reconnect_interval,
        buffer_size=buffer_size,
    )


def get_socket_client(name: str) -> Optional[TCPClient]:
    """소켓 클라이언트 조회 (편의 함수)"""
    manager = get_socket_manager()
    return manager.get_client(name)


def attach_socket_listener(name: str, listener: SocketDataListener):
    """리스너 등록 (편의 함수)"""
    manager = get_socket_manager()
    manager.attach_listener(name, listener)


def start_socket_client(name: str):
    """소켓 클라이언트 시작 (편의 함수)"""
    manager = get_socket_manager()
    manager.start_client(name)


def stop_socket_client(name: str):
    """소켓 클라이언트 중지 (편의 함수)"""
    manager = get_socket_manager()
    manager.stop_client(name)


def remove_socket_client(name: str):
    """소켓 클라이언트 제거 (편의 함수)"""
    manager = get_socket_manager()
    manager.remove_client(name)
