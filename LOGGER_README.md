# Async Logger - 비동기 로깅 시스템

멀티프로세스 기반 고성능 비동기 로깅 시스템

## 구조

```
service/
├── core/
│   └── asynclogger.py      # 핵심: 비동기 로그 기록 엔진
└── manager/
    └── logmanager.py       # 관리: 로거 인스턴스 등록/해제/관리
```

### Core (service/core/asynclogger.py)

**역할**: 실제 로그를 비동기적으로 기록하는 핵심 엔진

- `AsyncQueueHandler`: 로그 레코드를 큐에 전송하는 핸들러
- `_log_listener_process`: 별도 프로세스에서 실행되는 로그 리스너
- `AsyncLoggerCore`: 비동기 로그 기록 엔진 (멀티프로세스 기반)

**특징**:
- 별도 프로세스에서 로그 I/O 처리
- 메인 프로그램 성능에 영향 없음
- 호출 위치 정확하게 추적 (stacklevel=2)

### Manager (service/manager/logmanager.py)

**역할**: 로거 인스턴스 관리 및 전역 레지스트리

- `LoggerManager`: 로거 생성, 등록, 해제, 상태 조회
- `get_logger()`: 편의 함수 - 로거 생성/반환
- `register_logger()`: 로거 수동 등록
- `unregister_logger()`: 로거 해제
- `shutdown_all_loggers()`: 전체 로거 종료

**특징**:
- 스레드 안전 (threading.Lock)
- 싱글톤 패턴 기반 전역 로거 관리
- 자동 리소스 정리 (atexit)

## 사용법

### 1. 기본 사용

```python
from service.manager.logmanager import get_logger

# 로거 생성
log = get_logger("myapp")

# 로그 출력
log.info("애플리케이션 시작")
log.warning("경고 메시지")
log.error("에러 발생")

# 예외 로그
try:
    result = 1 / 0
except Exception:
    log.exception("예외 발생!")
```

### 2. 여러 로거 사용

```python
# 각 모듈별로 다른 로거 사용 가능
log1 = get_logger("module1", log_dir="logs/module1")
log2 = get_logger("module2", log_dir="logs/module2")

log1.info("모듈1 로그")
log2.info("모듈2 로그")
```

### 3. 로거 관리

```python
from service.manager.logmanager import LoggerManager

# 로거 존재 확인
if LoggerManager.has_logger("myapp"):
    print("로거가 이미 등록되어 있습니다")

# 모든 로거 상태 확인
stats = LoggerManager.get_logger_stats()
for name, stat in stats.items():
    print(f"{name}: {stat}")

# 특정 로거 해제
LoggerManager.unregister_logger("module2")

# 모든 로거 종료
LoggerManager.shutdown_all_loggers()
```

### 4. 수동 등록

```python
from service.core.asynclogger import AsyncLoggerCore
from service.manager.logmanager import register_logger

# 커스텀 설정으로 로거 생성
custom_log = AsyncLoggerCore(
    name="custom",
    log_dir="logs/custom",
    log_level=logging.DEBUG,
    console_output=True,
    file_output=True
)

# 레지스트리에 등록
register_logger("custom", custom_log)

# 사용
custom_log.debug("디버그 로그")
```

## 설정 옵션

```python
log = get_logger(
    name="app",                    # 로거 이름
    log_dir="logs",                # 로그 저장 디렉토리
    log_level=logging.INFO,        # 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    console_output=True,           # 콘솔 출력 여부
    file_output=True,              # 파일 출력 여부
    max_bytes=10*1024*1024,        # 로그 파일 최대 크기 (10MB)
    backup_count=5,                # 백업 파일 개수
    reuse=True                     # 기존 로거 재사용 여부
)
```

## 로그 파일 구조

```
logs/
├── myapp.log              # 모든 레벨의 로그
├── myapp_error.log        # ERROR 이상의 로그만
├── module1/
│   ├── module1.log
│   └── module1_error.log
└── module2/
    ├── module2.log
    └── module2_error.log
```

## 로그 포맷

### 콘솔
```
2025-12-23 22:31:54 [INFO    ] myapp - [main.py:42] 애플리케이션 시작
```

### 파일
```
2025-12-23 22:31:54 [INFO    ] myapp - [/path/to/main.py:42 in main()] - 애플리케이션 시작
```

## 성능

- **10,000개 로그**: 약 0.1초
- **처리량**: 약 100,000 logs/sec
- **메인 프로그램 블로킹**: 없음 (완전 비동기)

## 주의사항

1. **멀티프로세스 환경**: 각 프로세스는 독립적인 로거 프로세스를 생성
2. **리소스 정리**: 프로그램 종료 시 자동으로 정리되지만, 명시적 종료 권장
3. **로그 레벨**: 프로덕션에서는 INFO 이상 권장
4. **파일 크기**: max_bytes를 적절히 설정하여 디스크 공간 관리

## 예제

전체 예제는 다음 파일을 참고하세요:
- `tests/test_log_location2.py`: 로그 위치 추적 테스트
- `service/manager/logmanager.py`: 사용 예제 포함 (if __name__ == "__main__")
