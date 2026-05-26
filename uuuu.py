import subprocess
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

# ── 로깅 설정 ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("adb_monitor.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ── 데이터 모델 ────────────────────────────────────────────
@dataclass
class AdbDevice:
    serial: str
    mode: str        # "device" | "unauthorized" | "recovery" | "fastboot"
    model: str = ""
    detected_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def __str__(self):
        model_str = f" ({self.model})" if self.model else ""
        return f"{self.serial}{model_str} [{self.mode}]"


# ── ADB / Fastboot 쿼리 ────────────────────────────────────
def _run(cmd: list[str], timeout: int = 3) -> str:
    """명령어 실행 후 stdout 반환. 실패 시 빈 문자열."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def query_adb_devices() -> dict[str, AdbDevice]:
    """
    `adb devices -l` 파싱.
    반환: {serial: AdbDevice}
    """
    devices: dict[str, AdbDevice] = {}
    output = _run(["adb", "devices", "-l"])

    for line in output.splitlines():
        line = line.strip()
        # 헤더, 빈 줄 스킵
        if not line or line.startswith("List of"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        serial = parts[0]
        status = parts[1]  # device | unauthorized | offline | recovery ...

        # model 추출 (예: model:Pixel_6)
        model = ""
        for part in parts[2:]:
            if part.startswith("model:"):
                model = part.split(":", 1)[1].replace("_", " ")
                break

        devices[serial] = AdbDevice(serial=serial, mode=status, model=model)

    return devices


def query_fastboot_devices() -> dict[str, AdbDevice]:
    """
    `fastboot devices` 파싱.
    반환: {serial: AdbDevice}
    """
    devices: dict[str, AdbDevice] = {}
    output = _run(["fastboot", "devices"])

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) >= 1:
            serial = parts[0]
            devices[serial] = AdbDevice(serial=serial, mode="fastboot")

    return devices


def get_all_devices() -> dict[str, AdbDevice]:
    """ADB + Fastboot 장치를 합쳐서 반환. serial 중복 시 ADB 우선."""
    fastboot = query_fastboot_devices()
    adb = query_adb_devices()
    return {**fastboot, **adb}  # adb가 덮어쓰므로 ADB 우선


# ── 모니터 클래스 ──────────────────────────────────────────
class AdbMonitor:
    """
    ADB/Fastboot 장치 연결·해제를 폴링 방식으로 감지.

    사용 예:
        monitor = AdbMonitor(interval=1.0)
        monitor.on_connect = lambda d: print("연결:", d)
        monitor.on_disconnect = lambda d: print("해제:", d)
        monitor.start()
    """

    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.on_connect:    Callable[[AdbDevice], None] = self._default_connect
        self.on_disconnect: Callable[[AdbDevice], None] = self._default_disconnect
        self._prev: dict[str, AdbDevice] = {}
        self._running = False

    # ── 기본 콜백 ──────────────────────────────────────────
    @staticmethod
    def _default_connect(device: AdbDevice):
        icon = {
            "device":       "✅",
            "unauthorized": "⚠️ ",
            "recovery":     "🔧",
            "fastboot":     "⚡",
        }.get(device.mode, "🔌")
        log.info(f"{icon} 연결됨   : {device}")

    @staticmethod
    def _default_disconnect(device: AdbDevice):
        log.info(f"❌ 해제됨   : {device}")

    # ── 폴링 루프 ──────────────────────────────────────────
    def _poll(self):
        current = get_all_devices()

        # 신규 장치 (이전에 없던 serial)
        for serial, device in current.items():
            if serial not in self._prev:
                self.on_connect(device)

        # 해제된 장치 (현재 없는 serial)
        for serial, device in self._prev.items():
            if serial not in current:
                self.on_disconnect(device)

        self._prev = current

    def start(self):
        """블로킹 루프 시작 (Ctrl+C 로 종료)."""
        log.info(f"ADB/Fastboot 모니터 시작 (폴링 간격: {self.interval}s)")
        self._running = True

        # 초기 상태 스냅샷 (시작 시점 이미 연결된 장치를 이벤트로 올릴지 결정)
        self._prev = get_all_devices()
        if self._prev:
            log.info(f"시작 시 감지된 장치 {len(self._prev)}개:")
            for d in self._prev.values():
                log.info(f"  · {d}")
        else:
            log.info("현재 연결된 ADB/Fastboot 장치 없음.")

        try:
            while self._running:
                self._poll()
                time.sleep(self.interval)
        except KeyboardInterrupt:
            log.info("모니터 종료.")


# ── 커스텀 콜백 예시 ───────────────────────────────────────
def my_on_connect(device: AdbDevice):
    """연결 이벤트 처리 — 모드별 분기."""
    if device.mode == "fastboot":
        log.warning(f"⚡ Fastboot 장치 감지: {device.serial} — 부트로더 언락 주의!")
    elif device.mode == "unauthorized":
        log.warning(f"⚠️  인증 대기: {device.serial} — 기기에서 'USB 디버깅 허용'을 누르세요.")
    elif device.mode == "device":
        log.info(f"✅ ADB 준비 완료: {device}")
        # 예: 자동으로 logcat 시작, 스크린샷 저장 등
    elif device.mode == "recovery":
        log.info(f"🔧 Recovery 모드: {device}")


def my_on_disconnect(device: AdbDevice):
    log.info(f"❌ 장치 제거됨: {device.serial} (마지막 모드: {device.mode})")


# ── 진입점 ────────────────────────────────────────────────
if __name__ == "__main__":
    monitor = AdbMonitor(interval=1.0)
    monitor.on_connect    = my_on_connect
    monitor.on_disconnect = my_on_disconnect
    monitor.start()