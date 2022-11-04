from datetime import timedelta
import os

import bcrypt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from db import schemas, models
from db.database import database

from .models import Token, TokenData, NewPassword
from .utils.auth import create_access_token, user_authenticate
from .utils.get_current_user import get_current_user, get_current_active_user
from .utils.mail import send_mail

user_router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/users/token")

@user_router.post("/create", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
async def create_user(backgroundtasks: BackgroundTasks, user: schemas.UserCreate):
    """
    Registration request.
    Args:
        user: form with user credentials - email, firstname, lastname and password.
        backgroundtasks: instance of BackgroundTasks class for email sending.
    Returns:
        User: model with user parameteres.
    """
    query_db_user = models.users.select().where(models.users.c.email == user.email)
    db_user = await database.execute(query_db_user)
    if db_user:
        raise HTTPException(status_code=400, detail="User with this email already exists.")

    hashed_password = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt())
    user_data = {
        "firstname": user.firstname,
        "lastname": user.lastname,
        "email": user.email,
        "hashed_password": hashed_password.decode(),
        "disabled": True
    }

    query_user_create = models.users.insert().values(**user_data)
    last_record_id = await database.execute(query_user_create) # creates new record and returns its id.
    resp = schemas.User(**user_data, id=last_record_id)
    await send_mail(resp.email, "verify", "Account Verification", backgroundtasks)
    return resp

@user_router.post("/token", response_model=Token, status_code=status.HTTP_201_CREATED)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login request.
    Args:
        form_data: form with OAuth2 parameteres. Most important are username and password.
    Returns:
        token: dictionary with access token and its type.
    """
    user = await user_authenticate(form_data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    access_token_expires = timedelta(minutes=int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES")))
    access_token = await create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@user_router.get("/me", response_model=schemas.User, status_code=status.HTTP_200_OK)
async def retrieve_current_user(current_user: schemas.User = Depends(get_current_active_user)):
    """ Request to get current user. """
    return current_user

@user_router.get("/verification", status_code=status.HTTP_200_OK)
async def email_verification(token: str):
    """
    Email verification request. If user is disabled, changes this attribute to False.
    Args:
        token: JWT access token.
    Returns:
        JSON Response if successful.
    """
    user = await get_current_user(token)
    if user and user.disabled:
        query_update = models.users.update().where(models.users.c.id == user.id).values(disabled=False)
        await database.execute(query_update)
        return {"Success": True}
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"}
    )

@user_router.delete("/me/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(current_user: schemas.User = Depends(get_current_active_user)):
    """ Request to delete current active user. """
    query = models.users.delete().where(models.users.c.id == current_user.id)
    await database.execute(query)

@user_router.post("/reset/send", status_code=status.HTTP_200_OK)
async def send_reset_mail(bacgroundtasks: BackgroundTasks, email: TokenData):
    """ Request to send email with link to reset password. """
    await send_mail(email.email, "reset", "Reset password.", bacgroundtasks)
    return {"Success": True}

@user_router.patch("/reset/new_password", status_code=status.HTTP_201_CREATED)
async def reset_password(new_password: NewPassword):
    """ Request to set new password using token to determine user. """
    user = await get_current_user(new_password.access_token)
    hashed_password = bcrypt.hashpw(new_password.new_password.encode(), bcrypt.gensalt())

    query = models.users.update().where(models.users.c.id == user.id).values(hashed_password=hashed_password.decode())
    await database.execute(query)
    return {"hashed_password": hashed_password}
