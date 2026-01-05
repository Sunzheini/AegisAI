"""
You can use the same docker container if you provide a different db name.
need sqlalchemy and psycopg2 packages

You can check status with pgadmin docker container:
http://localhost:5050/
user: admin@admin.com, pass: admin
-> fastapi_db -> Schema -> public -> Tables -> Users -> Right click -> View/Edit Data
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import psycopg2

from models.models import User

load_dotenv()

# ---------------------------------------------------------------------------------------------
# General Settings
# ---------------------------------------------------------------------------------------------
DB_NAME = os.getenv("DB_NAME", "fastapi_db")  # Target database name
DB_USER = os.getenv("DB_USER", "postgres_user")  # DB username
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")  # DB password
DB_HOST = os.getenv("DB_HOST", "localhost")  # DB host (localhost for local Docker)
DB_PORT = os.getenv("DB_PORT", "5432")  # DB port (default 5432)

# POSTGRES_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# ---------------------------------------------------------------------------------------------
# Function to create the database if it doesn't exist with psycopg2
# ---------------------------------------------------------------------------------------------
def create_database_if_not_exists() -> bool:
    """Create the database if it doesn't exist. Returns True if DB exists or was created,
    False on failure."""
    try:
        # Use psycopg2 to connect to the default 'postgres' database with autocommit
        conn = psycopg2.connect(
            dbname="postgres",
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        )
        conn.autocommit = True  # Enable autocommit to allow CREATE DATABASE

        with conn.cursor() as cur:
            # Check if the target database already exists
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
            exists = cur.fetchone()
            if not exists:
                # If not, create the database
                cur.execute(f"CREATE DATABASE {DB_NAME}")
                print(f"Database '{DB_NAME}' created successfully!")
            else:
                print(f"Database '{DB_NAME}' already exists.")
        conn.close()
    except Exception as e:
        print(
            f"Error: Could not connect to PostgreSQL or create database. Make sure PostgreSQL is "
            f"running."
        )
        print(f"Details: {e}")
        return False

    return True


# ---------------------------------------------------------------------------------------------
# SQLAlchemy for ORM and DB management
# ---------------------------------------------------------------------------------------------
BASE = (
    declarative_base()
)  # Base class for ORM models, other models will inherit from this!
DB_ENGINE = create_engine(
    DATABASE_URL, echo=True
)  # SQLAlchemy engine for ORM operations
DB_SESSION_LOCAL = sessionmaker(
    autocommit=False, autoflush=False, bind=DB_ENGINE
)  # Session factory for DB sessions


# ----------------------------------------------------------------------------------------------
# ORM Models
# ----------------------------------------------------------------------------------------------
# SQLAlchemy ORM model
class SQLAlchemyUser(BASE):
    """SQLAlchemy ORM model corresponding to the pydantic User model."""

    __tablename__ = (
        "users"  # Table name in the database, also this is used to know where to
    )
    # insert the new record
    id = Column(Integer, primary_key=True, autoincrement=True)  # Let DB handle IDs
    name = Column(String, nullable=False, unique=True)
    age = Column(Integer, nullable=False)
    city = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)


def pydantic_to_orm(user_model: User) -> SQLAlchemyUser:
    """Convert a Pydantic User model to a SQLAlchemyUser ORM model."""
    return SQLAlchemyUser(
        id=user_model.id,
        name=user_model.name,
        age=user_model.age,
        city=user_model.city,
        email=user_model.email,
        password_hash=user_model.password_hash,
    )


def orm_to_pydantic(orm_user: SQLAlchemyUser) -> User:
    """Convert a SQLAlchemyUser ORM model to a Pydantic User model."""
    return User(
        id=orm_user.id,
        name=orm_user.name,
        age=orm_user.age,
        city=orm_user.city,
        email=orm_user.email,
        password_hash=orm_user.password_hash,
    )


def create_tables_from_models() -> None:
    """Create all tables defined in SQLAlchemy models."""
    BASE.metadata.create_all(bind=DB_ENGINE)


# ----------------------------------------------------------------------------------------------
# @App Startup - Initialize DB and create tables if needed
# ----------------------------------------------------------------------------------------------
def initialize_database() -> None:
    """Initialize database and tables."""
    try:
        if create_database_if_not_exists():
            create_tables_from_models()
            print("Database setup complete!")
    except (psycopg2.Error, SQLAlchemyError) as e:
        print(f"Database initialization failed: {e}")
