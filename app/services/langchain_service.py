"""
LangChain服务 - 电影推荐增强
优化版本，解决deprecation警告
"""

try:
    # LangChain 0.1.0 最佳实践导入方式
    from langchain_openai import ChatOpenAI, OpenAI
    from langchain_core.prompts import PromptTemplate
    from langchain.chains import LLMChain, ConversationChain
    from langchain.memory import ConversationBufferMemory

    LANGCHAIN_AVAILABLE = True
    print("[OK] LangChain 0.1.0 imported (recommended path)")

except ImportError as e:
    print(f"[ERROR] Primary import failed: {e}")
    print("[...] Trying fallback import...")

    try:
        # 备用导入方式（保持向后兼容）
        from langchain.llms.openai import OpenAI
        from langchain.prompts import PromptTemplate
        from langchain.chains import LLMChain
        from langchain.memory import ConversationBufferMemory
        from langchain.chat_models import ChatOpenAI

        LANGCHAIN_AVAILABLE = True
        print("[OK] LangChain fallback import succeeded")

    except ImportError as backup_error:
        print(f"[ERROR] Fallback import also failed: {backup_error}")
        LANGCHAIN_AVAILABLE = False

# 导入其他必需的模块
import json
import warnings
from typing import Dict, Any, List, Optional
from ..core.config import settings

# 忽略deprecation警告（可选）
warnings.filterwarnings("ignore", category=DeprecationWarning)


class LangChainService:
    """LangChain的电影推荐服务"""

    def __init__(self):
        """初始化LangChain服务"""
        self.available = LANGCHAIN_AVAILABLE
        self.llm = None
        self.memory = None

        if self.available:
            try:
                # 使用最新的langchain-openai包
                self.llm = ChatOpenAI(
                    model=settings.OPENAI_MODEL,
                    api_key=settings.OPENAI_API_KEY,  # 使用新的参数名
                    base_url=settings.OPENAI_BASE_URL,  # 使用新的参数名
                    temperature=0.7,
                    max_tokens=1500
                )

                # 初始化对话记忆
                self.memory = ConversationBufferMemory(
                    return_messages=True,
                    memory_key="history"
                )

                print("[OK] LangChain service initialized successfully")

            except Exception as e:
                print(f"[WARN] LangChain init failed: {e}")
                print(f"[...] Trying fallback config...")

                try:
                    # 备用配置
                    self.llm = ChatOpenAI(
                        openai_api_key=settings.OPENAI_API_KEY,
                        openai_api_base=settings.OPENAI_BASE_URL,
                        model_name=settings.OPENAI_MODEL,
                        temperature=0.7,
                        max_tokens=1500
                    )
                    print("[OK] Fallback config succeeded")

                except Exception as backup_e:
                    print(f"[ERROR] Fallback config also failed: {backup_e}")
                    self.available = False

    def analyze_user_query(self, query: str) -> Dict[str, Any]:
        """使用LangChain分析用户查询"""
        if not self.available or not self.llm:
            return self._fallback_analysis(query)

        try:
            # 创建分析提示模板
            analysis_template = PromptTemplate(
                input_variables=["query"],
                template="""分析以下用户的电影查询，返回JSON格式的结构化信息：

用户查询: {query}

请分析并返回以下信息的JSON（只返回JSON，不要包含其他文字）：
{{
    "query_type": "recommendation|chat|question",
    "genres": ["提取的电影类型"],
    "mood": "轻松|深刻|紧张|浪漫|搞笑",
    "rating_preference": "高分|经典|无偏好",
    "keywords": ["关键词"],
    "excluded_genres": ["不想看的类型"],
    "time_period": "90年代|2000年代|最新|无偏好",
    "intent": "用户意图描述"
}}

注意：query_type含义：如果用户请求推荐电影则为recommendation，如果是普通聊天则为chat，如果是询问电影相关信息则为question。如果用户说"不要"、"除了"、"不想看"某类型，将该类型放入excluded_genres。"""
            )

            # 创建分析链
            analysis_chain = LLMChain(
                llm=self.llm,
                prompt=analysis_template,
                verbose=False
            )

            # 执行分析
            result = analysis_chain.run(query=query)

            # 解析JSON结果
            try:
                # 清理结果字符串
                cleaned_result = result.strip()
                if cleaned_result.startswith('```json'):
                    cleaned_result = cleaned_result.replace('```json', '').replace('```', '')
                elif cleaned_result.startswith('```'):
                    cleaned_result = cleaned_result.replace('```', '')

                analysis_data = json.loads(cleaned_result)
                print(f"[Analysis] LangChain result: {analysis_data}")
                return analysis_data

            except json.JSONDecodeError as json_e:
                print(f"[WARN] JSON parse failed: {json_e}")
                print(f"Raw result: {result}")
                return self._fallback_analysis(query)

        except Exception as e:
            print(f"[WARN] LangChain analysis failed: {e}")
            return self._fallback_analysis(query)

    def generate_recommendation_reason(self, movie: Dict, query: str, analysis: Dict = None) -> str:
        """生成推荐理由"""
        if not self.available or not self.llm:
            return self._fallback_reason(movie, query)

        try:
            reason_template = PromptTemplate(
                input_variables=["movie_title", "movie_genres", "movie_rating", "movie_summary", "movie_tags", "user_query"],
                template="""为电影《{movie_title}》生成推荐理由：

电影信息：
- 标题：{movie_title}
- 类型：{movie_genres}
- 评分：{movie_rating}
- 简介：{movie_summary}
- 标签：{movie_tags}

用户需求：{user_query}

请生成一个简洁、个性化的推荐理由（20-40字），要结合电影的具体内容："""
            )

            reason_chain = LLMChain(
                llm=self.llm,
                prompt=reason_template,
                verbose=False
            )

            reason = reason_chain.run(
                movie_title=movie.get('title', '未知'),
                movie_genres=movie.get('genres', '未知'),
                movie_rating=movie.get('rating', '未知'),
                movie_summary=(movie.get('summary') or '暂无')[:150],
                movie_tags=movie.get('tags', '暂无'),
                user_query=query
            )

            return reason.strip()

        except Exception as e:
            print(f"[WARN] Reason generation failed: {e}")
            return self._fallback_reason(movie, query)

    def chat_with_context(self, message: str, history: List[Dict] = None) -> str:
        """带上下文的智能对话"""
        if not self.available or not self.llm:
            return self._fallback_chat_response(message)

        try:
            # 创建新的记忆实例用于此次对话
            conversation_memory = ConversationBufferMemory(
                return_messages=True,
                memory_key="history"
            )

            # 如果有历史对话，添加到记忆中
            if history:
                for msg in history[-5:]:  # 只保留最近5条
                    if msg.get('role') == 'user':
                        conversation_memory.chat_memory.add_user_message(msg.get('content', ''))
                    elif msg.get('role') == 'assistant':
                        conversation_memory.chat_memory.add_ai_message(msg.get('content', ''))

            # 创建对话链
            conversation_chain = ConversationChain(
                llm=self.llm,
                memory=conversation_memory,
                verbose=False
            )

            # 生成回复
            response = conversation_chain.predict(input=message)
            return response.strip()

        except Exception as e:
            print(f"[WARN] Smart chat failed: {e}")
            return self._fallback_chat_response(message)

    def generate_movie_summary(self, recommendations: List[Dict], query: str) -> str:
        """生成推荐总结"""
        if not self.available or not self.llm or not recommendations:
            return ""

        try:
            movie_titles = [rec.get('title', '未知') for rec in recommendations[:3]]

            summary_template = PromptTemplate(
                input_variables=["query", "movies"],
                template="""用户说："{query}"

你为用户推荐了这些电影：{movies}

请生成一句简洁的总结（15-25字），以推荐助手的身份直接告诉用户为什么这些电影适合他们："""
            )

            summary_chain = LLMChain(
                llm=self.llm,
                prompt=summary_template,
                verbose=False
            )

            summary = summary_chain.run(
                query=query,
                movies="、".join(movie_titles)
            )

            return summary.strip()

        except Exception as e:
            print(f"[WARN] Summary generation failed: {e}")
            return ""

    def test_connection(self) -> bool:
        """测试LangChain连接"""
        if not self.available:
            print("[ERROR] LangChain not available")
            return False

        try:
            test_result = self.llm.predict("Hello")
            print(f"[OK] LangChain connection test succeeded: {test_result[:50]}...")
            return bool(test_result)
        except Exception as e:
            print(f"[ERROR] LangChain connection test failed: {e}")
            return False

    def _fallback_analysis(self, query: str) -> Dict[str, Any]:
        """降级分析方法"""
        print("[FALLBACK] Using fallback analysis")

        analysis = {
            'query_type': 'recommendation',
            'genres': [],
            'mood': '',
            'rating_preference': '',
            'keywords': [],
            'excluded_genres': [],
            'time_period': '',
            'intent': '电影推荐'
        }

        # 简单关键词检测
        query_lower = query.lower()

        # 检测类型
        genre_map = {
            '喜剧': ['喜剧', '搞笑', '轻松', '幽默', 'comedy'],
            '科幻': ['科幻', 'sci-fi', '未来', '太空', '科学'],
            '爱情': ['爱情', '浪漫', '恋爱', '情侣', 'romance'],
            '动作': ['动作', '打斗', '武打', '功夫', 'action'],
            '恐怖': ['恐怖', '惊悚', '吓人', 'horror'],
            '剧情': ['剧情', '深刻', '内涵', '人生', 'drama'],
            '悬疑': ['悬疑', '推理', '侦探', 'mystery']
        }

        for genre, keywords in genre_map.items():
            if any(kw in query for kw in keywords):
                analysis['genres'].append(genre)

        # 检测心情
        if any(word in query for word in ['轻松', '搞笑', '开心', '愉快']):
            analysis['mood'] = '轻松'
        elif any(word in query for word in ['深刻', '内涵', '思考', '严肃']):
            analysis['mood'] = '深刻'
        elif any(word in query for word in ['浪漫', '甜蜜', '温馨']):
            analysis['mood'] = '浪漫'

        # 检测评分偏好
        if any(word in query for word in ['高分', '好评', '经典', '名片']):
            analysis['rating_preference'] = '高分'
        elif any(word in query for word in ['经典', '名作', '大师']):
            analysis['rating_preference'] = '经典'

        # 检测时期偏好
        if any(word in query for word in ['90年代', '九十年代', '90s']):
            analysis['time_period'] = '90年代'
        elif any(word in query for word in ['2000年代', '千禧年']):
            analysis['time_period'] = '2000年代'
        elif any(word in query for word in ['最新', '新片', '近期']):
            analysis['time_period'] = '最新'

        # 检测排除类型（用户明确不想看的）
        exclusion_markers = ['不要', '除了', '不想看', '不喜欢', '别推荐', '排除']
        if any(marker in query for marker in exclusion_markers):
            for genre, keywords in genre_map.items():
                if any(kw in query for kw in keywords):
                    # Check if the keyword appears near exclusion markers
                    for marker in exclusion_markers:
                        if marker in query:
                            idx = query.index(marker)
                            for kw in keywords:
                                kw_idx = query.find(kw)
                                if kw_idx >= 0 and abs(kw_idx - idx) < 15:
                                    if genre not in analysis['genres']:
                                        analysis['excluded_genres'].append(genre)
                                    break

        return analysis

    def _fallback_reason(self, movie: Dict, query: str) -> str:
        """降级推荐理由"""
        title = movie.get('title', '这部电影')
        rating = movie.get('rating')
        genres = movie.get('genres', '')

        if rating and rating >= 9.0:
            return f"{title}是一部评分{rating}的经典佳作，口碑极佳"
        elif rating and rating >= 8.5:
            return f"{title}评分{rating}，是一部高质量的优秀电影"
        elif '喜剧' in genres:
            return f"{title}是一部轻松搞笑的喜剧片，适合放松心情"
        elif '科幻' in genres:
            return f"{title}是一部精彩的科幻电影，想象力丰富"
        elif '爱情' in genres:
            return f"{title}是一部浪漫的爱情电影，情节动人"
        else:
            return f"{title}符合您的观影偏好，值得一看"

    def _fallback_chat_response(self, message: str) -> str:
        """降级聊天回复"""
        message_lower = message.lower()

        if any(word in message_lower for word in ['推荐', '电影', '影片']):
            return "我是专业的电影推荐助手！请告诉我您喜欢什么类型的电影，比如喜剧、科幻、爱情等，我会为您推荐合适的作品。"
        elif any(word in message_lower for word in ['你好', 'hello', '嗨', 'hi']):
            return "您好！我是智能电影推荐助手🎬 我可以根据您的喜好为您推荐精彩的电影。您想看什么类型的电影呢？"
        elif any(word in message_lower for word in ['谢谢', '感谢', 'thanks']):
            return "不客气！😊 如果您还想要更多电影推荐，请随时告诉我您的需求。我会继续为您找到最适合的电影！"
        elif any(word in message_lower for word in ['帮助', 'help']):
            return "我可以帮您：\n1. 根据类型推荐电影（如\"推荐些科幻片\"）\n2. 根据心情推荐（如\"想看轻松的电影\"）\n3. 推荐高分电影\n请告诉我您的需求！"
        else:
            return "我是专门为您推荐电影的智能助手🎬 您可以告诉我您想看的电影类型、心情或者具体需求，我会为您推荐最合适的电影！"


# 创建全局服务实例
langchain_service = LangChainService()


# 导出服务状态
def get_langchain_status() -> Dict[str, Any]:
    """获取LangChain服务状态"""
    return {
        "available": langchain_service.available,
        "llm_initialized": bool(langchain_service.llm),
        "memory_initialized": bool(langchain_service.memory)
    }