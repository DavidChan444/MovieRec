"""
大语言模型服务
"""
from openai import OpenAI
from typing import Dict, List, Any
from ..core.config import settings
import json
import re


class LLMService:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL
        )

    def analyze_user_query(self, query: str) -> Dict[str, Any]:
        """分析用户查询意图"""
        print(f"🔍 分析用户查询: {query}")

        # 直接使用规则分析，避免LLM调用和jieba依赖
        return self._simple_analysis(query)

    def _simple_analysis(self, query: str) -> Dict[str, Any]:
        """简单的规则分析"""
        query_lower = query.lower()

        # 类型映射 - 扩展关键词
        genre_mapping = {
            '喜剧': ['喜剧', '好笑', '搞笑', '幽默', '轻松', '开心', '有趣', '逗乐'],
            '科幻': ['科幻', '未来', '外星', '机器人', '太空', 'sci-fi', '科学', '技术'],
            '爱情': ['爱情', '恋爱', '浪漫', '情侣', '感情', '爱恋', '情感'],
            '动作': ['动作', '打斗', '功夫', '武侠', '动作片', '格斗'],
            '恐怖': ['恐怖', '惊悚', '害怕', '吓人', '惊悚片'],
            '悬疑': ['悬疑', '推理', '烧脑', '犯罪', '侦探', '破案'],
            '动画': ['动画', '卡通', '动漫', '动画片'],
            '战争': ['战争', '历史', '军事', '战争片'],
            '剧情': ['剧情', '文艺', '深刻', '剧情片'],
            '纪录片': ['纪录片', '真实', '记录', '纪实']
        }

        genres = []
        keywords = []

        # 检测类型
        for genre, words in genre_mapping.items():
            for word in words:
                if word in query_lower:
                    if genre not in genres:
                        genres.append(genre)
                    if word not in keywords:
                        keywords.append(word)

        # 提取其他关键词（简单分词）
        # 提取中文词汇和英文单词
        chinese_words = re.findall(r'[\u4e00-\u9fff]+', query)
        english_words = re.findall(r'[a-zA-Z]+', query)

        all_words = chinese_words + english_words

        for word in all_words:
            if len(word) > 1 and word not in keywords and len(keywords) < 8:
                keywords.append(word)

        # 检测情感词汇
        mood_keywords = {
            '轻松': ['轻松', '开心', '愉快', '快乐'],
            '深刻': ['深刻', '思考', '哲学', '内涵'],
            '刺激': ['刺激', '紧张', '兴奋']
        }

        mood = ""
        for mood_type, mood_words in mood_keywords.items():
            if any(word in query_lower for word in mood_words):
                mood = mood_type
                break

        analysis_result = {
            "query_type": "recommendation",
            "genres": genres,
            "keywords": keywords,
            "mood": mood,
            "preferences": query
        }

        print(f"📋 分析结果: {analysis_result}")
        return analysis_result

    def generate_recommendation_reason(self, movie_info: Dict, user_preferences: str) -> str:
        """生成推荐理由 - 调用OpenAI API，失败时降级到模板"""
        title = movie_info.get('title', '这部电影')
        genres = movie_info.get('genres', '')
        rating = movie_info.get('rating', 0)
        summary = movie_info.get('summary', '')
        tags = movie_info.get('tags', '')

        # 尝试使用OpenAI API生成个性化推荐理由
        try:
            prompt = f"""你是一个电影推荐专家。请为以下电影生成一个简洁、个性化的推荐理由（20-50字）。

电影信息：
- 标题：{title}
- 类型：{genres}
- 评分：{rating}
- 简介：{summary[:150] if summary else '暂无'}
- 标签：{tags if tags else '暂无'}

用户需求：{user_preferences}

推荐理由："""

            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.7
            )

            reason = response.choices[0].message.content.strip()
            if reason:
                return reason

        except Exception as e:
            print(f"⚠️ OpenAI API生成推荐理由失败，使用模板降级: {e}")

        # 降级：基于评分的模板推荐理由
        try:
            if rating and rating >= 9.0:
                return f"高分佳作《{title}》评分高达{rating}分，是{genres}类型的经典之作，口碑极佳"
            elif rating and rating >= 8.5:
                return f"《{title}》是一部优秀的{genres}电影，评分{rating}，深受观众喜爱"
            elif rating and rating >= 8.0:
                return f"推荐《{title}》这部{genres}电影，评分{rating}，质量上乘值得观看"
            elif rating and rating >= 7.0:
                return f"《{title}》是一部不错的{genres}电影，评分{rating}"
            else:
                return f"《{title}》是一部{genres}电影，符合您的观影偏好" if genres else f"推荐《{title}》，符合您的观影偏好"
        except Exception as e:
            print(f"生成推荐理由失败: {e}")
            return f"推荐《{title}》，这是一部值得观看的电影"


# 全局服务实例
llm_service = LLMService()