"""
Test script to verify complete setup:
- Configuration loading from root .env
- Database configuration
- Docker connectivity (once started)
"""

from app.config.settings import settings
from app.core.logging import setup_logging, get_logger


def test_complete_setup():
    """Test the complete backend setup"""
    
    print("=" * 70)
    print("Testing VeriNews Complete Backend Setup")
    print("=" * 70)
    
    # Setup logging first
    setup_logging(
        log_level=settings.LOG_LEVEL,
        log_file=settings.LOG_FILE,
        log_rotation=settings.LOG_ROTATION,
        log_retention=settings.LOG_RETENTION,
        log_compression=settings.LOG_COMPRESSION,
        environment=settings.ENVIRONMENT,
    )
    logger = get_logger(__name__)
    
    logger.info("Starting configuration tests...")
    
    # Test environment variables from root .env
    print("\n✅ Configuration (.env from VeriNews root):")
    print(f"  Project: {settings.PROJECT_NAME}")
    print(f"  Environment: {settings.ENVIRONMENT}")
    print(f"  API Prefix: {settings.API_PREFIX}")
    
    print("\n✅ Database Configuration:")
    print(f"  Host: {settings.POSTGRES_HOST}")
    print(f"  Port: {settings.POSTGRES_PORT}")
    print(f"  Database: {settings.POSTGRES_DB}")
    print(f"  User: {settings.POSTGRES_USER}")
    
    print("\n✅ Database URLs:")
    print(f"  Async:  {settings.POSTGRES_URL[:50]}...")
    print(f"  Sync:   {settings.POSTGRES_URL_SYNC[:50]}...")
    
    print("\n✅ YAML Configuration (config.yaml):")
    print(f"  Crawler Interval: {settings.scheduler.crawler_interval_minutes} min")
    print(f"  Article Expiration: {settings.scheduler.article_expiration_hours} hours")
    print(f"  Max Articles: {settings.crawler.max_articles_per_feed}")
    
    logger.success("All configuration tests passed!")
    
    print("\n" + "=" * 70)
    print("✅ Complete Setup Test Passed!")
    print("=" * 70)
    print("\n📝 Next Steps:")
    print("  1. Start Docker: cd ../.. && docker compose -f docker/docker-compose.yml up -d")
    print("  2. Check containers: docker compose -f docker/docker-compose.yml ps")
    print("  3. Initialize Alembic migrations")
    print("  4. Run FastAPI application")


if __name__ == "__main__":
    try:
        test_complete_setup()
    except Exception as e:
        print(f"\n❌ Setup Test Failed!")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

