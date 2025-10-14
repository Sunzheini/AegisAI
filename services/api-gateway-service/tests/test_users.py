import pytest

from models.models import User
from support.security import get_password_hash


# --------------------------------------------------------------------------------------
# Fixtures specific to this module
# --------------------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def clear_users_before_test(database):
    database.clear_users()
    yield


@pytest.fixture
def sample_user_data(database):
    new_user_data = {
        "name": "Alice36",
        "age": 33,
        "city": "New York",
        "email": "alice33@example.com",
        "password": "testpassword123",  # Added password for user creation
    }
    return new_user_data


# --------------------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------------------
def test_create_user(client, sample_user_data, auth_headers):
    # Act
    response = client.post("/users/create", json=sample_user_data, headers=auth_headers)

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


def test_get_user_by_id(client, auth_headers, database):
    # Ensure at least one user exists
    all_users = database.get_all_users()
    if not all_users:
        user = User(
            id=1,
            name="testuser",
            age=30,
            city="Boston",
            email="testuser@example.com",
            password_hash=get_password_hash("testpassword"),
        )
        database.create_user(user)
        user_id = user.id
    else:
        user_id = all_users[0].id

    response = client.get(f"/users/id/{user_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id


def test_get_users_by_city(client, auth_headers, database):
    # Ensure at least one user in Boston exists
    all_users = database.get_all_users()
    if not any(u.city.lower() == "boston" for u in all_users):
        user = User(
            id=2,
            name="Alice",
            age=25,
            city="Boston",
            email="alice@example.com",
            password_hash=get_password_hash("alicepass"),
        )
        database.create_user(user)

    response = client.get("/users/list/?city=Boston", headers=auth_headers)
    assert response.status_code == 200
    users = response.json()
    assert all(user["city"].lower() == "boston" for user in users)


def test_edit_user(client, auth_headers, database):
    # Ensure a user to edit exists
    all_users = database.get_all_users()
    if not all_users:
        user = User(
            id=1,
            name="Bob",
            age=40,
            city="Chicago",
            email="bob@example.com",
            password_hash=get_password_hash("bobpass"),
        )
        database.create_user(user)
        user_id = user.id
    else:
        user_id = all_users[0].id

    update_data = {
        "name": "Bob2",
        "age": 41,
        "city": "Chicago",
        "email": "bob2@example.com",
    }
    response = client.put(
        f"/users/edit/{user_id}", json=update_data, headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["name"] == "Bob2"
    # Check update in DB
    updated_user = database.get_user_by_id(user_id)
    assert updated_user.name == "Bob2"


def test_delete_user(client, auth_headers, database):
    # Ensure a user to delete exists
    all_users = database.get_all_users()
    if not all_users:
        user_to_delete = User(
            id=123,
            name="deleteuser",
            age=40,
            city="DeleteCity",
            email="deleteuser@example.com",
            password_hash=get_password_hash("deletepassword"),
        )
        database.create_user(user_to_delete)
        user_id = user_to_delete.id
    else:
        user_id = all_users[0].id

    response = client.delete(f"/users/delete/{user_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True
    assert data["id"] == user_id
    # Confirm user is deleted
    assert database.get_user_by_id(user_id) is None


def test_login_success(client, database):
    # Setup
    database.clear_users()
    database.create_user(
        User(
            id=1,
            name="testuser",
            age=30,
            city="Boston",
            email="test@example.com",
            password_hash=get_password_hash("correctpassword"),
        )
    )

    # Test successful login
    login_data = {"username": "testuser", "password": "correctpassword"}
    response = client.post("/auth/login", data=login_data)

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, database):
    # Setup
    database.clear_users()
    database.create_user(
        User(
            id=1,
            name="testuser",
            age=30,
            city="Boston",
            email="test@example.com",
            password_hash=get_password_hash("correctpassword"),
        )
    )

    # Test wrong password
    login_data = {"username": "testuser", "password": "wrongpassword"}
    response = client.post("/auth/login", data=login_data)

    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_login_user_not_found(client, database):
    # Setup - empty database
    database.clear_users()

    # Test non-existent user
    login_data = {"username": "nonexistent", "password": "anypassword"}
    response = client.post("/auth/login", data=login_data)

    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_protected_endpoint_without_token(client):
    # Test accessing protected endpoint without token
    response = client.get("/users/list")
    assert response.status_code == 401


def test_protected_endpoint_with_invalid_token(client):
    # Test accessing protected endpoint with invalid token
    headers = {"Authorization": "Bearer invalid_token_here"}
    response = client.get("/users/list", headers=headers)
    assert response.status_code == 401


# run with `pytest` in the terminal
# run with `pytest -s` to see print statements
