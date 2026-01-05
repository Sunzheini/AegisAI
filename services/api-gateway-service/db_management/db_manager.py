"""
Database manager for user data using PostgreSQL and SQLAlchemy.
"""

import os

from dotenv import load_dotenv

from models.models import User

load_dotenv()

# Conditional import for shared library usage ----------------------------------------------
USE_SHARED_LIB = os.getenv("USE_SHARED_LIB", False)
if USE_SHARED_LIB:
    from shared_lib.support.security import get_password_hash
    from shared_lib.interfaces.singleton_interface import SingletonInterface
else:
    from support.security import get_password_hash
    from interfaces.singleton_interface import SingletonInterface
# ------------------------------------------------------------------------------------------

from db_management.db_settings import (
    initialize_database,
    DB_SESSION_LOCAL,
    SQLAlchemyUser,
    pydantic_to_orm,
    orm_to_pydantic,
)


class DataBaseManager(SingletonInterface):
    """A database manager for user data using PostgreSQL and SQLAlchemy."""

    def _initialize(self):
        """Initialization logic that runs only once."""
        initialize_database()
        self._load_initial_data_if_empty()

    def _load_initial_data_if_empty(self):
        """Load initial user data if database is empty."""
        with DB_SESSION_LOCAL() as session:

            user_count = session.query(SQLAlchemyUser).count()
            if user_count == 0:
                self._load_initial_data(session)

    @staticmethod
    def _load_initial_data(session):
        """Load initial user data into the database."""
        users = [
            User(
                name="Alice",
                age=30,
                city="New York",
                email="alice@example.com",
                password_hash=get_password_hash("pass1"),
            ),
            User(
                name="Bob",
                age=25,
                city="Boston",
                email="bob@example.com",
                password_hash=get_password_hash("pass2"),
            ),
            User(
                name="Charlie",
                age=35,
                city="Chicago",
                email="charlie@example.com",
                password_hash=get_password_hash("pass3"),
            ),
            User(
                name="Bubka",
                age=43,
                city="Svishtov",
                email="bubka@example.com",
                password_hash=get_password_hash("pass4"),
            ),
        ]

        orm_users = [pydantic_to_orm(u) for u in users]  # convert to ORM models
        session.add_all(orm_users)
        session.commit()

    @staticmethod
    def get_all_users() -> list[User]:
        """Retrieve all users from the database."""
        with DB_SESSION_LOCAL() as session:
            orm_users = session.query(SQLAlchemyUser).all()
            return [orm_to_pydantic(u) for u in orm_users]

    @staticmethod
    def get_user_by_username(username: str) -> SQLAlchemyUser | None:
        """Retrieve a user by their username from the database."""
        with DB_SESSION_LOCAL() as session:
            return session.query(SQLAlchemyUser).filter_by(name=username).first()

    @staticmethod
    def get_user_by_id(user_id: int) -> User | None:
        """Retrieve a user by their ID from the database."""
        with DB_SESSION_LOCAL() as session:
            user = session.query(SQLAlchemyUser).filter_by(id=user_id).first()
            if user:
                return orm_to_pydantic(user)
            return None

    @staticmethod
    def create_user(user_data: User) -> User:
        """
        Create a new user record in the database's table.

        user = User(name="John", age=25, city="NYC", email="john@example.com",
        password_hash="hash123")
        created_user = create_user_record_in_a_existing_table(user)

        :param user_data: User data as a Pydantic model
        :return: The created SQLAlchemyUser ORM instance
        """
        # Convert Pydantic to ORM
        orm_user = pydantic_to_orm(user_data)

        with DB_SESSION_LOCAL() as session:
            session.add(orm_user)
            session.commit()
            session.refresh(orm_user)

        created_user = orm_to_pydantic(orm_user)  # Convert back to Pydantic
        return created_user

    @staticmethod
    def update_user(user_id: int, updated_data: dict) -> User | None:
        """Update an existing user record in the database."""
        with DB_SESSION_LOCAL() as session:
            user = session.query(SQLAlchemyUser).filter_by(id=user_id).first()
            if not user:
                return None

            for key, value in updated_data.items():
                if hasattr(user, key):
                    setattr(user, key, value)

            session.commit()
            session.refresh(user)
            return orm_to_pydantic(user)  # Convert back to Pydantic

    @staticmethod
    def delete_user_by_id(user_id: int) -> bool:
        """Delete a user by their ID from the database."""
        with DB_SESSION_LOCAL() as session:
            user = session.query(SQLAlchemyUser).filter_by(id=user_id).first()
            if user:
                session.delete(user)
                session.commit()
                return True
            return False

    @staticmethod
    def clear_users():
        """Delete all users from the database."""
        with DB_SESSION_LOCAL() as session:
            session.query(SQLAlchemyUser).delete()
            session.commit()
