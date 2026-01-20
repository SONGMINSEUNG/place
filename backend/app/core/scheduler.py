"""
[DEPRECATED] 이 모듈은 더 이상 사용되지 않습니다.
대신 app.services.scheduler 모듈을 사용하세요.

스케줄러는 services/scheduler.py의 PlaceScheduler 클래스로 통합되었습니다.
이 파일은 하위 호환성을 위해 유지됩니다.
"""
import logging
from warnings import warn

logger = logging.getLogger(__name__)

# 호환성을 위한 re-export
from app.services.scheduler import (
    place_scheduler,
    get_training_status,
    training_status,
)

# deprecated 함수들
async def nightly_training_job():
    """
    [DEPRECATED] services/scheduler.py의 place_scheduler.nightly_training_job()을 사용하세요.
    """
    warn(
        "core/scheduler.py의 nightly_training_job()은 deprecated입니다. "
        "services/scheduler.py의 place_scheduler.nightly_training_job()을 사용하세요.",
        DeprecationWarning,
        stacklevel=2
    )
    await place_scheduler.nightly_training_job()


async def refresh_all_keywords_job():
    """
    [DEPRECATED] services/scheduler.py의 place_scheduler.refresh_saved_keywords()을 사용하세요.
    """
    warn(
        "core/scheduler.py의 refresh_all_keywords_job()은 deprecated입니다. "
        "services/scheduler.py의 place_scheduler.refresh_saved_keywords()을 사용하세요.",
        DeprecationWarning,
        stacklevel=2
    )
    await place_scheduler.refresh_saved_keywords()


def start_scheduler():
    """
    [DEPRECATED] services/scheduler.py의 place_scheduler.start()를 사용하세요.
    """
    warn(
        "core/scheduler.py의 start_scheduler()은 deprecated입니다. "
        "main.py에서 place_scheduler.start()가 자동으로 호출됩니다.",
        DeprecationWarning,
        stacklevel=2
    )
    place_scheduler.start()


def stop_scheduler():
    """
    [DEPRECATED] services/scheduler.py의 place_scheduler.stop()을 사용하세요.
    """
    warn(
        "core/scheduler.py의 stop_scheduler()은 deprecated입니다. "
        "main.py에서 place_scheduler.stop()이 자동으로 호출됩니다.",
        DeprecationWarning,
        stacklevel=2
    )
    place_scheduler.stop()


logger.info("[core/scheduler.py] DEPRECATED: 이 모듈은 services/scheduler.py로 통합되었습니다.")
