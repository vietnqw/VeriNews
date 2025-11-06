"""
SQLAlchemy Base Model

All database models should inherit from this Base class.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models
    
    All models inherit from this to use declarative base.
    """
    pass

