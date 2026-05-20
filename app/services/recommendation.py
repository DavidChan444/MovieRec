"""
电影推荐算法服务 - 集成LangChain和向量搜索
"""
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from ..data.database import SessionLocal
from ..models.movie import Movie
from .langchain_service import langchain_service
from .vector_service import vector_service
from .llm_service import llm_service  # 保留作为降级选项
from .data_preprocessor import data_preprocessor
from .user_behavior_service import user_behavior_service


class RecommendationService:
    def __init__(self):
        self.use_langchain = True  # 控制是否使用LangChain
        self.use_vector_search = True  # 控制是否使用向量搜索

    def get_recommendations_by_query(self, query: str, limit: int = 10, user_id: int = None) -> Dict[str, Any]:
        """基于用户查询获取推荐 - 使用LangChain和向量搜索增强"""
        db = SessionLocal()
        try:
            # 使用LangChain分析用户查询
            if self.use_langchain:
                try:
                    analysis = langchain_service.analyze_user_query(query)
                    print(f"🚀 LangChain分析结果: {analysis}")
                except Exception as e:
                    print(f"⚠️ LangChain分析失败，降级到简单分析: {e}")
                    analysis = llm_service.analyze_user_query(query)
            else:
                analysis = llm_service.analyze_user_query(query)

            # 获取推荐候选
            candidates = self._get_recommendation_candidates(db, analysis, query, limit)
            # ✅ 添加调试
            print(f"📊 候选数量: {len(candidates)}")
            if candidates:
                print(f"📊 第一个候选: {candidates[0]}")

            # 加载用户偏好画像（如果有user_id）
            user_preferences = None
            user_profile_text = ""
            excluded_movie_ids = set()
            if user_id:
                try:
                    user_prefs = user_behavior_service.analyze_user_preferences(user_id)
                    user_preferences = user_prefs.get("preferences", {})
                    genre_keys = list(user_preferences.get("genres", {}).keys())[:3] if user_preferences.get("genres") else []
                    disliked_genres = user_preferences.get("disliked_genres", [])
                    user_profile_text = data_preprocessor.user_profile_to_prompt({
                        "preferences": {
                            "liked_genres": genre_keys,
                            "disliked_genres": disliked_genres,
                            "average_rating": user_preferences.get("ratings", {}).get("avg_rating", 7.0)
                        }
                    })
                    # Get excluded movie IDs (previously interacted)
                    excluded_movie_ids = user_behavior_service.get_interacted_movie_ids(user_id)
                    print(f"👤 加载用户 {user_id} 偏好画像, 已交互 {len(excluded_movie_ids)} 部电影")
                except Exception as e:
                    print(f"⚠️ 加载用户偏好失败: {e}")

            # 生成推荐理由和得分
            recommendations = []
            for candidate in candidates:
                movie_id = candidate.get('movie_id')

                # 跳过已交互的电影（提高新颖度）
                if movie_id and movie_id in excluded_movie_ids:
                    continue

                print(f"🔍 处理候选电影: {movie_id}")

                movie = self._get_movie_by_id(db, candidate.get('movie_id'))
                if not movie:
                    continue

                # 生成推荐理由
                movie_dict = movie.to_dict()
                # 使用 preprocessor 丰富电影信息
                movie_prompt = data_preprocessor.movie_to_prompt(movie_dict, 'rich')
                # 构建包含用户偏好的上下文
                reason_context = query
                if user_profile_text:
                    reason_context = f"{user_profile_text}\n用户需求：{query}"

                if self.use_langchain:
                    try:
                        reason = langchain_service.generate_recommendation_reason(
                            movie_dict, reason_context, analysis
                        )
                    except Exception as e:
                        print(f"⚠️ LangChain推荐理由生成失败，使用降级方法: {e}")
                        reason = llm_service.generate_recommendation_reason(
                            movie_dict, reason_context
                        )
                else:
                    reason = llm_service.generate_recommendation_reason(
                        movie_dict, reason_context
                    )

                # 计算综合得分（含个性化加权）
                match_score = self._calculate_enhanced_match_score(
                    movie, analysis, candidate, user_preferences
                )

                recommendations.append({
                    **movie.to_dict(),
                    'reason': reason,
                    'match_score': match_score,
                    'vector_similarity': candidate.get('similarity_score', 0),
                    'search_method': candidate.get('search_method', 'database')
                })

            # 按得分排序
            recommendations.sort(key=lambda x: x['match_score'], reverse=True)

            # 生成总结
            summary = ""
            if self.use_langchain and recommendations:
                try:
                    summary = langchain_service.generate_movie_summary(recommendations, query)
                except Exception as e:
                    print(f"⚠️ 总结生成失败: {e}")

            return {
                'query': query,
                'analysis': analysis,
                'recommendations': recommendations[:limit],
                'total': len(recommendations),
                'summary': summary,
                'search_methods_used': self._get_search_methods_stats(recommendations)
            }

        except Exception as e:
            print(f"推荐生成失败: {e}")
            return {'error': str(e)}
        finally:
            db.close()

    def _get_recommendation_candidates(self, db: Session, analysis: Dict, query: str, limit: int) -> List[Dict]:
        """获取推荐候选 - 结合多种搜索方法"""
        all_candidates = []

        # 1. 向量搜索（优先级最高）
        if self.use_vector_search:
            try:
                vector_candidates = vector_service.hybrid_search(query, analysis, limit * 2)
                for candidate in vector_candidates:
                    candidate['search_method'] = 'vector_search'
                    candidate['priority'] = 1
                all_candidates.extend(vector_candidates)
                print(f"🎯 向量搜索找到 {len(vector_candidates)} 个候选")
            except Exception as e:
                print(f"⚠️ 向量搜索失败: {e}")

        # 2. 传统数据库搜索（补充）
        if len(all_candidates) < limit:
            needed = limit - len(all_candidates)
            db_candidates = self._search_movies_by_analysis(db, analysis, max(needed * 2, limit))

            # 排除已有的候选
            existing_ids = {c.get('movie_id') for c in all_candidates}

            for movie in db_candidates:
                if str(movie.movie_id) not in existing_ids:
                    candidate = {
                        'movie_id': str(movie.movie_id),
                        'title': movie.title,
                        'rating': movie.rating,
                        'search_method': 'database_search',
                        'priority': 2,
                        'similarity_score': 0.5  # 默认相似度
                    }
                    all_candidates.append(candidate)

                    if len(all_candidates) >= limit * 1.5:  # 获取足够的候选
                        break

            print(f"📚 数据库搜索补充 {len(all_candidates) - len(vector_candidates)} 个候选")

        # 3. 按优先级和得分排序
        all_candidates.sort(key=lambda x: (x.get('priority', 3), -x.get('similarity_score', 0)))

        return all_candidates[:limit * 2]  # 返回更多候选用于后续筛选

    def _search_movies_by_analysis(self, db: Session, analysis: Dict, limit: int) -> List[Movie]:
        """传统数据库搜索方法（保持原有逻辑）"""
        base_query = db.query(Movie).filter(Movie.rating.isnot(None))

        # 类型过滤
        genres = analysis.get('genres', [])

        # 排除用户不想要的类型
        excluded_genres = analysis.get('excluded_genres', [])
        if excluded_genres:
            for eg in excluded_genres:
                base_query = base_query.filter(~Movie.genres.contains(eg))

        # 评分偏好处理
        rating_preference = analysis.get('rating_preference', '')
        if rating_preference in ['高分', '高分|经典']:
            base_query = base_query.filter(Movie.rating >= 8.5)
        elif rating_preference == '经典':
            base_query = base_query.filter(Movie.rating >= 9.0)

        if genres:
            type_query = base_query
            from sqlalchemy import or_
            genre_filters = []

            for genre in genres:
                genre_filters.append(Movie.genres.contains(genre))
                # 添加相关类型
                related_genres = self._get_related_genres(genre)
                for related in related_genres:
                    if related != genre:
                        genre_filters.append(Movie.genres.contains(related))

            if genre_filters:
                type_query = type_query.filter(or_(*genre_filters))

                # 根据心情调整排序
                mood = analysis.get('mood', '')
                if '轻松' in mood or '搞笑' in mood:
                    type_movies = type_query.filter(
                        Movie.rating >= 6.5
                    ).order_by(
                        Movie.rating.desc(),
                        Movie.total_ratings.desc()
                    ).limit(limit).all()
                else:
                    type_movies = type_query.order_by(
                        Movie.rating.desc(),
                        Movie.total_ratings.desc()
                    ).limit(limit).all()

                if type_movies:
                    return type_movies

        # 降级到电影（降低门槛以增加长尾）
        fallback_movies = base_query.filter(
            Movie.rating >= 6.5
        ).order_by(Movie.rating.desc()).limit(limit).all()

        return fallback_movies

    def _get_movie_by_id(self, db: Session, movie_id: str) -> Optional[Movie]:
        """根据豆瓣movie_id获取电影"""
        try:
            movie_id_str = str(movie_id).strip()
            print(f"[SEARCH] Looking up movie by movie_id: {movie_id_str}")
            movie = db.query(Movie).filter(Movie.movie_id == movie_id_str).first()

            if movie:
                print(f"[OK] Found movie: {movie.title}")
            else:
                print(f"[WARN] Movie not found by movie_id: {movie_id_str}")

            return movie
        except Exception as e:
            print(f"[ERROR] Lookup failed for movie_id {movie_id}: {e}")
            return None

    def _calculate_enhanced_match_score(self, movie: Movie, analysis: Dict, candidate: Dict, user_preferences: Dict = None) -> float:
        """计算增强的匹配得分 - 含新颖度"""
        score = 0.0

        # 基础评分权重 (大幅降低以促进长尾分布)
        if movie.rating:
            score += (movie.rating / 10.0) * 0.10

        # 向量相似度权重
        vector_similarity = candidate.get('similarity_score', 0)
        if vector_similarity > 0:
            score += vector_similarity * 0.30

        # 类型匹配
        movie_genres = movie.genres_list if movie.genres_list else []
        query_genres = analysis.get('genres', [])

        if query_genres:
            exact_matches = len(set(movie_genres) & set(query_genres))
            genre_score = exact_matches / len(query_genres)
            score += genre_score * 0.20

        # 用户偏好类型匹配
        if user_preferences:
            user_genres = user_preferences.get("genres", {})
            if user_genres and movie_genres:
                genre_pref_score = 0.0
                for genre in movie_genres:
                    genre_pref_score += user_genres.get(genre, 0)
                if movie_genres:
                    genre_pref_score = genre_pref_score / len(movie_genres)
                score += genre_pref_score * 0.15

        # 关键词匹配
        keywords = analysis.get('keywords', [])
        if keywords:
            title_lower = (movie.title or '').lower()
            keyword_matches = sum(1 for kw in keywords if kw.lower() in title_lower)
            if keywords:
                keyword_score = keyword_matches / len(keywords)
                score += keyword_score * 0.08

        # 标签匹配
        movie_tags = movie.tags_list if hasattr(movie, 'tags_list') else []
        if movie_tags and keywords:
            tag_matches = 0
            for kw in keywords:
                for tag in movie_tags:
                    if kw.lower() in tag.lower() or tag.lower() in kw.lower():
                        tag_matches += 1
                        break
            if keywords:
                tag_score = tag_matches / len(keywords)
                score += tag_score * 0.05

        # 新颖度加分：冷门好片获得额外分数（降低门槛，提升上限）
        total_ratings = movie.total_ratings or 0
        if total_ratings > 0:
            # 冷门电影获得加分（评分门槛从8.0降至6.5）
            if movie.rating and movie.rating >= 6.5 and total_ratings < 100000:
                novelty_bonus = min(0.20, (100000 - total_ratings) / 100000 * 0.20)
                score += novelty_bonus
            # 中等热度电影加分
            elif 1000 <= total_ratings < 50000:
                score += 0.05

        # 搜索方法加权
        search_method = candidate.get('search_method', 'database_search')
        if search_method == 'vector_search':
            score += 0.05

        return min(score, 1.0)

    def _get_search_methods_stats(self, recommendations: List[Dict]) -> Dict:
        """获取搜索方法统计"""
        stats = {}
        for rec in recommendations:
            method = rec.get('search_method', 'unknown')
            stats[method] = stats.get(method, 0) + 1
        return stats

    def get_similar_movies_enhanced(self, movie_id: str, limit: int = 10) -> List[Dict]:
        """增强的相似电影推荐 - 含多样性保障"""
        try:
            # 优先使用向量搜索
            if self.use_vector_search:
                vector_results = vector_service.find_similar_movies(movie_id, limit * 2)
                if vector_results:
                    db = SessionLocal()
                    try:
                        enhanced_results = []
                        seen_genres = {}
                        seen_directors = {}

                        for result in vector_results:
                            movie = self._get_movie_by_id(db, result['movie_id'])
                            if not movie:
                                continue

                            # 多样性检查：限制同类型和同导演数量
                            genres_str = movie.genres or ''
                            directors_str = movie.directors or ''
                            main_genre = genres_str.split(',')[0].strip() if genres_str else ''
                            main_director = directors_str.split(',')[0].strip() if directors_str else ''

                            if seen_genres.get(main_genre, 0) >= 3:
                                continue
                            if seen_directors.get(main_director, 0) >= 2:
                                continue

                            seen_genres[main_genre] = seen_genres.get(main_genre, 0) + 1
                            seen_directors[main_director] = seen_directors.get(main_director, 0) + 1

                            enhanced_results.append({
                                **movie.to_dict(),
                                'similarity_score': result['similarity_score'],
                                'search_method': 'vector_similarity'
                            })

                            if len(enhanced_results) >= limit:
                                break

                        # 如果多样性过滤后不够，补充非重复的结果
                        if len(enhanced_results) < limit:
                            existing_ids = {r['id'] for r in enhanced_results}
                            for result in vector_results:
                                if len(enhanced_results) >= limit:
                                    break
                                movie = self._get_movie_by_id(db, result['movie_id'])
                                if movie and movie.to_dict()['id'] not in existing_ids:
                                    enhanced_results.append({
                                        **movie.to_dict(),
                                        'similarity_score': result['similarity_score'],
                                        'search_method': 'vector_similarity'
                                    })

                        return enhanced_results[:limit]
                    finally:
                        db.close()

            return self.get_similar_movies(movie_id, limit)

        except Exception as e:
            print(f"增强相似电影推荐失败: {e}")
            return self.get_similar_movies(movie_id, limit)

    # 保持原有方法以确保兼容性
    def _get_related_genres(self, genre: str) -> List[str]:
        """获取相关类型"""
        related_map = {
            '喜剧': ['喜剧', '轻喜剧'],
            '科幻': ['科幻', '奇幻'],
            '爱情': ['爱情', '浪漫'],
            '动作': ['动作', '冒险'],
            '恐怖': ['恐怖', '惊悚'],
            '悬疑': ['悬疑', '犯罪'],
            '动画': ['动画', '家庭', '奇幻'],
            '战争': ['战争', '历史'],
            '纪录片': ['纪录片'],
            '剧情': ['剧情']
        }
        return related_map.get(genre, [genre])

    def get_similar_movies(self, movie_id: str, limit: int = 10) -> List[Dict]:
        """获取相似电影 - 含随机多样性"""
        db = SessionLocal()
        try:
            target_movie = db.query(Movie).filter(Movie.movie_id == movie_id).first()
            if not target_movie:
                return []

            similar_query = db.query(Movie).filter(
                Movie.movie_id != movie_id,
                Movie.rating.isnot(None)
            )

            if target_movie.genres:
                target_genres = target_movie.genres_list
                if target_genres:
                    from sqlalchemy import or_, func
                    genre_filters = []
                    for genre in target_genres[:2]:
                        genre_filters.append(Movie.genres.contains(genre))
                    if genre_filters:
                        similar_query = similar_query.filter(or_(*genre_filters))

            # Rating range with wider tolerance for more diversity
            if target_movie.rating:
                rating_range = 1.5
                similar_query = similar_query.filter(
                    Movie.rating.between(
                        max(0, (target_movie.rating or 7.0) - rating_range),
                        min(10, (target_movie.rating or 7.0) + rating_range)
                    )
                )

            # Use random ordering for diversity, then take top by rating
            from sqlalchemy import func
            candidates = similar_query.order_by(func.random()).limit(limit * 3).all()
            candidates.sort(key=lambda m: m.rating or 0, reverse=True)

            # Apply genre diversity
            seen_genres = {}
            result = []
            for movie in candidates:
                main_genre = (movie.genres or '').split(',')[0].strip()
                if seen_genres.get(main_genre, 0) >= 3:
                    continue
                seen_genres[main_genre] = seen_genres.get(main_genre, 0) + 1
                result.append(movie.to_dict())
                if len(result) >= limit:
                    break

            return result[:limit]

        except Exception as e:
            print(f"获取相似电影失败: {e}")
            return []
        finally:
            db.close()

    def get_trending_movies(self, limit: int = 20) -> List[Dict]:
        """获取热门电影（含随机化以支持刷新多样性）"""
        db = SessionLocal()
        try:
            from sqlalchemy import func
            # Fetch a larger pool then randomly sample for refresh variety
            pool = db.query(Movie).filter(
                Movie.rating >= 7.0,
                Movie.total_ratings >= 1000
            ).order_by(
                Movie.total_ratings.desc(),
                Movie.rating.desc()
            ).limit(limit * 3).all()

            if len(pool) <= limit:
                return [movie.to_dict() for movie in pool]

            # Randomly select from the top pool for variety on refresh
            import random
            sampled = random.sample(pool, limit)
            # Sort sampled by rating for consistent quality display
            sampled.sort(key=lambda m: m.rating or 0, reverse=True)
            return [movie.to_dict() for movie in sampled]

        except Exception as e:
            print(f"获取热门电影失败: {e}")
            return []
        finally:
            db.close()

    def search_movies_advanced(self,
                               title: str = None,
                               genres: List[str] = None,
                               year_start: int = None,
                               year_end: int = None,
                               min_rating: float = None,
                               max_rating: float = None,
                               limit: int = 20) -> List[Dict]:
        """高级搜索"""
        db = SessionLocal()
        try:
            query = db.query(Movie)

            if title:
                query = query.filter(Movie.title.contains(title))

            if genres:
                from sqlalchemy import or_
                genre_filters = []
                for genre in genres:
                    genre_filters.append(Movie.genres.contains(genre))
                if genre_filters:
                    query = query.filter(or_(*genre_filters))

            if year_start:
                query = query.filter(Movie.release_date.contains(str(year_start)))
            if year_end and year_start and year_end != year_start:
                from sqlalchemy import or_
                year_conditions = []
                for year in range(year_start, year_end + 1):
                    year_conditions.append(Movie.release_date.contains(str(year)))
                if year_conditions:
                    query = query.filter(or_(*year_conditions))

            if min_rating:
                query = query.filter(Movie.rating >= min_rating)
            if max_rating:
                query = query.filter(Movie.rating <= max_rating)

            movies = query.order_by(Movie.rating.desc()).limit(limit).all()
            return [movie.to_dict() for movie in movies]

        except Exception as e:
            print(f"高级搜索失败: {e}")
            return []
        finally:
            db.close()


# 全局推荐服务实例
recommendation_service = RecommendationService()