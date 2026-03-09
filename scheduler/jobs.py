"""
Scheduler module for daily paper push tasks.
"""
import asyncio
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from agents.base import AgentContext
from agents.publishers import OrchestratorAgent
from config.settings import settings


class DailyPushScheduler:
    """Scheduler for daily paper push tasks."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.orchestrator = OrchestratorAgent()

    async def run_daily_task(self):
        """Run the daily paper push task."""
        logger.info("=" * 50)
        logger.info(f"Starting daily paper push task at {datetime.now()}")
        logger.info("=" * 50)

        # Create execution context
        context = AgentContext(
            session_id=f"daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now().isoformat(),
            config={
                "daily_count": settings.DAILY_PAPER_COUNT,
                "selection_weights": settings.SELECTION_WEIGHTS,
            }
        )

        try:
            # Run orchestrator
            results = await self.orchestrator.run(context)

            logger.info("Daily task completed successfully")
            logger.info(f"Results: {results}")

            # TODO: Send notification to admins
            # TODO: Store execution results in database

            return results

        except Exception as e:
            logger.error(f"Daily task failed: {e}")
            raise

    def setup_schedule(self):
        """Set up the daily schedule."""
        # Schedule daily at configured time
        trigger = CronTrigger(
            hour=settings.SCHEDULE_HOUR,
            minute=settings.SCHEDULE_MINUTE
        )

        self.scheduler.add_job(
            self.run_daily_task,
            trigger=trigger,
            id="daily_paper_push",
            name="Daily Paper Push Task",
            replace_existing=True
        )

        logger.info(
            f"Scheduled daily task at {settings.SCHEDULE_HOUR}:"
            f"{settings.SCHEDULE_MINUTE:02d}"
        )

    def start(self):
        """Start the scheduler."""
        self.setup_schedule()
        self.scheduler.start()
        logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

    async def run_once(self):
        """Run the task once without scheduling."""
        return await self.run_daily_task()


async def main_async():
    """Main async entry point."""
    from storage.database import db

    # Initialize database
    await db.init()
    logger.info("Database initialized")

    # Create scheduler
    scheduler = DailyPushScheduler()

    # Run once for testing
    if settings.DEBUG:
        logger.info("Running in debug mode - executing once")
        results = await scheduler.run_once()
        logger.info(f"Results: {results}")
    else:
        # Start scheduler
        scheduler.start()

        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            scheduler.stop()

    # Close database
    await db.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Arxiv Daily Push System")
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run the task once and exit"
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Start the scheduler"
    )
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Only fetch papers, don't publish"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )

    args = parser.parse_args()

    if args.debug:
        import os
        os.environ["DEBUG"] = "true"

    # Run async main
    asyncio.run(main_async())


if __name__ == "__main__":
    main()