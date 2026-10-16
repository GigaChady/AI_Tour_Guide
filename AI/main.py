import logging

from app_config import AppConfig
from bootstrap import build_redis_narration_worker


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config = AppConfig()
    if not config.ai_run_stream_worker:
        raise RuntimeError("Run the research prototype in experiments/tourguide_pipeline_prototype.ipynb")
    build_redis_narration_worker(config).run()


if __name__ == "__main__":
    main()
