"""
自适应推荐服务 - 基于用户行为学习的个性化推荐
"""
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
import numpy as np
import json
import random
from datetime import datetime, timedelta

from ..data.database import SessionLocal
from ..models.user import User
from ..models.movie import Movie
from .user_behavior_service import user_behavior_service
from .langchain_service import langchain_service
from .vector_service import vector_service
from .recommendation import recommendation_service


class AdaptiveRecommendationService:
    def __init__(self):
        self.base_service = recommendation_service
        self.behavior_service = user_behavior_service

        # 推荐算法权重配置
        self.algorithm_weights = {
            "content_based": 0.3,
            "collaborative": 0.2,
            "vector_search": 0.3,
            "langchain": 0.2
        }

    def get_personalized_recommendations(self, user_id: int, query: str = "", limit: int = 10) -> Dict[str, Any]:
        """获取个性化推荐"""
        db = SessionLocal()
        try:
            print(f" 为用户 {user_id} 生成个性化推荐")

            # 获取用户偏好
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"error": "用户不存在"}

            # 分析用户偏好（如果需要更新）
            user_preferences = self._get_or_update_user_preferences(user_id, user)

            # 获取已交互的电影ID，用于排除
            excluded_movie_ids = self.behavior_service.get_interacted_movie_ids(user_id)

            # 确定推荐策略
            strategy = user_preferences.get("recommendation_strategy", {})

            # 根据策略选择推荐方法
            recommendations = self._generate_multi_algorithm_recommendations(
                user_id, user_preferences, query, strategy, limit, excluded_movie_ids
            )

            # 应用个性化过滤和排序
            filtered_recommendations = self._apply_personalized_filters(
                recommendations, user_preferences, strategy
            )

            # 添加多样性
            diversified_recommendations = self._add_diversity(
                filtered_recommendations, user_preferences, strategy.get("diversity_level", "medium")
            )

            # LangChain分析增强（不重复查询）
            diversified_recommendations = self._enrich_recommendations_with_langchain(
                diversified_recommendations, user_preferences, query
            )

            # 受控随机打乱（保留前2，打乱其余）
            diversified_recommendations = self._apply_controlled_shuffle(diversified_recommendations)

            # 生成解释
            explanations = self._generate_recommendation_explanations(
                diversified_recommendations[:limit], user_preferences, query
            )

            # 记录推荐行为
            self._log_recommendation_event(user_id, query, diversified_recommendations, strategy)

            return {
                "user_id": user_id,
                "query": query,
                "recommendations": diversified_recommendations[:limit],
                "explanations": explanations,
                "strategy_used": strategy,
                "user_preferences_summary": self._get_preferences_summary(user_preferences),
                "recommendation_context": {
                    "total_candidates": len(recommendations),
                    "filtered_count": len(filtered_recommendations),
                    "final_count": len(diversified_recommendations)
                }
            }

        except Exception as e:
            print(f"❌ 个性化推荐失败: {e}")
            return {"error": str(e)}
        finally:
            db.close()

    def _get_or_update_user_preferences(self, user_id: int, user: User) -> Dict[str, Any]:
        """获取或更新用户偏好"""

        # 检查是否需要更新偏好分析
        should_update = False

        if not user.preference_profile:
            should_update = True
            print(" 首次分析用户偏好")
        elif user.last_model_update:
            days_since_update = (datetime.utcnow() - user.last_model_update).days
            if days_since_update >= 7:  # 每周更新一次
                should_update = True
                print(f" 偏好数据已过期 ({days_since_update} 天)，重新分析")

        if should_update and user.total_interactions >= 3:
            preferences = self.behavior_service.analyze_user_preferences(user_id)
        else:
            preferences = user.preference_profile_dict if user.preference_profile else {}

        return preferences if preferences else self.behavior_service._get_default_preferences()

    def _generate_multi_algorithm_recommendations(self,
                                                  user_id: int,
                                                  preferences: Dict,
                                                  query: str,
                                                  strategy: Dict,
                                                  limit: int,
                                                  excluded_movie_ids: set = None) -> List[Dict]:
        """多算法融合推荐"""
        all_recommendations = []

        # 1. 基于内容的推荐
        content_recs = self._get_content_based_recommendations(user_id, preferences, query, limit)
        for rec in content_recs:
            rec['algorithm'] = 'content_based'
            rec['algorithm_weight'] = self.algorithm_weights['content_based']
        all_recommendations.extend(content_recs)

        # 2. 向量搜索推荐（无查询时使用用户偏好构建搜索文本）
        if query:
            vector_recs = self._get_vector_search_recommendations(preferences, query, limit)
        else:
            top_genres = preferences.get("preferences", {}).get("genres", {})
            sorted_genres = sorted(top_genres.items(), key=lambda x: x[1], reverse=True)[:3]
            implicit_query = " ".join([g for g, s in sorted_genres if s > 0.5]) if sorted_genres else ""
            if implicit_query:
                vector_recs = self._get_vector_search_recommendations(preferences, implicit_query, limit)
            else:
                vector_recs = []
        for rec in vector_recs:
            rec['algorithm'] = 'vector_search'
            rec['algorithm_weight'] = self.algorithm_weights['vector_search']
        all_recommendations.extend(vector_recs)

        # 3. 协同过滤推荐（基于相似用户，含随机化）
        collaborative_recs = self._get_collaborative_recommendations(user_id, preferences, limit)
        for rec in collaborative_recs:
            rec['algorithm'] = 'collaborative'
            rec['algorithm_weight'] = self.algorithm_weights['collaborative']
        all_recommendations.extend(collaborative_recs)

        # 合并和去重（含排除已交互电影 + 标题相似去重）
        unique_recommendations = self._merge_and_deduplicate(all_recommendations, excluded_movie_ids)

        print(
            f" 多算法推荐: 内容{len(content_recs)}, 向量{len(vector_recs)}, 协同{len(collaborative_recs)}")

        return unique_recommendations

    def _get_content_based_recommendations(self, user_id: int, preferences: Dict, query: str, limit: int) -> List[Dict]:
        """基于内容的推荐"""
        db = SessionLocal()
        try:
            genre_prefs = preferences.get("preferences", {}).get("genres", {})
            rating_prefs = preferences.get("preferences", {}).get("ratings", {})

            # 构建查询
            base_query = db.query(Movie).filter(Movie.rating.isnot(None))

            # 应用质量阈值
            min_rating = rating_prefs.get("min_acceptable", 6.0)
            base_query = base_query.filter(Movie.rating >= min_rating)

            # 如果有查询，分析查询中的类型偏好（兼顾用户偏好和查询意图）
            query_genres = []
            if query:
                try:
                    analysis = langchain_service.analyze_user_query(query)
                    query_genres = analysis.get('genres', [])
                except Exception:
                    pass

            # 类型偏好过滤：优先使用查询类型，其次使用用户偏好
            from sqlalchemy import or_
            genre_filters = []
            if query_genres:
                for genre in query_genres:
                    genre_filters.append(Movie.genres.contains(genre))
            elif genre_prefs:
                for genre, score in genre_prefs.items():
                    if score > 0.5:
                        genre_filters.append(Movie.genres.contains(genre))

            if genre_filters:
                base_query = base_query.filter(or_(*genre_filters))

            # 获取候选电影（随机化以增加刷新多样性）
            from sqlalchemy import func
            candidates = base_query.order_by(func.random()).limit(limit * 3).all()

            # 计算个性化得分
            recommendations = []
            for movie in candidates:
                score = self._calculate_personalized_score(movie, preferences)
                # Boost score for query genre match
                if query_genres:
                    movie_genres = movie.genres_list
                    for qg in query_genres:
                        if qg in movie_genres:
                            score += 0.15  # Boost per matching query genre

                rec = movie.to_dict()
                rec['personalized_score'] = min(score, 1.0)
                rec['explanation'] = f"根据您对{movie.genres}的偏好推荐"
                recommendations.append(rec)

            # 按个性化得分排序
            recommendations.sort(key=lambda x: x['personalized_score'], reverse=True)

            return recommendations[:limit]

        except Exception as e:
            print(f"❌ 基于内容推荐失败: {e}")
            return []
        finally:
            db.close()

    def _get_vector_search_recommendations(self, preferences: Dict, query: str, limit: int) -> List[Dict]:
        """向量搜索推荐"""
        try:
            # 增强查询
            enhanced_query = self._enhance_query_with_preferences(query, preferences)

            # 执行向量搜索（获取更多候选以提高多样性）
            vector_results = vector_service.semantic_search(enhanced_query, limit * 3)

            recommendations = []
            for result in vector_results:
                # 获取完整电影信息
                db = SessionLocal()
                try:
                    movie = db.query(Movie).filter(Movie.movie_id == result['movie_id']).first()
                    if movie:
                        rec = movie.to_dict()
                        rec['similarity_score'] = result['similarity_score']
                        rec['explanation'] = f"语义匹配您的查询：{query}"
                        recommendations.append(rec)
                finally:
                    db.close()

            return recommendations[:limit]

        except Exception as e:
            print(f"❌ 向量搜索推荐失败: {e}")
            return []

    def _get_langchain_recommendations(self, query: str, preferences: Dict, limit: int) -> List[Dict]:
        """LangChain增强推荐"""
        try:
            # 使用基础推荐服务的LangChain功能
            result = self.base_service.get_recommendations_by_query(query, limit)

            if 'error' in result:
                return []

            recommendations = result.get('recommendations', [])

            # 添加LangChain特有的解释
            for rec in recommendations:
                if not rec.get('explanation'):
                    rec['explanation'] = rec.get('reason', '基于智能分析推荐')

            return recommendations

        except Exception as e:
            print(f"❌ LangChain推荐失败: {e}")
            return []

    def _get_collaborative_recommendations(self, user_id: int, preferences: Dict, limit: int) -> List[Dict]:
        """协同过滤推荐（基于真实用户交互）"""
        db = SessionLocal()
        try:
            from ..models.user import UserInteraction
            from sqlalchemy import func

            # 寻找相似用户（基于类型偏好）
            user_genres = preferences.get("preferences", {}).get("genres", {})
            if not user_genres:
                return []

            # 获取其他用户的偏好
            other_users = db.query(User).filter(
                User.id != user_id,
                User.genre_preferences.isnot(None)
            ).limit(30).all()

            similar_users = []
            for other_user in other_users:
                other_genres = other_user.genre_preferences_dict
                if other_genres:
                    similarity = self._calculate_user_similarity(user_genres, other_genres)
                    if similarity > 0.3:
                        similar_users.append((other_user.id, similarity))

            if not similar_users:
                # Fallback: diverse random sample
                return self._get_diverse_random_recommendations(db, limit)

            # Sort by similarity, take top 5 similar users
            similar_users.sort(key=lambda x: x[1], reverse=True)
            similar_user_ids = [uid for uid, _ in similar_users[:5]]

            # Get movies liked by similar users (real collaborative signal)
            collab_movie_ids = db.query(UserInteraction.movie_id).filter(
                UserInteraction.user_id.in_(similar_user_ids),
                UserInteraction.interaction_type.in_(['like', 'view']),
                UserInteraction.movie_id != ''
            ).distinct().all()
            collab_movie_ids = {row[0] for row in collab_movie_ids if row[0]}

            if collab_movie_ids:
                # Get full movie data for collaborative candidates, sorted randomly
                collab_movies = db.query(Movie).filter(
                    Movie.movie_id.in_(collab_movie_ids),
                    Movie.rating >= 6.0
                ).order_by(func.random()).limit(limit * 3).all()

                recommendations = []
                for movie in collab_movies:
                    rec = movie.to_dict()
                    rec['explanation'] = "相似用户也喜欢这部电影"
                    recommendations.append(rec)

                return recommendations[:limit]

            # No collaborative data, fallback to diverse random
            return self._get_diverse_random_recommendations(db, limit)

        except Exception as e:
            print(f"❌ 协同过滤推荐失败: {e}")
            return []
        finally:
            db.close()

    def _get_diverse_random_recommendations(self, db, limit: int) -> List[Dict]:
        """获取多样化的随机推荐（含去重和类型多样性）"""
        from sqlalchemy import func
        # Get more candidates with random ordering
        candidates = db.query(Movie).filter(
            Movie.rating >= 6.0
        ).order_by(func.random()).limit(limit * 4).all()

        # Apply genre diversity: max 2 per main genre
        seen_genres = {}
        recommendations = []
        for movie in candidates:
            main_genre = (movie.genres or '').split(',')[0].strip()
            if seen_genres.get(main_genre, 0) >= 2:
                continue
            seen_genres[main_genre] = seen_genres.get(main_genre, 0) + 1
            rec = movie.to_dict()
            rec['explanation'] = "发现冷门好片"
            recommendations.append(rec)
            if len(recommendations) >= limit:
                break

        return recommendations

    def _calculate_personalized_score(self, movie: Movie, preferences: Dict) -> float:
        """计算个性化得分 - 含新颖度"""
        score = 0.0

        # 基础评分权重 (大幅降低以增加长尾分布)
        if movie.rating:
            score += (movie.rating / 10.0) * 0.15

        # 类型匹配得分
        genre_prefs = preferences.get("preferences", {}).get("genres", {})
        if genre_prefs and movie.genres:
            movie_genres = movie.genres_list
            genre_score = 0.0
            for genre in movie_genres:
                genre_score += genre_prefs.get(genre, 0)

            if movie_genres:
                genre_score = genre_score / len(movie_genres)
            score += genre_score * 0.35

        # 导演匹配得分
        director_prefs = preferences.get("preferences", {}).get("directors", {})
        if director_prefs and movie.directors:
            movie_directors = [d.strip() for d in movie.directors.split(',')]
            director_score = 0.0
            for director in movie_directors:
                director_score += director_prefs.get(director, 0)

            if movie_directors:
                director_score = director_score / len(movie_directors)
            score += director_score * 0.15

        # 新颖度加分（增强以促进长尾分布）
        total_ratings = movie.total_ratings or 0
        if total_ratings > 0:
            if movie.rating and movie.rating >= 6.5 and total_ratings < 100000:
                # 冷门电影加分（降低评分门槛，提升上限）
                novelty_bonus = min(0.20, (100000 - total_ratings) / 100000 * 0.20)
                score += novelty_bonus
            elif total_ratings >= 1000 and total_ratings < 50000:
                # 中等冷门电影加分
                score += 0.05

        # 时间新颖度：近期电影微加分
        if movie.release_date:
            import re
            year_match = re.search(r'(\d{4})', movie.release_date)
            if year_match:
                year = int(year_match.group(1))
                if year >= 2023:
                    score += 0.05
                elif year >= 2020:
                    score += 0.02

        return min(score, 1.0)

    def _calculate_user_similarity(self, user1_genres: Dict, user2_genres: Dict) -> float:
        """计算用户相似度"""
        if not user1_genres or not user2_genres:
            return 0.0

        # 计算余弦相似度
        common_genres = set(user1_genres.keys()) & set(user2_genres.keys())
        if not common_genres:
            return 0.0

        dot_product = sum(user1_genres[genre] * user2_genres[genre] for genre in common_genres)

        norm1 = sum(score ** 2 for score in user1_genres.values()) ** 0.5
        norm2 = sum(score ** 2 for score in user2_genres.values()) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _merge_and_deduplicate(self, recommendations: List[Dict], excluded_movie_ids: set = None) -> List[Dict]:
        """合并和去重推荐结果（含排除已交互电影 + 标题相似去重）"""
        if excluded_movie_ids is None:
            excluded_movie_ids = set()

        movie_scores = {}
        movie_data = {}

        for rec in recommendations:
            movie_id = rec.get('movie_id')
            if not movie_id:
                continue

            # 排除已交互的电影
            if movie_id in excluded_movie_ids:
                continue

            # 计算综合得分（含新颖度）
            algo_weight = rec.get('algorithm_weight', 0.25)
            personalized_score = rec.get('personalized_score', 0.5)
            similarity_score = rec.get('similarity_score', 0.5)
            base_rating = (rec.get('rating', 7.0) / 10.0)

            # 新颖度因子：冷门电影额外加分（降低门槛）
            novelty_bonus = 0.0
            if rec.get('total_ratings', 0) < 50000 and rec.get('rating', 0) >= 6.5:
                novelty_bonus = 0.06

            combined_score = (
                    personalized_score * algo_weight * 0.30 +
                    similarity_score * 0.20 +
                    base_rating * 0.15 +
                    novelty_bonus * 0.30
            )

            # 如果已存在，取更高得分
            if movie_id in movie_scores:
                if combined_score > movie_scores[movie_id]:
                    movie_scores[movie_id] = combined_score
                    movie_data[movie_id] = rec
            else:
                movie_scores[movie_id] = combined_score
                movie_data[movie_id] = rec

        # 按得分排序
        sorted_movies = sorted(movie_scores.items(), key=lambda x: x[1], reverse=True)

        # movie_id去重后的结果
        result = []
        for movie_id, score in sorted_movies:
            rec = movie_data[movie_id].copy()
            rec['final_score'] = round(score, 3)
            result.append(rec)

        # 内容相似标题去重：相同前4字标题只保留得分最高的
        title_groups = {}
        for rec in result:
            title_prefix = rec.get('title', '')[:4]
            if title_prefix:
                if title_prefix not in title_groups:
                    title_groups[title_prefix] = []
                title_groups[title_prefix].append(rec)

        content_filtered = []
        for title_prefix, recs in title_groups.items():
            if len(recs) == 1:
                content_filtered.append(recs[0])
            else:
                # 保留得分最高的，其余降级随机混入末尾
                recs.sort(key=lambda x: x.get('final_score', 0), reverse=True)
                content_filtered.append(recs[0])

        # 按得分重新排序
        content_filtered.sort(key=lambda x: x.get('final_score', 0), reverse=True)

        return content_filtered

    def _apply_personalized_filters(self, recommendations: List[Dict], preferences: Dict, strategy: Dict) -> List[Dict]:
        """应用个性化过滤 - 排除已交互电影，探索率控制"""
        filtered = []

        quality_threshold = strategy.get("quality_threshold", 6.5)
        rating_prefs = preferences.get("preferences", {}).get("ratings", {})
        exploration_rate = strategy.get("exploration_rate", 0.35)

        for rec in recommendations:
            # 质量过滤
            if rec.get('rating', 0) < quality_threshold:
                continue

            # 评分范围过滤（但exploration_rate概率允许通过高分/低分）
            ideal_range = rating_prefs.get("ideal_range", [6.0, 10.0])
            in_range = ideal_range[0] <= rec.get('rating', 7.0) <= ideal_range[1]
            if not in_range:
                if np.random.random() > exploration_rate:
                    continue

            # 探索率：随机允许一些不在理想范围的电影通过
            if np.random.random() < exploration_rate * 0.3:
                filtered.append(rec)
                continue

            filtered.append(rec)

        return filtered

    def _add_diversity(self, recommendations: List[Dict], preferences: Dict, diversity_level: str) -> List[Dict]:
        """添加推荐多样性"""
        if diversity_level == "low":
            return recommendations  # 不添加多样性

        diversified = []
        used_genres = set()
        used_directors = set()

        # 多样性参数
        if diversity_level == "high":
            max_same_genre = 2
            max_same_director = 1
        else:  # medium
            max_same_genre = 3
            max_same_director = 2

        genre_counts = {}
        director_counts = {}

        for rec in recommendations:
            movie_genres = rec.get('genres', '').split(', ') if rec.get('genres') else []
            movie_directors = rec.get('directors', '').split(', ') if rec.get('directors') else []

            # 检查类型多样性
            genre_ok = True
            for genre in movie_genres[:2]:  # 只检查前2个类型
                if genre_counts.get(genre, 0) >= max_same_genre:
                    genre_ok = False
                    break

            # 检查导演多样性
            director_ok = True
            for director in movie_directors[:1]:  # 只检查第一个导演
                if director_counts.get(director, 0) >= max_same_director:
                    director_ok = False
                    break

            if genre_ok and director_ok:
                diversified.append(rec)

                # 更新计数
                for genre in movie_genres[:2]:
                    genre_counts[genre] = genre_counts.get(genre, 0) + 1
                for director in movie_directors[:1]:
                    director_counts[director] = director_counts.get(director, 0) + 1

        # 如果多样性过滤导致结果不足，补充高质量推荐
        if len(diversified) < len(recommendations):
            remaining = [r for r in recommendations if r not in diversified]
            remaining.sort(key=lambda x: x.get('final_score', 0), reverse=True)
            diversified.extend(remaining[:len(recommendations) - len(diversified)])

        return diversified

    def _enhance_query_with_preferences(self, query: str, preferences: Dict) -> str:
        """基于用户偏好增强查询（仅补充相关偏好，避免稀释查询意图）"""
        enhanced_parts = [query]

        # 分析查询是否已包含明确的类型/风格关键词
        query_has_genre = False
        genre_keywords = ['科幻', '喜剧', '动作', '爱情', '悬疑', '恐怖', '剧情', '动画', '战争', '纪录片']
        for kw in genre_keywords:
            if kw in query:
                query_has_genre = True
                break

        # 仅当查询没有明确类型时，才添加用户偏好类型
        if not query_has_genre:
            genre_prefs = preferences.get("preferences", {}).get("genres", {})
            top_genres = sorted(genre_prefs.items(), key=lambda x: x[1], reverse=True)[:2]
            for genre, score in top_genres:
                if score > 0.7:
                    enhanced_parts.append(genre)

        # 导演偏好仅在无明确查询类型时添加
        if not query_has_genre:
            director_prefs = preferences.get("preferences", {}).get("directors", {})
            top_directors = sorted(director_prefs.items(), key=lambda x: x[1], reverse=True)[:1]
            for director, score in top_directors:
                if score > 0.7:
                    enhanced_parts.append(director)

        # 评分偏好始终添加（不影响语义方向）
        rating_prefs = preferences.get("preferences", {}).get("ratings", {})
        avg_rating = rating_prefs.get("avg_rating", 7.0)
        if avg_rating >= 8.0:
            enhanced_parts.append("高分经典")

        return " ".join(enhanced_parts)

    def _generate_recommendation_explanations(self, recommendations: List[Dict], preferences: Dict, query: str) -> Dict[
        str, str]:
        """生成推荐解释"""
        explanations = {}

        for rec in recommendations:
            movie_id = rec.get('movie_id')
            if not movie_id:
                continue

            explanation_parts = []

            # 基于算法的解释
            algorithm = rec.get('algorithm', '')
            if algorithm == 'content_based':
                explanation_parts.append("基于您的观影偏好")
            elif algorithm == 'collaborative':
                explanation_parts.append("相似用户也喜欢")
            elif algorithm == 'vector_search':
                explanation_parts.append("语义匹配您的需求")
            elif algorithm == 'langchain':
                explanation_parts.append("AI智能分析推荐")

            # 基于得分的解释
            final_score = rec.get('final_score', 0)
            if final_score > 0.8:
                explanation_parts.append("高度匹配")
            elif final_score > 0.6:
                explanation_parts.append("较好匹配")

            # 基于电影属性的解释
            if rec.get('rating', 0) >= 9.0:
                explanation_parts.append("经典佳作")
            elif rec.get('rating', 0) >= 8.5:
                explanation_parts.append("高分好片")

            explanations[movie_id] = "，".join(explanation_parts) if explanation_parts else "为您推荐"

        return explanations

    def _get_preferences_summary(self, preferences: Dict) -> Dict[str, Any]:
        """获取偏好摘要"""
        prefs = preferences.get("preferences", {})

        return {
            "dominant_genres": preferences.get("dominant_genres", [])[:3],
            "avg_rating_preference": prefs.get("ratings", {}).get("avg_rating", 7.0),
            "overall_sentiment": prefs.get("sentiment", {}).get("overall_sentiment", "neutral"),
            "confidence_score": preferences.get("confidence_score", 0.0),
            "sample_size": preferences.get("sample_size", 0)
        }

    def _enrich_recommendations_with_langchain(self, recommendations: List[Dict],
                                                preferences: Dict, query: str) -> List[Dict]:
        """使用LangChain进行分析增强和相关性过滤"""
        if not query or not langchain_service.available:
            return recommendations

        try:
            analysis = langchain_service.analyze_user_query(query)
            if not analysis:
                return recommendations

            query_genres = analysis.get('genres', [])
            query_keywords = analysis.get('keywords', [])
            excluded_genres = analysis.get('excluded_genres', [])

            enriched = []
            for rec in recommendations:
                # 排除查询中明确不想看的类型
                rec_genres = rec.get('genres', '')
                if excluded_genres:
                    skip = False
                    for eg in excluded_genres:
                        if eg in rec_genres:
                            skip = True
                            break
                    if skip:
                        continue

                # 如果有查询类型，检查相关性
                if query_genres:
                    movie_genres = rec_genres.split(', ') if rec_genres else []
                    genre_match = any(qg in movie_genres for qg in query_genres)
                    if not genre_match:
                        # No genre match, reduce score significantly
                        rec['final_score'] = rec.get('final_score', 0.5) * 0.5

                if not rec.get('explanation') or rec.get('explanation') == '':
                    rec['explanation'] = f"AI分析匹配您的查询：{query}"
                rec['langchain_analysis'] = query_genres
                enriched.append(rec)

            # If filtering removed too many, keep originals
            if len(enriched) < 2 and len(recommendations) > len(enriched):
                return recommendations

            return enriched
        except Exception as e:
            print(f"LangChain enrichment failed: {e}")
            return recommendations

    def _apply_controlled_shuffle(self, recommendations: List[Dict]) -> List[Dict]:
        """受控随机打乱：保留前2在位置，其余随机排列"""
        if len(recommendations) <= 2:
            return recommendations
        top_two = recommendations[:2]
        rest = recommendations[2:]
        random.shuffle(rest)
        return top_two + rest

    def _log_recommendation_event(self, user_id: int, query: str, recommendations: List[Dict], strategy: Dict):
        """记录推荐事件"""
        try:
            # 记录推荐上下文
            context = {
                "strategy": strategy,
                "algorithm_distribution": {},
                "total_recommendations": len(recommendations),
                "query": query
            }

            # 统计算法分布
            for rec in recommendations:
                algo = rec.get('algorithm', 'unknown')
                context["algorithm_distribution"][algo] = context["algorithm_distribution"].get(algo, 0) + 1

            # 记录为搜索交互
            self.behavior_service.record_interaction(
                user_id=user_id,
                movie_id="",  # 推荐事件不针对特定电影
                interaction_type="recommendation_generated",
                recommendation_context=context,
                search_query=query
            )

        except Exception as e:
            print(f"❌ 记录推荐事件失败: {e}")


# 全局自适应推荐服务实例
adaptive_recommendation_service = AdaptiveRecommendationService()