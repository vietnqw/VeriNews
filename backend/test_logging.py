"""
Test script to verify logging configuration
"""

import logging
from app.core.logging import setup_logging, get_logger
from app.config.settings import settings


def test_logging():
    """Test that logging works correctly"""
    
    print("=" * 60)
    print("Testing VeriNews Logging System")
    print("=" * 60)
    
    # Setup logging
    setup_logging(
        log_level=settings.LOG_LEVEL,
        log_file=settings.LOG_FILE,
        log_rotation=settings.LOG_ROTATION,
        log_retention=settings.LOG_RETENTION,
        log_compression=settings.LOG_COMPRESSION,
        environment=settings.ENVIRONMENT,
    )
    
    # Get a logger instance
    logger = get_logger(__name__)
    
    print("\n📝 Testing different log levels:\n")
    
    # Test all log levels
    logger.trace("This is a TRACE message (very detailed)")
    logger.debug("This is a DEBUG message (development info)")
    logger.info("This is an INFO message (general information)")
    logger.success("This is a SUCCESS message (operation completed)")
    logger.warning("This is a WARNING message (something to watch)")
    logger.error("This is an ERROR message (something went wrong)")
    logger.critical("This is a CRITICAL message (severe problem)")
    
    # Test logging with context
    print("\n📋 Testing logging with context:\n")
    logger.info("Processing user request", user_id=123, action="login")
    logger.info("Database query executed", query="SELECT * FROM users", duration_ms=45)
    
    # Test standard Python logging interception
    print("\n🔄 Testing standard Python logging interception:\n")
    std_logger = logging.getLogger("test_standard")
    std_logger.info("This is from standard Python logging")
    std_logger.warning("This warning is intercepted by Loguru")
    
    # Test uvicorn logger interception
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.info("This is from uvicorn logger")
    
    print("\n" + "=" * 60)
    print("✅ Logging Test Completed Successfully!")
    print("=" * 60)
    print(f"\nEnvironment: {settings.ENVIRONMENT}")
    print(f"Log Level: {settings.LOG_LEVEL}")
    if settings.ENVIRONMENT == "production":
        print(f"Log File: {settings.LOG_FILE}")
    else:
        print("Log File: Not enabled (local environment)")


if __name__ == "__main__":
    try:
        test_logging()
    except Exception as e:
        print(f"\n❌ Logging Test Failed!")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

