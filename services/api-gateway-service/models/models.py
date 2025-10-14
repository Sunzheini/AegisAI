from typing import Optional

from fastapi import Form
from pydantic import BaseModel, Field


class User(BaseModel):
    """User model representing a user in the system."""
    id: Optional[int] = Field(default=None, ge=1, description="Auto-generated positive integer ID")
    name: str = Field(min_length=1, max_length=100, description="User's full name")
    age: int = Field(ge=0, le=120, description="User's age between 0 and 120")
    city: str = Field(min_length=1, max_length=100, description="City name")
    email: Optional[str] = Field(default=None, description="Valid email address if provided")
    password_hash: Optional[str] = Field(default=None, description="Hashed password")

    # Example data for documentation on swagger UI
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Alice",
                "age": 30,
                "city": "New York",
                "email": "eee",
                "password_hash": "hashed_password_here"
            }
        }
    }

    @classmethod
    def as_form(
        cls,
        name: str = Form(..., min_length=1, max_length=100, description="User's full name"),
        age: int = Form(..., ge=0, le=120, description="User's age between 0 and 120"),
        city: str = Form(..., min_length=1, max_length=100, description="City name"),
        email: Optional[str] = Form(None, description="Valid email address if provided"),
        password: Optional[str] = Form(..., min_length=8, description="User's password"),
    ) -> "User":

        return cls(
            name=name,
            age=age,
            city=city,
            email=email,
            password_hash=password
        )


class UserCreate(BaseModel):
    """User creation model for input validation when creating a new user."""
    name: str = Field(min_length=1, max_length=100, description="User's full name")
    age: int = Field(ge=0, le=120, description="User's age between 0 and 120")
    city: str = Field(min_length=1, max_length=100, description="City name")
    email: Optional[str] = Field(default=None, description="Valid email address if provided")
    password: str = Field(min_length=8, description="User's password")


class UserUpdate(BaseModel):
    """User update model for input validation when updating an existing user."""
    name: str = Field(min_length=1, max_length=100, description="User's full name")
    age: int = Field(ge=0, le=120, description="User's age between 0 and 120")
    city: str = Field(min_length=1, max_length=100, description="City name")
    email: Optional[str] = Field(default=None, description="Valid email address if provided")
    password: Optional[str] = Field(default=None, min_length=8, description="User's new password (optional)")
