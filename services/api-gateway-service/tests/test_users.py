import pytest
from fastapi.testclient import TestClient

from main import app
from models.temp_db import DataBaseManager
from models.models import User

# --------------------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------------------
@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def database():
    db = DataBaseManager.users_db
    db.clear()  # reset
    return db


@pytest.fixture
def sample_user_data(database):
    new_user_data = {'name': 'Alice36', 'age': 33, 'city': 'New York', 'email': 'alice33@example.com'}
    return new_user_data


@pytest.fixture
def auth_token(client):
    # Reset DB and add a known user for testing
    db = DataBaseManager()
    db.users_db.clear()
    db.users_db.append(User(id=1, name="testuser", age=30, city="Boston", email="test@example.com"))

    login_data = {"username": "testuser", "password": "anything"}  # password is ignored in your code
    response = client.post("/auth/login", data=login_data)
    assert response.status_code == 200, f"Login failed: {response.json()}"
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# --------------------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------------------
def test_create_user(client, sample_user_data):
    # Act
    response = client.post("/users/create", json=sample_user_data)

    # Assert
    assert response.status_code == 201  # created

    data = response.json()
    assert data["name"] == sample_user_data["name"]
    assert data["age"] == sample_user_data["age"]
    assert data["city"] == sample_user_data["city"]
    assert data["email"] == sample_user_data["email"]
    assert "id" in data  # auto-generated ID


def test_list_users_requires_auth(client, auth_headers):
    # Without token
    response = client.get("/users/list")
    assert response.status_code == 401

    # With token
    response = client.get("/users/list", headers=auth_headers)
    assert response.status_code == 200
    users = response.json()
    assert isinstance(users, list)


def test_get_user_by_id(client):
    db = DataBaseManager()
    if not db.users_db:
        db.users_db.append(User(id=1, name="testuser", age=30, city="Boston", email="test@example.com"))

    user_id = db.users_db[0].id
    response = client.get(f"/users/id/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id


def test_get_users_by_city(client):
    db = DataBaseManager()
    db.users_db.append(User(id=2, name="Alice", age=25, city="Boston", email="alice@example.com"))

    response = client.get("/users/list/?city=Boston")
    assert response.status_code == 200
    users = response.json()
    assert all(user["city"].lower() == "boston" for user in users)


def test_edit_user(client):
    db = DataBaseManager()
    if not db.users_db:
        db.users_db.append(User(id=1, name="Bob", age=40, city="Chicago", email="bob@example.com"))

    user_id = db.users_db[0].id
    update_data = {"name": "Bob2", "age": 41, "city": "Chicago", "email": "bob2@example.com"}
    response = client.put(f"/users/edit/{user_id}", json=update_data)
    assert response.status_code == 204
    # Check update in DB
    user = next(u for u in db.users_db if u.id == user_id)
    assert user.name == "Bob2"


def test_delete_user(client):
    db = DataBaseManager()
    user_to_delete = User(id=999, name="Temp", age=50, city="LA", email="temp@example.com")
    db.users_db.append(user_to_delete)

    response = client.delete(f"/users/delete/{user_to_delete.id}")
    assert response.status_code == 204
    assert all(u.id != user_to_delete.id for u in db.users_db)


# run with `pytest` in th terminal
# run with `pytest -s` to see print statements