import time
from multiprocessing import freeze_support

from service.manager.logmanager import get_logger

def worker():
    # 각 실행 컨텍스트에서 로거를 가져와 사용 (Windows spawn 환경에서도 안전)
    log = get_logger()
    log.info("워커 프로세스 시작")

def main():
    print("=== 로거 매니저 테스트 ===\n")

    log = get_logger()
    log.info("메인 프로세스 로그")
    
    log.error("에러 로그 테스트")
    
    
    worker()
    
    time.sleep(0.5)  # 로그 처리 대기
    
    log.warning("워닝 로그 테스트")
    log.critical("크리티컬 로그 테스트")
    

    # # 1. 로거 생성
    # print("1. 로거 생성...")
    # # log1 = get_logger("app1")
    # # log2 = get_logger("app2", log_dir="logs/app2")

    # log1.info("app1 로그")
    # log2.info("app2 로그")

    # # 2. 로거 상태 확인
    # print("\n2. 로거 상태:")
    # stats = LoggerManager.get_logger_stats()
    # for name, stat in stats.items():
    #     print(f"  {name}: {stat}")

    # # 3. 로거 재사용 테스트
    # print("\n3. 로거 재사용 테스트...")
    # log1_reused = get_logger("app1")  # 같은 인스턴스 반환
    # print(f"  같은 인스턴스: {log1 is log1_reused}")

    # # 4. 로거 해제
    # print("\n4. 로거 해제...")
    # unregister_logger("app2")
    # print(f"  app2 존재: {LoggerManager.has_logger('app2')}")

    # # 5. 수동 등록
    # print("\n5. 수동 로거 등록...")
    # from service.core.asynclogger import AsyncLoggerCore

    # custom_log = AsyncLoggerCore("custom", log_dir="logs/custom")
    # register_logger("custom", custom_log)
    # custom_log.info("커스텀 로거 테스트")

    
    
if __name__ == "__main__":
    freeze_support()  # Windows에서 multiprocessing 지원을 위해 필요
    
    main()
    
    # 로그 처리 대기
    time.sleep(1)

    print("\n✅ 테스트 완료!")