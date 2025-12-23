#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
로그 위치 표시 테스트
"""

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from service.manager.logmanager import get_logger
import time


def function_a():
    """함수 A에서 로그"""
    log = get_logger("location_test")
    log.info("function_a에서 호출한 로그")
    log.warning("function_a에서 경고")


def function_b():
    """함수 B에서 로그"""
    log = get_logger("location_test")
    log.info("function_b에서 호출한 로그")
    log.error("function_b에서 에러")


class MyClass:
    """클래스 메서드에서 로그"""

    def method_1(self):
        log = get_logger("location_test")
        log.info("MyClass.method_1에서 호출")

    def method_2(self):
        log = get_logger("location_test")
        log.warning("MyClass.method_2에서 경고")


if __name__ == "__main__":
    print("=== 로그 위치 표시 테스트 ===\n")

    # 메인에서 직접 호출
    log = get_logger("location_test")
    log.info("메인에서 직접 호출한 로그")

    # 함수에서 호출
    function_a()
    function_b()

    # 클래스 메서드에서 호출
    obj = MyClass()
    obj.method_1()
    obj.method_2()

    # 예외 로그
    try:
        result = 10 / 0
    except Exception:
        log.exception("메인에서 예외 발생")

    # 로그 처리 대기
    time.sleep(1)

    print("\n각 로그의 [파일:라인] 정보를 확인하세요!")
    print("같은 파일(test_log_location2.py)의 다른 라인 번호가 표시되어야 합니다.")
