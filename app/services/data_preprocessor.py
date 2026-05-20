# app/services/data_preprocessor.py
"""
数据预处理服务：将结构化数据转化为自然语言Prompt
"""
import json
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime


class DataPreprocessor:
    BUILTIN_FEW_SHOT_EXAMPLES = [
        {
            'user_query': '我想看一部轻松搞笑的喜剧片',
            'recommended_movie': '《唐伯虎点秋香》',
            'reason': '周星驰经典无厘头喜剧，笑点密集且不低俗，适合放松心情时观看，评分8.7分口碑极佳。'
        },
        {
            'user_query': '推荐一些烧脑的科幻电影',
            'recommended_movie': '《盗梦空间》',
            'reason': '诺兰经典科幻巨作，多层梦境嵌套设定令人拍案叫绝，视觉奇观与哲学思考兼备，是烧脑爱好者的不二之选。'
        },
        {
            'user_query': '有没有适合情侣一起看的爱情片',
            'recommended_movie': '《怦然心动》',
            'reason': '纯真美好的青春爱情故事，双视角叙事独具匠心，温暖治愈又发人深省，非常适合情侣共同观看。'
        },
        {
            'user_query': '推荐一些经典的悬疑推理电影',
            'recommended_movie': '《看不见的客人》',
            'reason': '西班牙悬疑佳作，层层反转出人意料，逻辑严谨环环相扣，全程无尿点，推理爱好者必看之作。'
        }
    ]

    def __init__(self):
        self.movie_templates = {
            'basic': "电影《{title}》是一部{genres}类型的影片，评分{rating}，发布于{release_date}年。",
            'detailed': "电影《{title}》({release_date})是一部{genres}电影，豆瓣评分{rating}。剧情简介：{summary}",
            'rich': "《{title}》({release_date})：这是一部{genres}类型的{rating}分佳作。{summary} 标签：{tags}。"
        }

        self.user_templates = {
            'preference': "用户偏好：喜欢{liked_genres}类型电影，不喜欢{disliked_genres}，平均观影评分{avg_rating}。",
            'history': "观影历史：最近观看了{recent_movies}，评分分别为{recent_ratings}。",
            'context': "当前状态：{mood}心情，有{time_available}时间，希望看{preference_description}的电影。"
        }

    def movie_to_prompt(self, movie_data: Dict[str, Any], template_type: str = 'detailed') -> str:
        """将电影数据转换为自然语言描述"""
        try:
            template = self.movie_templates.get(template_type, self.movie_templates['detailed'])

            # 处理类型字段
            genres = movie_data.get('genres', [])
            if isinstance(genres, list):
                genres_str = '、'.join(genres) if genres else '未分类'
            else:
                genres_str = str(genres)

            # 处理标签
            tags = movie_data.get('tags', [])
            if isinstance(tags, list):
                tags_str = '、'.join(tags[:5]) if tags else '暂无'
            elif isinstance(tags, str):
                tags_str = tags if tags else '暂无'
            else:
                tags_str = str(tags) if tags else '暂无'

            # 处理年份
            release_date = movie_data.get('release_date', '')
            if release_date and len(release_date) >= 4:
                year = release_date[:4]
            else:
                year = '未知'

            # 处理简介
            summary = movie_data.get('summary', '')
            if not summary:
                summary = '暂无简介'
            elif len(summary) > 200:
                summary = summary[:200] + '...'

            # 格式化prompt
            prompt = template.format(
                title=movie_data.get('title', '未知标题'),
                genres=genres_str,
                rating=movie_data.get('rating', 0.0),
                release_date=year,
                summary=summary,
                tags=tags_str
            )

            return prompt

        except Exception as e:
            print(f"❌ 电影数据转换失败: {e}")
            return f"电影《{movie_data.get('title', '未知')}》"

    def user_profile_to_prompt(self, user_data: Dict[str, Any]) -> str:
        """将用户画像转换为自然语言描述"""
        try:
            prompts = []

            # 用户偏好
            if user_data.get('preferences'):
                pref = user_data['preferences']
                liked = '、'.join(pref.get('liked_genres', ['无特殊偏好']))
                disliked = '、'.join(pref.get('disliked_genres', ['无']))
                avg_rating = pref.get('average_rating', 7.0)

                prompts.append(self.user_templates['preference'].format(
                    liked_genres=liked,
                    disliked_genres=disliked,
                    avg_rating=avg_rating
                ))

            # 观影历史
            if user_data.get('recent_history'):
                history = user_data['recent_history']
                movies = [h['title'] for h in history[:3]]
                ratings = [str(h['rating']) for h in history[:3]]

                prompts.append(self.user_templates['history'].format(
                    recent_movies='《' + '》、《'.join(movies) + '》',
                    recent_ratings='、'.join(ratings) + '分'
                ))

            # 当前上下文
            if user_data.get('current_context'):
                ctx = user_data['current_context']
                prompts.append(self.user_templates['context'].format(
                    mood=ctx.get('mood', '普通'),
                    time_available=ctx.get('time_available', '充足'),
                    preference_description=ctx.get('preference_description', '有趣')
                ))

            return ' '.join(prompts)

        except Exception as e:
            print(f"❌ 用户画像转换失败: {e}")
            return "普通用户，无特殊偏好。"

    def create_few_shot_examples(self, examples: List[Dict[str, Any]]) -> str:
        """创建Few-shot学习样例"""
        few_shot_prompt = "以下是一些推荐示例：\n\n"

        for i, example in enumerate(examples, 1):
            few_shot_prompt += f"示例{i}：\n"
            few_shot_prompt += f"用户需求：{example['user_query']}\n"
            few_shot_prompt += f"推荐电影：{example['recommended_movie']}\n"
            few_shot_prompt += f"推荐理由：{example['reason']}\n\n"

        return few_shot_prompt

    def create_recommendation_prompt(self, user_query: str, user_profile: str,
                                     candidate_movies: List[Dict[str, Any]],
                                     few_shot_examples: str = "") -> str:
        """创建完整的推荐prompt"""
        prompt = f"""你是一个专业的电影推荐专家。请根据用户的需求和个人偏好，从候选电影中选择最合适的推荐，并提供详细的推荐理由。

{few_shot_examples}

用户画像：{user_profile}

用户当前需求：{user_query}

候选电影：
"""

        for i, movie in enumerate(candidate_movies, 1):
            movie_desc = self.movie_to_prompt(movie, 'rich')
            prompt += f"{i}. {movie_desc}\n"

        prompt += """
请从以上候选电影中选择1-3部最合适的进行推荐，格式如下：

推荐电影：
1. 《电影名称》
   推荐理由：[详细解释为什么推荐这部电影，结合用户偏好和电影特点]

2. 《电影名称》
   推荐理由：[详细解释推荐理由]

请确保推荐理由具体、个性化，能够说服用户观看。
"""

        return prompt


# 全局实例
data_preprocessor = DataPreprocessor()