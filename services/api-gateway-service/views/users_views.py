from fastapi import APIRouter, HTTPException, Path, Query, Depends
from starlette import status as H

from models.models import User, UserCreate
from models.temp_db import DataBaseManager
from routers.security import auth_required, get_password_hash


class UsersViewsManager:
    """
    Manages user-related views (endpoints) for the FastAPI application.
    """
    def __init__(self, router: APIRouter, get_current_user):
        self.router = router
        self.get_current_user = get_current_user
        self.db = DataBaseManager

        self.register_views()

    def register_views(self):
        # GET list @ http://127.0.0.1:8000/users/list
        @self.router.get("/list", status_code=H.HTTP_200_OK)   # status code if successful
        @auth_required                                              # only authenticated users can see the list
        async def list_users(current_user = Depends(self.get_current_user)) -> list[User]:
            """
            List all users.
            :param current_user: the currently authenticated user (used in the decorator)
            :return: list of all users
            """
            return self.db.users_db

        # GET 1 with path parameter @ http://127.0.0.1:8000/users/id/2
        @self.router.get("/id/{user_id}", status_code=H.HTTP_200_OK)
        @auth_required
        async def get_user(user_id: int = Path(gt=0), current_user = Depends(self.get_current_user)) -> User:  # validation on path parameter
            """
            Get user by id (path parameter).
            :param user_id: the user id to retrieve
            :param current_user: the currently authenticated user (used in the decorator)
            :return: the user with the specified id
            """
            for user in self.db.users_db:
                if user.id == user_id:
                    return user
            raise HTTPException(status_code=404, detail="User not found with path parameter")

        # GET 1 with query parameter @ http://127.0.0.1:8000/users/list/city?city=Boston
        @self.router.get("/list/", status_code=H.HTTP_200_OK)
        @auth_required
        async def get_users_by_city(city: str = Query(min_length=1, max_length=100), current_user = Depends(self.get_current_user)) ->  list[User]:  # validation on query parameter
            """
            Get users by a query parameter city.
            :param city: the city to filter users by
            :param current_user: the currently authenticated user (used in the decorator)
            :return: list of users in the specified city
            """
            users_in_city = [user for user in self.db.users_db if user.city.lower() == city.lower()]
            if not users_in_city:
                raise HTTPException(status_code=404, detail="No users found in the specified city")
            return users_in_city

        # POST @ http://127.0.0.1:8000/users/create
        @self.router.post("/create", status_code=H.HTTP_201_CREATED)
        @auth_required
        async def create_user(new_item: UserCreate, current_user = Depends(self.get_current_user)) -> User:
            """
            Create a new user.
            request body (application/json)
            {"name": "Alice3", "age": 30, "city": "New York", "email": "alice@example.com", "password": "password123"}
            :param new_item: the new user data as a UserCreate model
            :param current_user: the currently authenticated user (used in the decorator)
            :return: the created user with assigned id
            """
            list_of_ids = [user.id for user in self.db.users_db]
            latest_id = max(list_of_ids) if list_of_ids else 0

            new_user = User(
                id=latest_id + 1,
                name=new_item.name,
                age=new_item.age,
                city=new_item.city,
                email=new_item.email,
                password_hash=get_password_hash(new_item.password)
            )

            self.db.users_db.append(new_user)
            return new_user

        # PUT @ http://127.0.0.1:8000/users/edit/1
        @self.router.put("/edit/{user_id}", status_code=H.HTTP_200_OK)
        @auth_required
        async def edit_user(user_id: int, updated_item: User, current_user = Depends(self.get_current_user)) -> User:
            """
            Edit user with given id.
            request body (application/json)
            {"name": "Alice2", "age": 30, "city": "New York", "email": "alice@example.com"}
            :param user_id: the user id to update
            :param updated_item: the updated user data
            :param current_user: the currently authenticated user (used in the decorator)
            :return: the updated user (200 OK)
            """
            for user in self.db.users_db:
                if user.id == user_id:
                    user.name = updated_item.name
                    user.age = updated_item.age
                    user.city = updated_item.city
                    user.email = updated_item.email
                    return user

            raise HTTPException(status_code=404, detail="User not found with path parameter")

        # DELETE @ http://127.0.0.1:8000/users/delete/3
        @self.router.delete("/delete/{user_id}", status_code=H.HTTP_200_OK)
        @auth_required
        async def delete_user(user_id: int = Path(gt=0), current_user = Depends(self.get_current_user)) -> dict:
            """
            Delete user with given id.
            :param user_id: the user id to delete
            :param current_user: the currently authenticated user (used in the decorator)
            :return: {"deleted": true, "id": <user_id>} (200 OK)
            """
            for user in self.db.users_db:
                if user.id == user_id:
                    self.db.users_db.remove(user)
                    return {"deleted": True, "id": user_id}

            raise HTTPException(status_code=404, detail="User not found with path parameter")
