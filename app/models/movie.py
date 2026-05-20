"""
电影模型 - 适配豆瓣数据
"""
from sqlalchemy import Column, String, Integer, Float, Text, JSON
from .base import BaseModel

class Movie(BaseModel):
    """电影模型"""
    __tablename__ = "movies"

    # CSV数据字段
    movie_id = Column(String(20), unique=True, index=True)  # 豆瓣ID
    title = Column(String(200), nullable=False, index=True)
    rating = Column(Float, nullable=True, index=True)
    total_ratings = Column(Integer, default=0)
    directors = Column(Text, nullable=True)
    actors = Column(Text, nullable=True)
    screenwriters = Column(Text, nullable=True)
    release_date = Column(String(20), nullable=True)
    genres = Column(Text, nullable=True, index=True)
    countries = Column(Text, nullable=True)
    languages = Column(Text, nullable=True)
    runtime = Column(String(20), nullable=True)
    summary = Column(Text, nullable=True)
    link = Column(String(500), nullable=True)
    poster = Column(String(500), nullable=True)
    tags = Column(Text, nullable=True)

    # 推荐系统字段
    features = Column(JSON, nullable=True)  # 特征向量
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    dislike_count = Column(Integer, default=0)

    def __repr__(self):
        return f"<Movie(title='{self.title}', rating={self.rating})>"

    @property
    def genres_list(self):
        """返回类型列表"""
        if self.genres:
            return [g.strip() for g in self.genres.split(',')]
        return []

    @property
    def directors_list(self):
        """返回导演列表"""
        if self.directors:
            return [d.strip() for d in self.directors.split(',')]
        return []

    @property
    def actors_list(self):
        """返回演员列表"""
        if self.actors:
            return [a.strip() for a in self.actors.split(',')]
        return []

    @property
    def tags_list(self):
        """返回标签列表"""
        if self.tags:
            return [t.strip() for t in self.tags.split(',')]
        return []

    @property
    def runtime_minutes(self):
        """提取时长的分钟数"""
        if self.runtime and '分钟' in self.runtime:
            try:
                return int(self.runtime.replace('分钟', ''))
            except:
                return None
        return None

    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'movie_id': self.movie_id,
            'title': self.title,
            'rating': self.rating,
            'total_ratings': self.total_ratings,
            'directors': self.directors,
            'actors': self.actors,
            'genres': self.genres,
            'release_date': self.release_date,
            'summary': self.summary,
            'poster': self.poster,
            'runtime': self.runtime,
            'countries': self.countries,
            'languages': self.languages,
            'tags': self.tags,
            'tags_list': self.tags_list
        }