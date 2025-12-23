# SubprocessTCPClient - 서브프로세스 기반 TCP 클라이언트 + 옵저버 패턴

## 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                    메인 프로세스                          │
│                                                          │
│  ┌────────────────┐                                     │
│  │ SubprocessTCP  │                                     │
│  │    Client      │                                     │
│  └───────┬────────┘                                     │
│          │                                              │
│          │ MPQueue                                      │
│          ▼                                              │
│  ┌────────────────┐      ┌──────────────────┐         │
│  │  Data Process  │      │  SocketObserver  │         │
│  │    Thread      ├─────►│                  │         │
│  │   (파싱)        │      │  - notify_data   │         │
│  └────────────────┘      │  - notify_conn   │         │
│                          │  - notify_error  │         │
│                          └────────┬─────────┘         │
│                                   │                    │
│                                   │ notify()           │
│                                   ▼                    │
│                          ┌─────────────────┐          │
│                          │   Listeners      │          │
│                          │                  │          │
│                          │  - ConsoleLogger │          │
│                          │  - DataCollector │          │
│                          │  - JsonFilter    │          │
│                          └──────────────────┘          │
└──────────────────────────────────────────────────────────┘
                                   ▲
                                   │
                           MPQueue │
                                   │
┌──────────────────────────────────┴───────────────────────┐
│                    서브프로세스                           │
│                                                          │
│  ┌────────────────┐                                     │
│  │  TCP Loop      │                                     │
│  │                │                                     │
│  │  - connect()   │                                     │
│  │  - recv()      │                                     │
│  │  - queue.put() │                                     │
│  └────────────────┘                                     │
│         ▲                                               │
│         │ Socket                                        │
│         ▼                                               │
│    ┌─────────┐                                          │
│    │  Server │                                          │
│    └─────────┘                                          │
└──────────────────────────────────────────────────────────┘
```

## 주요 컴포넌트

### 1. SubprocessTCPClient
- **서브프로세스**에서 TCP 연결 및 수신
- **자동 재연결** 기능
- **MPQueue**를 통한 프로세스 간 통신
- 데이터 파싱 및 옵저버 알림

### 2. SocketObserver
- **옵저버 패턴** 구현
- 여러 리스너 관리
- 스레드 안전한 알림 메커니즘

### 3. SocketDataListener (인터페이스)
- `on_data_received()` - 데이터 수신 콜백
- `on_connection_changed()` - 연결 상태 변경
- `on_error()` - 에러 처리

### 4. DataParser
- JSON 파싱
- 바이너리 프로토콜 파싱
- 텍스트 파싱
- 확장 가능한 구조

## 사용 예제

### 기본 사용법

```python
from analysis.socketmanager import (
    SubprocessTCPClient,
    SocketObserver,
    SocketDataListener,
    ParsedMessage,
)

# 1. 리스너 구현
class MyListener(SocketDataListener):
    def on_data_received(self, data: ParsedMessage):
        print(f"수신: {data.payload}")
    
    def on_connection_changed(self, connected: bool):
        print(f"연결: {connected}")
    
    def on_error(self, error: Exception):
        print(f"에러: {error}")

# 2. 옵저버 생성 및 리스너 등록
observer = SocketObserver()
observer.attach(MyListener())

# 3. TCP 클라이언트 시작
client = SubprocessTCPClient(
    host="127.0.0.1",
    port=8888,
    observer=observer,
    auto_reconnect=True
)
client.start()

# 4. 실행...
time.sleep(10)

# 5. 종료
client.stop()
```

### 여러 리스너 사용

```python
# 다양한 용도의 리스너들
class ConsoleLogger(SocketDataListener):
    """콘솔 출력"""
    def on_data_received(self, data):
        print(f"[LOG] {data.message_type}: {data.payload}")
    # ... 나머지 구현

class DataCollector(SocketDataListener):
    """데이터 수집"""
    def __init__(self):
        self.data = []
    
    def on_data_received(self, data):
        self.data.append(data)
    # ... 나머지 구현

class MetricsMonitor(SocketDataListener):
    """메트릭 모니터링"""
    def __init__(self):
        self.count = 0
        self.bytes = 0
    
    def on_data_received(self, data):
        self.count += 1
        self.bytes += len(data.raw_data)
    # ... 나머지 구현

# 모든 리스너 등록
observer = SocketObserver()
observer.attach(ConsoleLogger())
observer.attach(DataCollector())
observer.attach(MetricsMonitor())
```

### 선택적 데이터 처리

```python
class JsonOnlyListener(SocketDataListener):
    """JSON 데이터만 처리"""
    
    def on_data_received(self, data: ParsedMessage):
        # JSON 타입만 필터링
        if isinstance(data.payload, dict):
            self.process_json(data.payload)
    
    def process_json(self, json_data):
        # JSON 처리 로직
        pass
    
    def on_connection_changed(self, connected: bool):
        pass  # 무시
    
    def on_error(self, error: Exception):
        pass  # 무시
```

### 동적 리스너 관리

```python
observer = SocketObserver()

# 런타임에 리스너 추가
listener1 = ConsoleLogger()
observer.attach(listener1)

# ... 나중에 제거
observer.detach(listener1)

# 현재 리스너 수 확인
count = observer.listener_count()
```

## 데이터 형식

### ParsedMessage 구조

```python
@dataclass
class ParsedMessage:
    message_type: str      # "test", "unknown", "text", "raw", etc.
    payload: Any           # dict, str, bytes 등
    raw_data: bytes        # 원본 데이터
    timestamp: float       # 수신 시각
    metadata: Dict         # 추가 정보 (프로토콜, 길이 등)
```

### 지원하는 데이터 형식

1. **JSON** (자동 감지)
```json
{"type": "message", "data": "hello"}
```

2. **바이너리 프로토콜**
```
[4 bytes: length][1 byte: type][N bytes: payload]
```

3. **일반 텍스트**
```
Plain text message
```

## 설정 옵션

```python
client = SubprocessTCPClient(
    host="127.0.0.1",           # 서버 주소
    port=8888,                   # 포트
    observer=observer,           # 옵저버 객체
    auto_reconnect=True,         # 자동 재연결
    reconnect_interval=5.0,      # 재연결 간격(초)
    buffer_size=4096,            # 수신 버퍼
)
```

## 통계 정보

```python
stats = client.get_stats()
# {
#     'connected': True,
#     'total_received': 42,
#     'total_bytes': 1234,
#     'last_received': 1702876543.21
# }
```

## 커스텀 파서 구현

```python
from analysis.socketmanager import DataParser, ParsedMessage

class MyCustomParser(DataParser):
    @staticmethod
    def parse(data: bytes) -> ParsedMessage:
        # 커스텀 파싱 로직
        if data.startswith(b'CUSTOM:'):
            payload = data[7:].decode()
            return ParsedMessage(
                message_type='custom',
                payload=payload,
                raw_data=data,
                timestamp=time.time()
            )
        
        # 기본 파서 사용
        return DataParser.parse(data)

# 클라이언트에 적용
client.parser = MyCustomParser()
```

## 테스트

### Mock 서버와 테스트
```bash
python test_tcp_observer.py mock
```

### 실제 서버와 테스트
```bash
# 터미널 1: 에코 서버
nc -l 8888

# 터미널 2: 클라이언트
python test_tcp_observer.py
```

## 장점

✅ **프로세스 분리**: TCP I/O가 메인 프로그램을 블로킹하지 않음  
✅ **자동 재연결**: 네트워크 장애 시 자동 복구  
✅ **옵저버 패턴**: 여러 컴포넌트가 독립적으로 데이터 처리  
✅ **확장성**: 리스너를 쉽게 추가/제거  
✅ **타입 안전**: 데이터 클래스 사용  
✅ **에러 격리**: 한 리스너의 에러가 다른 리스너에 영향 없음  

## 주의사항

⚠️ **멀티프로세싱**: `if __name__ == "__main__":` 필수  
⚠️ **리스너 스레드 안전**: 리스너 내부에서 공유 자원 접근 시 락 필요  
⚠️ **메모리**: 큐 크기 제한 없으므로 처리 속도 < 수신 속도인 경우 주의  
