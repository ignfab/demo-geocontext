from fastapi import Request
from pydantic import BaseModel
from typing import List

class User(BaseModel):
    id: str
    username: str
    email: str
    groups: List[str]

def get_current_user(
    request: Request
) -> User :
    """Retrieve current user from forwarded headers in request"""
    # X-Forwarded-User, X-Forwarded-Email, X-Forwarded-Preferred-Username and X-Forwarded-Groups
    id = request.headers.get('X-Forwarded-User','anonymous')
    username = request.headers.get('X-Forwarded-Preferred-Username','anonymous')
    email = request.headers.get('X-Forwarded-Email','anonymous@gpf.fr')
    
    groups_str=request.headers.get('X-Forwarded-Groups',None)
    groups = [] if groups_str is None else groups_str.split(',') 
    return User(id=id, username=username, email=email, groups=groups)
