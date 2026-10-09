import json
import logging

from app_config import AppConfig
from bootstrap import build_narration_pipeline, build_redis_narration_worker
from narration.schemas import (
    NarrationDetailLevel,
    NarrationLanguage,
    NarrationPipelineRequest,
    NarrationSettings,
)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] (%(funcName)s): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run_demo_pipeline() -> None:
    pipeline = build_narration_pipeline()
    settings = NarrationSettings(
        latitude=41.889799,
        longitude=12.491015,
        detail_level=NarrationDetailLevel.DETAILED,
        search_radius=50,
        language=NarrationLanguage(language_name="Polish", language_tag="pl"),
        user_preferences="history architecture",
    )
    result = pipeline.run(
        NarrationPipelineRequest(session_id="local-demo", settings=settings)
    )
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


def main() -> None:
    configure_logging()
    config = AppConfig()
    if config.ai_run_stream_worker:
        build_redis_narration_worker(config).run()
    else:
        run_demo_pipeline()


if __name__ == "__main__":
    main()
