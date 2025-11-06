"""
Test script to verify configuration loading
"""

from app.config.settings import settings


def test_configuration():
    """Test that all configuration settings load correctly"""
    
    print("=" * 60)
    print("Testing VeriNews Configuration System")
    print("=" * 60)
    
    # Test environment variables
    print("\n📝 Environment Variables (.env):")
    print(f"  Project Name: {settings.PROJECT_NAME}")
    print(f"  Environment: {settings.ENVIRONMENT}")
    print(f"  API Prefix: {settings.API_PREFIX}")
    print(f"  Backend Host: {settings.BACKEND_HOST}")
    print(f"  Backend Port: {settings.BACKEND_PORT}")
    print(f"  CORS Origins: {settings.BACKEND_CORS_ORIGINS}")
    print(f"  Secret Key: {'*' * 20} (hidden)")
    
    print("\n🗄️  Database Configuration:")
    print(f"  Host: {settings.POSTGRES_HOST}")
    print(f"  Port: {settings.POSTGRES_PORT}")
    print(f"  Database: {settings.POSTGRES_DB}")
    print(f"  User: {settings.POSTGRES_USER}")
    print(f"  Password: {'*' * len(settings.POSTGRES_PASSWORD)} (hidden)")
    print(f"  Async URL: postgresql+asyncpg://.../{settings.POSTGRES_DB}")
    print(f"  Sync URL: postgresql+psycopg2://.../{settings.POSTGRES_DB}")
    
    print("\n📋 Logging Configuration:")
    print(f"  Level: {settings.LOG_LEVEL}")
    print(f"  File: {settings.LOG_FILE}")
    print(f"  Rotation: {settings.LOG_ROTATION}")
    print(f"  Retention: {settings.LOG_RETENTION}")
    print(f"  Compression: {settings.LOG_COMPRESSION}")
    
    print("\n🤖 AI/ML Configuration:")
    print(f"  OpenAI API Key: {'Set' if settings.OPENAI_API_KEY else 'Not Set'}")
    
    # Test YAML configuration
    print("\n📄 YAML Configuration (config.yaml):")
    print("\n  Scheduler Settings:")
    print(f"    Crawler Interval: {settings.scheduler.crawler_interval_minutes} minutes")
    print(f"    Article Expiration: {settings.scheduler.article_expiration_hours} hours")
    
    print("\n  Crawler Settings:")
    print(f"    Max Articles Per Feed: {settings.crawler.max_articles_per_feed}")
    print(f"    Max Content Length: {settings.crawler.max_content_length}")
    
    # Verify database URLs are constructed correctly
    print("\n🔗 Database URLs:")
    print(f"  Async URL format valid: {settings.POSTGRES_URL.startswith('postgresql+asyncpg://')}")
    print(f"  Sync URL format valid: {settings.POSTGRES_URL_SYNC.startswith('postgresql+psycopg2://')}")
    
    print("\n" + "=" * 60)
    print("✅ Configuration Test Completed Successfully!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_configuration()
    except Exception as e:
        print(f"\n❌ Configuration Test Failed!")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

