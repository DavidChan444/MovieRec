"""
安全认证相关功能
"""
from datetime import datetime, timedelta
from typing import Any, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from .config import settings

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    """创建JWT访问令牌"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Union[str, None]:
    """验证JWT令牌"""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = payload.get("sub")
        return token_data
    except JWTError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """获取密码哈希"""
    print(f"Password type: {type(password)}")
    print(f"Password length: {len(password)}")
    print(f"Password bytes length: {len(password.encode('utf-8'))}")
    print(f"Password: {password}")

    result = pwd_context.hash(password)
    print(f"Hash result type: {type(result)}")
    return result


def create_user_session_token(user_id: int, additional_data: dict = None) -> str:
    """创建用户会话令牌"""
    payload = {
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
    }

    if additional_data:
        payload.update(additional_data)

    return create_access_token(subject=payload)


def decode_user_session_token(token: str) -> Union[dict, None]:
    """解码用户会话令牌"""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload.get("sub")
    except JWTError:
        return None