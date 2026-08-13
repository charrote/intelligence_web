"""Entry point for the scheduler process."""
from core.scheduler.scheduler import start_scheduler


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s"
    )
    start_scheduler()
