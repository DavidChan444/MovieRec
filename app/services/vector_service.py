"""
Chroma向量数据库服务 - 实现语义相似度搜索
"""
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
import json
from ..core.config import settings
from ..data.database import SessionLocal
from ..models.movie import Movie


class VectorService:
    def __init__(self):
        # 初始化Chroma客户端
        self.chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIRECTORY,
            settings=ChromaSettings(anonymized_telemetry=False)
        )

        # 初始化语义编码器
        self.encoder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

        # 获取或创建电影集合
        self.collection_name = "movie_collection"
        self.collection = self._get_or_create_collection()

        print(f"[OK] Vector service initialized, collection: {self.collection_name}")

    def _get_or_create_collection(self):
        """获取或创建电影集合"""
        try:
            collection = self.chroma_client.get_collection(self.collection_name)
            count = collection.count()
            print(f"[OK] Found existing collection: {self.collection_name}, {count} vectors")

            # Check if rebuild is needed (tags field missing in metadata)
            if count > 0:
                sample = collection.get(limit=1, include=["metadatas"])
                if sample['metadatas'] and sample['metadatas'][0]:
                    if 'tags' not in sample['metadatas'][0]:
                        print("[REBUILD] Tags field missing in vector DB, rebuilding...")
                        self.chroma_client.delete_collection(self.collection_name)
                        collection = self.chroma_client.create_collection(
                            name=self.collection_name,
                            metadata={"description": "电影向量数据库", "version": "2.0"}
                        )
                        self.initialize_movie_vectors(force_rebuild=False)
                        print("[OK] Vector DB rebuilt with tag support")
            else:
                # Collection exists but is empty - initialize it
                print(f"[INIT] Collection exists but empty, populating vectors...")
                self.collection = collection
                self.initialize_movie_vectors()

            return collection
        except Exception:
            collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "电影向量数据库", "version": "2.0"}
            )
            print(f"[NEW] Creating collection: {self.collection_name}")
            # Initialize vectors for the new empty collection
            self.collection = collection
            self.initialize_movie_vectors()
            return collection

    def build_movie_text(self, movie: Movie) -> str:
        """构建电影的文本表示用于向量化"""
        parts = []

        # 标题
        if movie.title:
            parts.append(f"电影标题: {movie.title}")

        # 类型
        if movie.genres:
            parts.append(f"电影类型: {movie.genres}")

        # 标签
        if movie.tags:
            parts.append(f"电影标签: {movie.tags[:200]}")

        # 导演
        if movie.directors:
            parts.append(f"导演: {movie.directors}")

        # 演员
        if movie.actors:
            actors = movie.actors[:100]  # 限制长度
            parts.append(f"主演: {actors}")

        # 简介
        if movie.summary:
            summary = movie.summary[:200]  # 限制长度
            parts.append(f"剧情简介: {summary}")

        # 评分信息
        if movie.rating:
            parts.append(f"评分: {movie.rating}分")

        return " | ".join(parts)

    def initialize_movie_vectors(self, force_rebuild: bool = False):
        """初始化电影向量数据库"""
        try:
            current_count = self.collection.count()

            if current_count > 0 and not force_rebuild:
                print(f"[OK] Vector DB already has {current_count} movie vectors, skipping init")
                return True

            if force_rebuild and current_count > 0:
                print("[REBUILD] Force rebuilding vector database...")
                self.chroma_client.delete_collection(self.collection_name)
                self.collection = self._get_or_create_collection()

            # 从数据库获取所有电影
            db = SessionLocal()
            try:
                movies = db.query(Movie).filter(
                    Movie.title.isnot(None),
                    Movie.summary.isnot(None)
                ).limit(1000).all()  # 限制数量避免内存问题

                if not movies:
                    print("[ERROR] No movie data found")
                    return False

                print(f"[...] Starting vectorization of {len(movies)} movies...")

                # 批量处理
                batch_size = 50
                total_processed = 0

                for i in range(0, len(movies), batch_size):
                    batch = movies[i:i + batch_size]
                    self._process_movie_batch(batch)
                    total_processed += len(batch)

                    if total_processed % 100 == 0:
                        print(f"[...] Processed {total_processed}/{len(movies)} movies")

                print(f"[OK] Vectorization complete! Total: {total_processed} movies")
                return True

            finally:
                db.close()

        except Exception as e:
            print(f"[ERROR] Vector DB initialization failed: {e}")
            return False

    def _process_movie_batch(self, movies: List[Movie]):
        """批量处理电影向量化"""
        try:
            texts = []
            metadatas = []
            ids = []

            for movie in movies:
                # 构建文本
                text = self.build_movie_text(movie)
                texts.append(text)

                # 构建元数据
                metadata = {
                    "title": movie.title or "",
                    "genres": movie.genres or "",
                    "directors": movie.directors or "",
                    "rating": float(movie.rating) if movie.rating else 0.0,
                    "year": self._extract_year(movie.release_date),
                    "movie_id": str(movie.movie_id),
                    "tags": movie.tags or ""
                }
                metadatas.append(metadata)

                # ID
                ids.append(f"movie_{movie.movie_id}")

            # 生成向量并添加到集合
            embeddings = self.encoder.encode(texts).tolist()

            self.collection.add(
                embeddings=embeddings,
                metadatas=metadatas,
                documents=texts,
                ids=ids
            )

        except Exception as e:
            print(f"[ERROR] Batch processing failed: {e}")

    def semantic_search(self, query: str, limit: int = 10, filters: Dict = None) -> List[Dict]:
        """语义相似度搜索"""
        try:
            print(f"[SEARCH] Vector search: {query} (limit: {limit})")

            # 编码查询
            query_embedding = self.encoder.encode([query]).tolist()[0]

            # 构建过滤条件
            where_clause = {}
            if filters:
                if filters.get('min_rating'):
                    where_clause["rating"] = {"$gte": float(filters['min_rating'])}
                if filters.get('genres'):
                    # Chroma支持文本包含搜索
                    where_clause["genres"] = {"$contains": filters['genres']}

            # 执行搜索
            search_kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": limit,
                "include": ["metadatas", "documents", "distances"]
            }

            if where_clause:
                search_kwargs["where"] = where_clause

            results = self.collection.query(**search_kwargs)

            # 处理结果
            search_results = []
            if results['metadatas'] and results['metadatas'][0]:
                for i, metadata in enumerate(results['metadatas'][0]):
                    distance = results['distances'][0][i] if results['distances'] else 0

                    # 将欧氏距离转换为相似度 (0~1范围)
                    similarity = 1.0 / (1.0 + distance) if distance >= 0 else 0.0

                    search_results.append({
                        'movie_id': metadata.get('movie_id'),
                        'title': metadata.get('title'),
                        'genres': metadata.get('genres'),
                        'directors': metadata.get('directors'),
                        'rating': metadata.get('rating'),
                        'year': metadata.get('year'),
                        'similarity_score': round(similarity, 4),
                        'document': results['documents'][0][i] if results['documents'] else ""
                    })

            print(f"[OK] Found {len(search_results)} similar results")
            return search_results

        except Exception as e:
            print(f"[ERROR] Vector search failed: {e}")
            return []

    def find_similar_movies(self, movie_id: str, limit: int = 10) -> List[Dict]:
        """查找相似电影"""
        try:
            # 获取目标电影的向量
            target_results = self.collection.get(
                ids=[f"movie_{movie_id}"],
                include=["embeddings", "metadatas"]
            )

            if not target_results['embeddings'] or not target_results['embeddings'][0]:
                print(f"[ERROR] Movie {movie_id} vector not found")
                return []

            target_embedding = target_results['embeddings'][0]

            # 搜索相似电影（排除自身）
            results = self.collection.query(
                query_embeddings=[target_embedding],
                n_results=limit + 1,  # +1 因为会包含自身
                include=["metadatas", "distances"]
            )

            similar_movies = []
            for i, metadata in enumerate(results['metadatas'][0]):
                # 跳过自身
                if metadata.get('movie_id') == movie_id:
                    continue

                distance = results['distances'][0][i]
                similarity = 1.0 / (1.0 + distance) if distance >= 0 else 0.0
                similar_movies.append({
                    'movie_id': metadata.get('movie_id'),
                    'title': metadata.get('title'),
                    'genres': metadata.get('genres'),
                    'rating': metadata.get('rating'),
                    'similarity_score': round(similarity, 4)
                })

                if len(similar_movies) >= limit:
                    break

            return similar_movies

        except Exception as e:
            print(f"[ERROR] Find similar movies failed: {e}")
            return []

    def hybrid_search(self, query: str, analysis: Dict, limit: int = 10) -> List[Dict]:
        """混合搜索：结合向量搜索和规则过滤"""
        try:
            print(f"[HYBRID] Hybrid search: {query}")

            # 构建搜索查询
            search_query = query

            # 从分析结果中增强查询
            if analysis.get('genres'):
                search_query += f" {' '.join(analysis['genres'])}"

            if analysis.get('mood'):
                search_query += f" {analysis['mood']}"

            # 构建过滤条件
            filters = {}

            # 评分过滤
            rating_pref = analysis.get('rating_preference', '')
            if rating_pref == '高分':
                filters['min_rating'] = 8.5
            elif rating_pref == '经典':
                filters['min_rating'] = 9.0

            # 执行向量搜索
            vector_results = self.semantic_search(
                search_query,
                limit=limit * 2,  # 获取更多结果用于后续排序
                filters=filters
            )
            # ✅ 转换为 recommendation.py 期望的格式
            candidates = []
            for result in vector_results:
                candidate = {
                    'movie_id': result.get('movie_id'),
                    'title': result.get('title'),
                    'similarity_score': result.get('similarity_score', 0.5),
                    'search_method': 'vector_search',
                    'priority': 1,
                    'rating': result.get('rating', 0),
                    'genres': result.get('genres', '')
                }
                candidates.append(candidate)

            print(f"[HYBRID] Vector search found {len(candidates)} candidates")
            return candidates
            # 计算综合得分
            #for result in vector_results:
             #   result['combined_score'] = self._calculate_combined_score(
             #       result, analysis
              #  )

            # 按综合得分排序
            #vector_results.sort(key=lambda x: x['combined_score'], reverse=True)

            #return vector_results[:limit]

        except Exception as e:
            print(f"[ERROR] Hybrid search failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _calculate_combined_score(self, result: Dict, analysis: Dict) -> float:
        """计算综合得分"""
        score = 0.0

        # 向量相似度权重 (40%)
        similarity = result.get('similarity_score', 0)
        score += similarity * 0.4

        # 评分权重 (30%)
        rating = result.get('rating', 0)
        if rating:
            score += (rating / 10.0) * 0.3

        # 类型匹配权重 (20%)
        movie_genres = result.get('genres', '').lower()
        query_genres = [g.lower() for g in analysis.get('genres', [])]

        genre_match = sum(1 for genre in query_genres if genre in movie_genres)
        if query_genres:
            genre_score = genre_match / len(query_genres)
            score += genre_score * 0.2

        # 心情匹配权重 (10%)
        mood = analysis.get('mood', '').lower()
        if mood and mood in movie_genres:
            score += 0.1

        return min(score, 1.0)

    def _extract_year(self, date_string: str) -> int:
        """提取年份"""
        if not date_string:
            return 0

        import re
        match = re.search(r'(\d{4})', date_string)
        return int(match.group(1)) if match else 0

    def get_collection_stats(self) -> Dict:
        """获取集合统计信息"""
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "total_vectors": count,
                "status": "ready" if count > 0 else "empty"
            }
        except Exception as e:
            return {
                "collection_name": self.collection_name,
                "total_vectors": 0,
                "status": "error",
                "error": str(e)
            }

    def add_movie_vector(self, movie: Movie):
        """添加单个电影向量"""
        try:
            text = self.build_movie_text(movie)
            embedding = self.encoder.encode([text]).tolist()[0]

            metadata = {
                "title": movie.title or "",
                "genres": movie.genres or "",
                "directors": movie.directors or "",
                "rating": float(movie.rating) if movie.rating else 0.0,
                "year": self._extract_year(movie.release_date),
                "movie_id": str(movie.movie_id),
                "tags": movie.tags or ""
            }

            self.collection.add(
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[text],
                ids=[f"movie_{movie.movie_id}"]
            )

            print(f"[OK] Added movie vector: {movie.title}")

        except Exception as e:
            print(f"[ERROR] Add movie vector failed: {e}")

    def search_by_description(self, description: str, limit: int = 10) -> List[Dict]:
        """根据描述搜索电影"""
        return self.semantic_search(
            f"电影描述: {description}",
            limit=limit
        )


# 全局向量服务实例
vector_service = VectorService()