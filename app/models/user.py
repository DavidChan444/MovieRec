"""
用户相关数据模型
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.data.database import Base
import json


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # 基本信息
    full_name = Column(String(100))
    avatar_url = Column(String(255))
    birth_year = Column(Integer)
    gender = Column(String(10))
    location = Column(String(100))

    # 用户状态
    is_active = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    # 用户偏好数据
    preference_profile = Column(JSON)  # 用户偏好画像
    genre_preferences = Column(JSON)  # 类型偏好得分
    director_preferences = Column(JSON)  # 导演偏好
    actor_preferences = Column(JSON)  # 演员偏好
    rating_preferences = Column(JSON)  # 评分偏好分布

    # 行为统计
    total_interactions = Column(Integer, default=0)
    total_movies_watched = Column(Integer, default=0)
    total_likes = Column(Integer, default=0)
    total_dislikes = Column(Integer, default=0)
    total_favorites = Column(Integer, default=0)  # 已废弃，保留列以兼容旧数据库

    # 学习模型参数
    learning_rate = Column(Float, default=0.1)
    model_version = Column(String(20), default="v1.0")
    last_model_update = Column(DateTime)

    # 关联关系
    interactions = relationship("UserInteraction", back_populates="user")
    reviews = relationship("UserReview", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "avatar_url": self.avatar_url,
            "birth_year": self.birth_year,
            "gender": self.gender,
            "location": self.location,
            "is_active": self.is_active,
            "is_premium": self.is_premium,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "preference_profile": self.preference_profile or {},
            "genre_preferences": self.genre_preferences or {},
            "total_interactions": self.total_interactions,
            "total_movies_watched": self.total_movies_watched,
            "model_version": self.model_version
        }

    @property
    def genre_preferences_dict(self):
        """获取类型偏好字典"""
        return json.loads(self.genre_preferences) if self.genre_preferences else {}

    @property
    def preference_profile_dict(self):
        """获取偏好画像字典"""
        return json.loads(self.preference_profile) if self.preference_profile else {}


class UserInteraction(Base):
    __tablename__ = "user_interactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"),nullable=False, index=True)
    movie_id = Column(String(50), nullable=False, index=True)

    # 交互类型和详情
    interaction_type = Column(String(20), nullable=False)  # view, like, dislike, cancel_like, cancel_dislike, cancel_view, share, search, click
    interaction_value = Column(Float)  # 交互强度值
    session_id = Column(String(100))  # 会话ID

    # 上下文信息
    search_query = Column(Text)  # 搜索查询
    recommendation_context = Column(JSON)  # 推荐上下文
    device_info = Column(String(100))  # 设备信息

    # 时间信息
    interaction_time = Column(DateTime, default=datetime.utcnow)
    duration = Column(Integer)  # 交互持续时间（秒）

    # 位置信息
    position_in_list = Column(Integer)  # 在推荐列表中的位置
    total_list_size = Column(Integer)  # 推荐列表总大小

    # 反馈信息
    user_feedback = Column(Text)  # 用户反馈文本
    feedback_score = Column(Float)  # 反馈得分

    # 关联关系
    user = relationship("User", back_populates="interactions")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "movie_id": self.movie_id,
            "interaction_type": self.interaction_type,
            "interaction_value": self.interaction_value,
            "search_query": self.search_query,
            "recommendation_context": self.recommendation_context,
            "interaction_time": self.interaction_time.isoformat() if self.interaction_time else None,
            "duration": self.duration,
            "position_in_list": self.position_in_list,
            "user_feedback": self.user_feedback,
            "feedback_score": self.feedback_score
        }


class UserReview(Base):
    __tablename__ = "user_reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"),nullable=False, index=True)
    movie_id = Column(String(50), nullable=False, index=True)

    # 评价内容
    rating = Column(Float, nullable=False)  # 用户评分 1-10
    review_text = Column(Text)  # 评价文本
    tags = Column(JSON)  # 用户标签

    # 情感分析结果
    sentiment_score = Column(Float)  # 情感得分 -1到1
    emotion_analysis = Column(JSON)  # 情感分析详情

    # 时间信息
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    # 有用性评价
    helpful_count = Column(Integer, default=0)
    total_votes = Column(Integer, default=0)

    # 关联关系
    user = relationship("User", back_populates="reviews")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "movie_id": self.movie_id,
            "rating": self.rating,
            "review_text": self.review_text,
            "tags": self.tags or [],
            "sentiment_score": self.sentiment_score,
            "emotion_analysis": self.emotion_analysis or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "helpful_count": self.helpful_count,
            "total_votes": self.total_votes
        }


class UserPreferenceVector(Base):
    __tablename__ = "user_preference_vectors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"),nullable=False, index=True)

    # 向量信息
    vector_type = Column(String(50), nullable=False)  # genre, director, actor, content
    vector_data = Column(JSON)  # 实际向量数据
    vector_dimension = Column(Integer)

    # 元数据
    confidence_score = Column(Float)  # 置信度
    sample_size = Column(Integer)  # 样本大小
    last_updated = Column(DateTime, default=datetime.utcnow)

    # 版本信息
    model_version = Column(String(20), default="v1.0")
    is_active = Column(Boolean, default=True)

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "vector_type": self.vector_type,
            "vector_data": self.vector_data,
            "vector_dimension": self.vector_dimension,
            "confidence_score": self.confidence_score,
            "sample_size": self.sample_size,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "model_version": self.model_version,
            "is_active": self.is_active
        }


class ChatSession(Base):
    """聊天会话"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), default="新对话")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", order_by="ChatMessage.created_at")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active,
            "message_count": len(self.messages) if self.messages else 0
        }


class ChatMessage(Base):
    """聊天消息"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    recommendations = Column(JSON)  # 推荐电影列表
    query_analysis = Column(JSON)  # 查询分析结果
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "recommendations": self.recommendations or [],
            "query_analysis": self.query_analysis or {},
            "created_at": self.created_at.isoformat() if self.created_at else None
        }