"""
电影相关路由
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from ..services.recommendation import recommendation_service
from ..services.llm_service import llm_service
from ..services.vector_service import vector_service
from ..schemas.movie import MovieResponse, RecommendationRequest, RecommendationResponse
from ..models.movie import Movie
from ..data.database import SessionLocal

router = APIRouter(prefix="/api/movies", tags=["movies"])


@router.get("/search", response_model=List[MovieResponse])
async def search_movies(
        title: Optional[str] = Query(None, description="电影标题关键词"),
        genres: Optional[str] = Query(None, description="电影类型，多个用逗号分隔"),
        year_start: Optional[int] = Query(None, description="起始年份"),
        year_end: Optional[int] = Query(None, description="结束年份"),
        min_rating: Optional[float] = Query(None, ge=0.0, le=10.0, description="最低评分"),
        max_rating: Optional[float] = Query(None, ge=0.0, le=10.0, description="最高评分"),
        limit: int = Query(20, ge=1, le=100, description="返回数量限制")
):
    """高级电影搜索（含向量语义搜索增强）"""
    try:
        genres_list = []
        if genres:
            genres_list = [g.strip() for g in genres.split(',') if g.strip()]

        movies = recommendation_service.search_movies_advanced(
            title=title,
            genres=genres_list,
            year_start=year_start,
            year_end=year_end,
            min_rating=min_rating,
            max_rating=max_rating,
            limit=limit
        )

        # 如果有标题查询，补充向量语义搜索结果
        if title and len(movies) < limit:
            existing_ids = {str(m.get('movie_id')) for m in movies if m.get('movie_id')}
            try:
                vector_results = vector_service.semantic_search(
                    f"电影标题: {title} | 电影描述: {title}",
                    limit=limit
                )
                db = SessionLocal()
                try:
                    for vr in vector_results:
                        mid = vr.get('movie_id')
                        if mid and mid not in existing_ids:
                            movie = db.query(Movie).filter(Movie.movie_id == mid).first()
                            if movie:
                                movies.append(movie.to_dict())
                                existing_ids.add(mid)
                            if len(movies) >= limit:
                                break
                finally:
                    db.close()
            except Exception as e:
                print(f"向量搜索增强失败: {e}")

        # 转换为响应模型
        return [_movie_dict_to_response(movie) for movie in movies[:limit]]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/trending", response_model=List[MovieResponse])
async def get_trending_movies(limit: int = Query(20, ge=1, le=50, description="返回数量")):
    """获取热门电影"""
    try:
        movies = recommendation_service.get_trending_movies(limit)
        return [_movie_dict_to_response(movie) for movie in movies]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取热门电影失败: {str(e)}")


@router.get("/{movie_id}", response_model=MovieResponse)
async def get_movie_detail(movie_id: int):
    """获取电影详情"""
    db = SessionLocal()
    try:
        movie = db.query(Movie).filter(Movie.id == movie_id).first()
        if not movie:
            raise HTTPException(status_code=404, detail="电影不存在")
        return _movie_dict_to_response(movie.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取电影详情失败: {str(e)}")
    finally:
        db.close()


@router.get("/{movie_id}/similar", response_model=List[MovieResponse])
async def get_similar_movies(
        movie_id: str,
        limit: int = Query(10, ge=1, le=30, description="返回数量")
):
    """获取相似电影"""
    try:
        movies = recommendation_service.get_similar_movies(movie_id, limit)
        return [_movie_dict_to_response(movie) for movie in movies]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取相似电影失败: {str(e)}")


@router.post("/recommend", response_model=RecommendationResponse)
async def get_recommendations(request: RecommendationRequest):
    """智能电影推荐"""
    try:
        result = recommendation_service.get_recommendations_by_query(
            request.query,
            request.limit
        )

        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])

        # 转换推荐结果
        movie_responses = [
            _movie_dict_to_response(rec)
            for rec in result['recommendations']
        ]

        return RecommendationResponse(
            movies=movie_responses,
            query=result['query'],
            total=result['total']
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推荐失败: {str(e)}")


def _movie_dict_to_response(movie: dict) -> MovieResponse:
    """将电影字典转换为响应模型"""
    return MovieResponse(
        id=movie.get('id', 0),
        created_at=movie.get('created_at'),
        title=movie.get('title', ''),
        director=movie.get('directors'),
        year=_extract_year(movie.get('release_date')),
        genre=movie.get('genres'),
        rating=movie.get('rating'),
        plot=movie.get('summary'),
        cast=movie.get('actors'),
        duration=_extract_duration(movie.get('runtime')),
        poster_url=movie.get('poster'),
        view_count=movie.get('view_count', 0),
        like_count=movie.get('like_count', 0),
        movie_id=movie.get('movie_id'),
        reason=movie.get('reason', ''),
        match_score=movie.get('match_score')
    )


def _extract_year(date_string: Optional[str]) -> Optional[int]:
    """从日期字符串中提取年份"""
    if not date_string:
        return None

    import re
    match = re.search(r'(\d{4})', date_string)
    return int(match.group(1)) if match else None


def _extract_duration(runtime: Optional[str]) -> Optional[int]:
    """从运行时间字符串中提取分钟数"""
    if not runtime:
        return None

    import re
    match = re.search(r'(\d+)', runtime)
    return int(match.group(1)) if match else None