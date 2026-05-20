"""
用户行为分析和学习服务
"""
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import numpy as np
from collections import defaultdict, Counter
import math

from ..data.database import SessionLocal
from ..models.user import User, UserInteraction, UserReview, UserPreferenceVector
from ..models.movie import Movie
from ..core.config import settings


class UserBehaviorService:
    def __init__(self):
        self.behavior_weights = settings.BEHAVIOR_WEIGHT_CONFIG
        self.decay_days = settings.PREFERENCE_DECAY_DAYS
        self.min_interactions = settings.MIN_INTERACTIONS_FOR_LEARNING

    def record_interaction(self,
                           user_id: int,
                           movie_id: str,
                           interaction_type: str,
                           **kwargs) -> bool:
        """记录用户交互行为"""
        db = SessionLocal()
        try:
            # 创建交互记录
            interaction = UserInteraction(
                user_id=user_id,
                movie_id=movie_id,
                interaction_type=interaction_type,
                interaction_value=self.behavior_weights.get(interaction_type, 1.0),
                search_query=kwargs.get('search_query'),
                recommendation_context=kwargs.get('recommendation_context'),
                device_info=kwargs.get('device_info'),
                session_id=kwargs.get('session_id'),
                duration=kwargs.get('duration'),
                position_in_list=kwargs.get('position_in_list'),
                total_list_size=kwargs.get('total_list_size'),
                user_feedback=kwargs.get('user_feedback'),
                feedback_score=kwargs.get('feedback_score')
            )

            db.add(interaction)

            # 更新用户统计信息
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.total_interactions += 1

                if interaction_type == 'like':
                    user.total_likes += 1
                elif interaction_type == 'cancel_like':
                    user.total_likes = max(0, user.total_likes - 1)
                elif interaction_type == 'dislike':
                    user.total_dislikes += 1
                elif interaction_type == 'cancel_dislike':
                    user.total_dislikes = max(0, user.total_dislikes - 1)
                elif interaction_type == 'view':
                    user.total_movies_watched += 1
                elif interaction_type == 'cancel_view':
                    user.total_movies_watched = max(0, user.total_movies_watched - 1)

            # 处理取消操作：删除原始交互记录，使电影不再被排除
            cancel_to_original = {
                'cancel_like': 'like',
                'cancel_dislike': 'dislike',
                'cancel_view': 'view'
            }
            if interaction_type in cancel_to_original:
                original_type = cancel_to_original[interaction_type]
                # 删除最旧的原始交互记录
                original = db.query(UserInteraction).filter(
                    UserInteraction.user_id == user_id,
                    UserInteraction.movie_id == movie_id,
                    UserInteraction.interaction_type == original_type
                ).first()
                if original:
                    db.delete(original)

            db.commit()

            # 触发异步学习更新（如果有足够的交互）
            if user and user.total_interactions >= self.min_interactions:
                self._trigger_learning_update(user_id)

            print(f"✅ 记录用户 {user_id} 对电影 {movie_id} 的 {interaction_type} 行为")
            return True

        except Exception as e:
            db.rollback()
            print(f"❌ 记录交互失败: {e}")
            return False
        finally:
            db.close()

    def analyze_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """分析用户偏好"""
        db = SessionLocal()
        try:
            print(f" 分析用户 {user_id} 的偏好...")

            # 获取用户最近的交互记录
            cutoff_date = datetime.utcnow() - timedelta(days=self.decay_days)

            interactions = db.query(UserInteraction).filter(
                UserInteraction.user_id == user_id,
                UserInteraction.interaction_time >= cutoff_date
            ).all()

            if len(interactions) < 3:
                print(f"⚠️ 用户交互数据不足 ({len(interactions)} < 3)")
                return self._get_default_preferences()

            # 获取相关电影信息
            movie_ids = list(set([i.movie_id for i in interactions]))
            movies = db.query(Movie).filter(Movie.movie_id.in_(movie_ids)).all()
            movie_dict = {str(m.movie_id): m for m in movies}

            # 分析各种偏好
            genre_preferences = self._analyze_genre_preferences(interactions, movie_dict)
            director_preferences = self._analyze_director_preferences(interactions, movie_dict)
            actor_preferences = self._analyze_actor_preferences(interactions, movie_dict)
            rating_preferences = self._analyze_rating_preferences(interactions, movie_dict)
            temporal_patterns = self._analyze_temporal_patterns(interactions)
            sentiment_analysis = self._analyze_sentiment_patterns(user_id, db)

            # 构建用户画像
            user_profile = {
                "user_id": user_id,
                "analysis_date": datetime.utcnow().isoformat(),
                "sample_size": len(interactions),
                "preferences": {
                    "genres": genre_preferences,
                    "directors": director_preferences,
                    "actors": actor_preferences,
                    "ratings": rating_preferences,
                    "temporal": temporal_patterns,
                    "sentiment": sentiment_analysis
                },
                "confidence_score": self._calculate_confidence_score(len(interactions)),
                "dominant_genres": self._get_dominant_genres(genre_preferences),
                "recommendation_strategy": self._determine_recommendation_strategy(
                    genre_preferences, rating_preferences, sentiment_analysis
                )
            }

            # 更新用户偏好数据
            self._update_user_preference_profile(db, user_id, user_profile)

            print(f"✅ 用户 {user_id} 偏好分析完成")
            return user_profile

        except Exception as e:
            print(f"❌ 用户偏好分析失败: {e}")
            return self._get_default_preferences()
        finally:
            db.close()

    def _analyze_genre_preferences(self, interactions: List[UserInteraction], movie_dict: Dict) -> Dict[str, float]:
        """分析类型偏好"""
        genre_scores = defaultdict(float)
        genre_counts = defaultdict(int)

        for interaction in interactions:
            movie = movie_dict.get(interaction.movie_id)
            if not movie or not movie.genres:
                continue

            # 应用时间衰减
            time_weight = self._calculate_time_decay(interaction.interaction_time)
            interaction_weight = interaction.interaction_value * time_weight

            # 分析每个类型
            genres = movie.genres_list
            for genre in genres:
                genre_scores[genre] += interaction_weight
                genre_counts[genre] += 1

        # 计算标准化得分
        if not genre_scores:
            return {}

        max_score = max(genre_scores.values())
        normalized_scores = {}

        for genre, score in genre_scores.items():
            # 结合频次和得分
            frequency_bonus = math.log(genre_counts[genre] + 1) * 0.1
            normalized_score = (score / max_score) + frequency_bonus
            normalized_scores[genre] = min(normalized_score, 1.0)

        # 返回前10个类型
        sorted_genres = sorted(normalized_scores.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_genres[:10])

    def _analyze_director_preferences(self, interactions: List[UserInteraction], movie_dict: Dict) -> Dict[str, float]:
        """分析导演偏好"""
        director_scores = defaultdict(float)

        for interaction in interactions:
            movie = movie_dict.get(interaction.movie_id)
            if not movie or not movie.directors:
                continue

            time_weight = self._calculate_time_decay(interaction.interaction_time)
            interaction_weight = interaction.interaction_value * time_weight

            # 分析导演（假设多个导演用逗号分隔）
            directors = [d.strip() for d in movie.directors.split(',')]
            for director in directors[:2]:  # 只考虑前2个导演
                if director:
                    director_scores[director] += interaction_weight

        # 标准化
        if not director_scores:
            return {}

        max_score = max(director_scores.values())
        normalized_scores = {k: v / max_score for k, v in director_scores.items()}

        # 返回前5个导演
        sorted_directors = sorted(normalized_scores.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_directors[:5])

    def _analyze_actor_preferences(self, interactions: List[UserInteraction], movie_dict: Dict) -> Dict[str, float]:
        """分析演员偏好"""
        actor_scores = defaultdict(float)

        for interaction in interactions:
            movie = movie_dict.get(interaction.movie_id)
            if not movie or not movie.actors:
                continue

            time_weight = self._calculate_time_decay(interaction.interaction_time)
            interaction_weight = interaction.interaction_value * time_weight

            # 分析主要演员
            actors = [a.strip() for a in movie.actors.split(',')]
            for i, actor in enumerate(actors[:5]):  # 只考虑前5个演员
                if actor:
                    # 主演权重更高
                    position_weight = 1.0 - (i * 0.1)
                    actor_scores[actor] += interaction_weight * position_weight

        # 标准化
        if not actor_scores:
            return {}

        max_score = max(actor_scores.values())
        normalized_scores = {k: v / max_score for k, v in actor_scores.items()}

        # 返回前8个演员
        sorted_actors = sorted(normalized_scores.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_actors[:8])

    def _analyze_rating_preferences(self, interactions: List[UserInteraction], movie_dict: Dict) -> Dict[str, Any]:
        """分析评分偏好"""
        ratings = []
        weighted_ratings = []

        for interaction in interactions:
            movie = movie_dict.get(interaction.movie_id)
            if not movie or not movie.rating:
                continue

            time_weight = self._calculate_time_decay(interaction.interaction_time)
            weight = interaction.interaction_value * time_weight

            ratings.append(movie.rating)
            weighted_ratings.extend([movie.rating] * int(abs(weight) * 10))

        if not ratings:
            return {"preference": "medium", "avg_rating": 7.0}

        avg_rating = np.mean(ratings)
        weighted_avg = np.mean(weighted_ratings) if weighted_ratings else avg_rating
        std_rating = np.std(ratings) if len(ratings) > 1 else 0

        # 分析偏好类型
        if weighted_avg >= 8.5:
            preference_type = "high_quality"
        elif weighted_avg >= 7.0:
            preference_type = "medium_high"
        elif weighted_avg >= 6.0:
            preference_type = "medium"
        else:
            preference_type = "diverse"

        # 分析评分分布
        rating_distribution = {}
        for rating in ratings:
            bucket = f"{int(rating)}-{int(rating) + 0.9}"
            rating_distribution[bucket] = rating_distribution.get(bucket, 0) + 1

        return {
            "preference": preference_type,
            "avg_rating": round(weighted_avg, 2),
            "std_rating": round(std_rating, 2),
            "distribution": rating_distribution,
            "min_acceptable": max(weighted_avg - 1.5, 5.0),
            "ideal_range": [weighted_avg - 0.5, weighted_avg + 1.0]
        }

    def _analyze_temporal_patterns(self, interactions: List[UserInteraction]) -> Dict[str, Any]:
        """分析时间模式"""
        hours = [i.interaction_time.hour for i in interactions]
        weekdays = [i.interaction_time.weekday() for i in interactions]

        # 活跃时段分析
        hour_counter = Counter(hours)
        peak_hours = [h for h, count in hour_counter.most_common(3)]

        # 活跃日期分析
        weekday_counter = Counter(weekdays)
        peak_weekdays = [d for d, count in weekday_counter.most_common(3)]

        # 最近活跃度
        recent_interactions = [i for i in interactions
                               if i.interaction_time >= datetime.utcnow() - timedelta(days=7)]
        recent_activity = len(recent_interactions)

        return {
            "peak_hours": peak_hours,
            "peak_weekdays": peak_weekdays,
            "recent_activity": recent_activity,
            "total_days_active": len(set(i.interaction_time.date() for i in interactions)),
            "avg_interactions_per_day": len(interactions) / max(1, len(set(
                i.interaction_time.date() for i in interactions)))
        }

    def _analyze_sentiment_patterns(self, user_id: int, db: Session) -> Dict[str, Any]:
        """分析情感模式"""
        reviews = db.query(UserReview).filter(UserReview.user_id == user_id).all()

        if not reviews:
            return {"overall_sentiment": "neutral", "confidence": 0.0}

        sentiments = [r.sentiment_score for r in reviews if r.sentiment_score is not None]
        ratings = [r.rating for r in reviews]

        if not sentiments:
            # 从评分推断情感
            if not ratings:
                return {"overall_sentiment": "neutral", "confidence": 0.0}

            avg_rating = np.mean(ratings)
            if avg_rating >= 8.0:
                sentiment_type = "positive"
            elif avg_rating >= 6.0:
                sentiment_type = "neutral"
            else:
                sentiment_type = "negative"

            confidence = min(len(ratings) / 10.0, 1.0)

        else:
            avg_sentiment = np.mean(sentiments)
            if avg_sentiment >= 0.3:
                sentiment_type = "positive"
            elif avg_sentiment >= -0.3:
                sentiment_type = "neutral"
            else:
                sentiment_type = "negative"

            confidence = min(len(sentiments) / 15.0, 1.0)

        return {
            "overall_sentiment": sentiment_type,
            "confidence": round(confidence, 3),
            "avg_rating": round(np.mean(ratings), 2) if ratings else None,
            "total_reviews": len(reviews)
        }

    def _calculate_time_decay(self, interaction_time: datetime) -> float:
        """计算时间衰减权重"""
        days_ago = (datetime.utcnow() - interaction_time).days
        decay_factor = 0.95  # 每天衰减5%
        return decay_factor ** days_ago

    def _calculate_confidence_score(self, sample_size: int) -> float:
        """计算置信度得分"""
        # 基于样本大小的置信度函数
        return min(1.0, sample_size / 50.0)

    def _get_dominant_genres(self, genre_preferences: Dict[str, float]) -> List[str]:
        """获取主导类型"""
        if not genre_preferences:
            return []

        # 获取得分大于0.7的类型
        dominant = [genre for genre, score in genre_preferences.items() if score >= 0.7]

        # 如果没有高得分类型，返回前3个
        if not dominant:
            sorted_genres = sorted(genre_preferences.items(), key=lambda x: x[1], reverse=True)
            dominant = [g[0] for g in sorted_genres[:3]]

        return dominant

    def _determine_recommendation_strategy(self, genre_prefs: Dict, rating_prefs: Dict, sentiment: Dict) -> Dict[
        str, Any]:
        """确定推荐策略"""
        strategy = {
            "primary_method": "hybrid",
            "diversity_level": "medium",
            "exploration_rate": 0.2,
            "quality_threshold": 7.0
        }

        # 基于类型偏好确定多样性
        if len(genre_prefs) <= 2:
            strategy["diversity_level"] = "low"
            strategy["exploration_rate"] = 0.1
        elif len(genre_prefs) >= 5:
            strategy["diversity_level"] = "high"
            strategy["exploration_rate"] = 0.3

        # 基于评分偏好调整质量阈值
        if rating_prefs.get("preference") == "high_quality":
            strategy["quality_threshold"] = 8.5
            strategy["primary_method"] = "content_based"
        elif rating_prefs.get("preference") == "diverse":
            strategy["quality_threshold"] = 6.0
            strategy["primary_method"] = "collaborative"

        # 基于情感调整探索率
        if sentiment.get("overall_sentiment") == "positive":
            strategy["exploration_rate"] *= 1.2
        elif sentiment.get("overall_sentiment") == "negative":
            strategy["exploration_rate"] *= 0.8

        return strategy

    def _get_default_preferences(self) -> Dict[str, Any]:
        """获取默认偏好设置"""
        return {
            "user_id": None,
            "analysis_date": datetime.utcnow().isoformat(),
            "sample_size": 0,
            "preferences": {
                "genres": {"剧情": 0.8, "喜剧": 0.6, "科幻": 0.5},
                "directors": {},
                "actors": {},
                "ratings": {"preference": "medium", "avg_rating": 7.0},
                "temporal": {},
                "sentiment": {"overall_sentiment": "neutral", "confidence": 0.0}
            },
            "confidence_score": 0.0,
            "dominant_genres": ["剧情"],
            "recommendation_strategy": {
                "primary_method": "content_based",
                "diversity_level": "medium",
                "exploration_rate": 0.2,
                "quality_threshold": 7.0
            }
        }

    def _update_user_preference_profile(self, db: Session, user_id: int, profile: Dict):
        """更新用户偏好画像"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.preference_profile = json.dumps(profile, ensure_ascii=False)
                user.genre_preferences = json.dumps(profile["preferences"]["genres"], ensure_ascii=False)
                user.director_preferences = json.dumps(profile["preferences"]["directors"], ensure_ascii=False)
                user.actor_preferences = json.dumps(profile["preferences"]["actors"], ensure_ascii=False)
                user.rating_preferences = json.dumps(profile["preferences"]["ratings"], ensure_ascii=False)
                user.last_model_update = datetime.utcnow()
                db.commit()
                print(f"✅ 用户 {user_id} 偏好画像已更新")
        except Exception as e:
            print(f"❌ 更新用户偏好画像失败: {e}")

    def _trigger_learning_update(self, user_id: int):
        """触发学习更新"""
        try:
            # 这里可以加入异步任务队列
            print(f" 触发用户 {user_id} 的学习模型更新")
            self.analyze_user_preferences(user_id)
        except Exception as e:
            print(f"❌ 触发学习更新失败: {e}")

    def get_interacted_movie_ids(self, user_id: int) -> set:
        """获取用户已交互的所有电影ID，用于排除推荐"""
        db = SessionLocal()
        try:
            interactions = db.query(UserInteraction.movie_id).filter(
                UserInteraction.user_id == user_id,
                UserInteraction.movie_id != ''
            ).distinct().all()
            return {i[0] for i in interactions if i[0]}
        except Exception as e:
            print(f"获取交互电影ID失败: {e}")
            return set()
        finally:
            db.close()

    def get_user_movies_by_interaction(self, user_id: int, interaction_type: str = None,
                                         limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """获取用户按交互类型分类的电影列表（带电影详情）"""
        db = SessionLocal()
        try:
            query = db.query(UserInteraction).filter(
                UserInteraction.user_id == user_id,
                UserInteraction.movie_id != ''
            )

            if interaction_type:
                if isinstance(interaction_type, list):
                    query = query.filter(UserInteraction.interaction_type.in_(interaction_type))
                else:
                    query = query.filter(UserInteraction.interaction_type == interaction_type)

            interactions = query.order_by(
                UserInteraction.interaction_time.desc()
            ).all()

            # Deduplicate movie_ids while preserving order
            seen_movie_ids = set()
            ordered_movie_ids = []
            for interaction in interactions:
                if interaction.movie_id not in seen_movie_ids:
                    seen_movie_ids.add(interaction.movie_id)
                    ordered_movie_ids.append(interaction.movie_id)

            total = len(ordered_movie_ids)
            page_movie_ids = ordered_movie_ids[offset:offset + limit]

            # Get movie details
            movies = db.query(Movie).filter(
                Movie.movie_id.in_(page_movie_ids)
            ).all()

            movie_map = {m.movie_id: m for m in movies}
            movie_list = []
            for mid in page_movie_ids:
                if mid in movie_map:
                    movie_list.append(movie_map[mid].to_dict())

            return {
                "user_id": user_id,
                "interaction_type": interaction_type,
                "movies": movie_list,
                "total": total,
                "limit": limit,
                "offset": offset
            }

        except Exception as e:
            print(f"获取用户交互电影失败: {e}")
            return {"error": str(e), "movies": [], "total": 0}
        finally:
            db.close()

    def get_user_behavior_stats(self, user_id: int) -> Dict[str, Any]:
        """获取用户行为统计"""
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"error": "用户不存在"}

            # 最近30天的交互
            recent_date = datetime.utcnow() - timedelta(days=30)
            recent_interactions = db.query(UserInteraction).filter(
                UserInteraction.user_id == user_id,
                UserInteraction.interaction_time >= recent_date
            ).count()

            # 交互类型分布
            interactions = db.query(UserInteraction).filter(
                UserInteraction.user_id == user_id
            ).all()

            type_distribution = Counter([i.interaction_type for i in interactions])

            # 最活跃时段
            if interactions:
                hours = [i.interaction_time.hour for i in interactions]
                peak_hour = Counter(hours).most_common(1)[0][0] if hours else 12
            else:
                peak_hour = 12

            return {
                "user_id": user_id,
                "total_interactions": user.total_interactions,
                "recent_interactions_30d": recent_interactions,
                "interaction_distribution": dict(type_distribution),
                "peak_activity_hour": peak_hour,
                "total_movies_watched": user.total_movies_watched,
                "total_likes": user.total_likes,
                "total_dislikes": user.total_dislikes,
                "preference_confidence": user.preference_profile_dict.get("confidence_score", 0.0),
                "model_version": user.model_version,
                "last_update": user.last_model_update.isoformat() if user.last_model_update else None
            }

        except Exception as e:
            print(f"❌ 获取用户行为统计失败: {e}")
            return {"error": str(e)}
        finally:
            db.close()


# 全局用户行为服务实例
user_behavior_service = UserBehaviorService()