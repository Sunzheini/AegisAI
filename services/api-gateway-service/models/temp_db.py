from models.models import User
from routers.security import get_password_hash


class DataBaseManager:
    """A simple in-memory database manager for user data."""
    users_db = []
    _initialized = False

    def __init__(self):
        if not self._initialized:
            self._load_initial_data()
            DataBaseManager._initialized = True

    @staticmethod
    def _load_initial_data() -> None:
        """Load initial user data into the in-memory database."""
        DataBaseManager.users_db.clear()

        DataBaseManager.users_db.append(User(
            id=1, name="Alice", age=30, city="New York", email="alice@example.com",
            password_hash=get_password_hash("pass1"))),
        DataBaseManager.users_db.append(User(
            id=2, name="Bob", age=25, city="Boston", email="bob@example.com",
            password_hash=get_password_hash("pass2"))),
        DataBaseManager.users_db.append(User(
            id=3, name="Charlie", age=35, city="Chicago", email="charlie@example.com",
            password_hash=get_password_hash("pass3"))),
        DataBaseManager.users_db.append(User(
            id=4, name="Bubka", age=43, city="Svishtov", email="bubka@example.com",
            password_hash=get_password_hash("pass4"))),

    def get_user_by_username(self, username: str) -> User | None:
        """Retrieve a user by their username."""
        for user in self.users_db:
            if user.name == username:
                return user
        return None
