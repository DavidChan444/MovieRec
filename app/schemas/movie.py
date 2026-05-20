"""
电影数据模式定义
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class MovieResponse(BaseModel):
    """电影响应模型"""
    id: int = Field(..., description="数据库ID")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    title: str = Field(..., description="电影标题")
    director: Optional[str] = Field(None, description="导演")
    year: Optional[int] = Field(None, description="年份")
    genre: Optional[str] = Field(None, description="类型")
    rating: Optional[float] = Field(None, description="评分")
    plot: Optional[str] = Field(None, description="剧情")
    cast: Optional[str] = Field(None, description="演员")
    duration: Optional[int] = Field(None, description="时长（分钟）")
    poster_url: Optional[str] = Field(None, description="海报URL")
    view_count: int = Field(0, description="观看次数")
    like_count: int = Field(0, description="点赞数")
    movie_id: Optional[str] = Field(None, description="豆瓣电影ID")
    reason: Optional[str] = Field(None, description="推荐理由")
    match_score: Optional[float] = Field(None, description="匹配得分")

    class Config:
        from_attributes = True

class RecommendationRequest(BaseModel):
    """推荐请求"""
    query: str = Field(..., description="查询内容")
    limit: int = Field(10, ge=1, le=50, description="返回数量")

class RecommendationResponse(BaseModel):
    """推荐响应"""
    movies: List[MovieResponse] = Field(..., description="推荐的电影列表")
    query: str = Field(..., description="原始查询")
    total: int = Field(..., description="总数量")

