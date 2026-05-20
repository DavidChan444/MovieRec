"""
用户管理API路由
"""
from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime

from ..data.database import SessionLocal
from ..models.user import User, UserInteraction, UserReview
from ..core.security import verify_password, get_password_hash, create_access_token, verify_token
from ..services.user_behavior_service import user_behavior_service
from ..services.adaptive_recommendation_service import adaptive_recommendation_service

router = APIRouter(prefix="/api/users", tags=["users"])
security = HTTPBearer()


# Pydantic 模型
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    birth_year: Optional[int] = None
    gender: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    birth_year: Optional[int] = None
    gender: Optional[str] = None
    location: Optional[str] = None


class InteractionRequest(BaseModel):
    movie_id: str
    interaction_type: str  # view, like, dislike, cancel_like, cancel_dislike, share, search, click
    duration: Optional[int] = None
    search_query: Optional[str] = None
    position_in_list: Optional[int] = None
    user_feedback: Optional[str] = None


class ReviewRequest(BaseModel):
    movie_id: str
    rating: float  # 1-10
    review_text: Optional[str] = None
    tags: Optional[List[str]] = None


def get_database():
    """数据库依赖"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security),
                     db: Session = Depends(get_database)) -> User:
    """获取当前用户"""
    token = credentials.credentials
    user_data = verify_token(token)

    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == int(user_data)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )

    return user


@router.post("/register")
async def register_user(user_data: UserRegister, db: Session = Depends(get_database)):
    """用户注册"""
    try:
        # 检查用户名是否存在
        existing_user = db.query(User).filter(User.username == user_data.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )

        # 检查邮箱是否存在
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被注册"
            )

        # 创建新用户
        print(f"Received password: {user_data.password}")
        print(f"Password length: {len(user_data.password)}")

        # 确保密码是字符串
        password_str = str(user_data.password)

        # 创建哈希
        hashed_password = get_password_hash(password_str)
        print(f"Hashed password length: {len(hashed_password)}")

        new_user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            birth_year=user_data.birth_year,
            gender=user_data.gender,
            created_at=datetime.utcnow()
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # 生成访问令牌
        access_token = create_access_token(subject=new_user.id)

        print(f"✅ 新用户注册成功: {new_user.username} (ID: {new_user.id})")

        return {
            "message": "注册成功",
            "user": new_user.to_dict(),
            "access_token": access_token,
            "token_type": "bearer"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册失败: {str(e)}"
        )


@router.post("/login")
async def login_user(login_data: UserLogin, db: Session = Depends(get_database)):
    """用户登录"""
    try:
        # 验证用户
        user = db.query(User).filter(User.username == login_data.username).first()

        if not user or not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="账户已被禁用"
            )

        # 更新最后登录时间
        user.last_login = datetime.utcnow()
        db.commit()

        # 生成访问令牌
        access_token = create_access_token(subject=user.id)

        print(f"✅ 用户登录成功: {user.username} (ID: {user.id})")

        return {
            "message": "登录成功",
            "user": user.to_dict(),
            "access_token": access_token,
            "token_type": "bearer"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登录失败: {str(e)}"
        )


@router.get("/me")
async def get_user_info(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "user": current_user.to_dict(),
        "behavior_stats": user_behavior_service.get_user_behavior_stats(current_user.id)
    }


@router.put("/me")
async def update_user_info(
        user_update: UserUpdate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_database)
):
    """更新用户信息"""
    try:
        # 更新用户信息
        if user_update.full_name is not None:
            current_user.full_name = user_update.full_name
        if user_update.birth_year is not None:
            current_user.birth_year = user_update.birth_year
        if user_update.gender is not None:
            current_user.gender = user_update.gender
        if user_update.location is not None:
            current_user.location = user_update.location

        db.commit()

        return {
            "message": "用户信息更新成功",
            "user": current_user.to_dict()
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败: {str(e)}"
        )


@router.post("/interactions")
async def record_interaction(
        interaction: InteractionRequest,
        current_user: User = Depends(get_current_user)
):
    """记录用户交互行为"""
    try:
        success = user_behavior_service.record_interaction(
            user_id=current_user.id,
            movie_id=interaction.movie_id,
            interaction_type=interaction.interaction_type,
            duration=interaction.duration,
            search_query=interaction.search_query,
            position_in_list=interaction.position_in_list,
            user_feedback=interaction.user_feedback
        )

        if success:
            return {"message": "交互记录成功"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="交互记录失败"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"记录交互失败: {str(e)}"
        )


@router.post("/reviews")
async def create_review(
        review: ReviewRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_database)
):
    """创建电影评价"""
    try:
        # 检查是否已经评价过
        existing_review = db.query(UserReview).filter(
            UserReview.user_id == current_user.id,
            UserReview.movie_id == review.movie_id
        ).first()

        if existing_review:
            # 更新现有评价
            existing_review.rating = review.rating
            existing_review.review_text = review.review_text
            existing_review.tags = review.tags
            existing_review.updated_at = datetime.utcnow()
            message = "评价更新成功"
        else:
            # 创建新评价
            new_review = UserReview(
                user_id=current_user.id,
                movie_id=review.movie_id,
                rating=review.rating,
                review_text=review.review_text,
                tags=review.tags,
                created_at=datetime.utcnow()
            )
            db.add(new_review)
            message = "评价创建成功"

        db.commit()

        # 同时记录为交互行为
        user_behavior_service.record_interaction(
            user_id=current_user.id,
            movie_id=review.movie_id,
            interaction_type="review",
            user_feedback=review.review_text,
            feedback_score=review.rating
        )

        return {"message": message}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"评价失败: {str(e)}"
        )


@router.get("/recommendations")
async def get_personalized_recommendations(
        query: str = "",
        limit: int = 10,
        current_user: User = Depends(get_current_user)
):
    """获取个性化推荐"""
    try:
        result = adaptive_recommendation_service.get_personalized_recommendations(
            user_id=current_user.id,
            query=query,
            limit=limit
        )

        if 'error' in result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result['error']
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取推荐失败: {str(e)}"
        )


@router.get("/preferences")
async def get_user_preferences(current_user: User = Depends(get_current_user)):
    """获取用户偏好分析"""
    try:
        preferences = user_behavior_service.analyze_user_preferences(current_user.id)
        return {
            "user_id": current_user.id,
            "preferences": preferences,
            "behavior_stats": user_behavior_service.get_user_behavior_stats(current_user.id)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取偏好分析失败: {str(e)}"
        )


@router.get("/interactions")
async def get_user_interactions(
        limit: int = 50,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_database)
):
    """获取用户交互历史"""
    try:
        interactions = db.query(UserInteraction).filter(
            UserInteraction.user_id == current_user.id
        ).order_by(UserInteraction.interaction_time.desc()).limit(limit).all()

        return {
            "user_id": current_user.id,
            "interactions": [interaction.to_dict() for interaction in interactions],
            "total": len(interactions)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取交互历史失败: {str(e)}"
        )


@router.get("/interactions/movies")
async def get_user_interaction_movies(
        interaction_type: Optional[str] = Query(None, description="like, dislike, view"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        current_user: User = Depends(get_current_user)
):
    """获取用户交互过的电影列表（带电影详情）"""
    try:
        result = user_behavior_service.get_user_movies_by_interaction(
            user_id=current_user.id,
            interaction_type=interaction_type,
            limit=limit,
            offset=offset
        )

        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取交互电影失败: {str(e)}"
        )


@router.delete("/account")
async def delete_account(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_database)
):
    """删除用户账户"""
    try:
        # 软删除：标记为不活跃
        current_user.is_active = False
        db.commit()

        return {"message": "账户已注销"}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注销账户失败: {str(e)}"
        )