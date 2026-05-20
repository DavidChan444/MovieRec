"""
LLM聊天路由 - 集成LangChain、对话历史、自适应推荐
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..services.langchain_service import langchain_service
from ..services.recommendation import recommendation_service
from ..services.adaptive_recommendation_service import adaptive_recommendation_service
from ..core.security import verify_token
from ..models.user import ChatSession, ChatMessage
from ..data.database import SessionLocal

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessageSchema(BaseModel):
    """聊天消息模型"""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    history: List[ChatMessageSchema] = []
    session_id: Optional[int] = None


class ChatResponse(BaseModel):
    """聊天响应"""
    response: str
    recommendations: List[Dict[str, Any]] = []
    query_analysis: Dict[str, Any] = {}
    summary: str = ""
    session_id: Optional[int] = None


@router.post("/", response_model=ChatResponse)
async def chat_with_llm(
    request: ChatRequest,
    authorization: Optional[str] = Header(None)
):
    """与LLM聊天并获取电影推荐 - 支持对话历史和自适应推荐"""
    try:
        print(f"[CHAT] 收到聊天请求: {request.message}")

        # 提取用户身份
        user_id = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization[7:]
            user_data = verify_token(token)
            if user_data:
                try:
                    user_id = int(user_data)
                    print(f"[CHAT] 已认证用户: {user_id}")
                except (ValueError, TypeError):
                    pass

        # 转换历史消息格式
        conversation_history = []
        for msg in request.history:
            conversation_history.append({
                "role": msg.role,
                "content": msg.content
            })

        # 分析用户查询
        analysis = langchain_service.analyze_user_query(request.message)
        print(f"[CHAT] 查询分析: {analysis}")

        # 检查是否需要电影推荐
        if analysis.get('query_type') == 'recommendation':
            # 使用自适应推荐（如果用户已认证）
            if user_id:
                try:
                    recommendation_result = adaptive_recommendation_service.get_personalized_recommendations(
                        user_id=user_id, query=request.message, limit=8
                    )
                    if 'error' in recommendation_result:
                        print(f"[CHAT] 自适应推荐失败, 降级: {recommendation_result['error']}")
                        recommendation_result = recommendation_service.get_recommendations_by_query(
                            request.message, limit=8, user_id=user_id
                        )
                except Exception as e:
                    print(f"[CHAT] 自适应推荐异常, 降级: {e}")
                    recommendation_result = recommendation_service.get_recommendations_by_query(
                        request.message, limit=8, user_id=user_id
                    )
            else:
                recommendation_result = recommendation_service.get_recommendations_by_query(
                    request.message, limit=8
                )

            if 'error' not in recommendation_result:
                recommendations = recommendation_result.get('recommendations', [])
                summary = recommendation_result.get('summary', '')

                if recommendations:
                    # 生成智能回复
                    try:
                        movie_descriptions = []
                        for m in recommendations[:5]:
                            reason = m.get('reason', '')
                            movie_descriptions.append(f"《{m['title']}》- {m.get('genres','')} - 评分{m.get('rating','')} - {reason}")
                        smart_response = langchain_service.chat_with_context(
                            f"你是电影推荐助手。用户说：「{request.message}」\n\n"
                            f"你找到了以下电影：\n"
                            + "\n".join(f"- {d}" for d in movie_descriptions) +
                            "\n\n请以推荐助手的身份，直接向用户推荐这些电影。注意：不要说「您的推荐很好」之类的赞同用户的话——这些电影是你要推荐给用户的，不是用户推荐的。简要介绍每部电影为什么适合用户，语气热情专业。",
                            conversation_history
                        )
                        response_text = smart_response
                    except Exception as e:
                        print(f"[CHAT] LangChain智能回复失败: {e}")
                        response_text = f"根据您的需求「{request.message}」，我为您推荐以下{len(recommendations)}部电影：\n\n"
                        for i, movie in enumerate(recommendations, 1):
                            response_text += f"{i}. 《{movie['title']}》\n"
                            response_text += f"   评分: {movie.get('rating', 'N/A')}\n"
                            response_text += f"   类型: {movie.get('genres', 'N/A')}\n"
                            response_text += f"   推荐理由: {movie.get('reason', '这部电影符合您的偏好')}\n\n"
                else:
                    response_text = "抱歉，没有找到完全符合您要求的电影。请尝试调整您的需求描述，或者告诉我更多您的偏好。"
                    recommendations = []
                    summary = ""
            else:
                response_text = "抱歉，推荐系统暂时遇到问题，请稍后再试。"
                recommendations = []
                summary = ""
        else:
            try:
                response_text = langchain_service.chat_with_context(
                    request.message, conversation_history
                )
            except Exception as e:
                print(f"[CHAT] LangChain对话失败: {e}")
                response_text = _generate_general_response(request.message, analysis)
            recommendations = []
            summary = ""

        # 持久化对话历史
        session_id = request.session_id
        if user_id:
            session_id = _save_chat_messages(
                user_id=user_id,
                session_id=session_id,
                user_message=request.message,
                assistant_message=response_text,
                recommendations=recommendations,
                analysis=analysis
            )

        return ChatResponse(
            response=response_text,
            recommendations=recommendations,
            query_analysis=analysis,
            summary=summary,
            session_id=session_id
        )

    except Exception as e:
        print(f"[CHAT] 聊天处理失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"聊天处理失败: {str(e)}")


def _save_chat_messages(
    user_id: int,
    session_id: Optional[int],
    user_message: str,
    assistant_message: str,
    recommendations: List[Dict],
    analysis: Dict
) -> int:
    """保存聊天消息到数据库"""
    db = SessionLocal()
    try:
        # 获取或创建会话
        if session_id:
            session = db.query(ChatSession).filter(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id
            ).first()

        if not session_id or not session:
            # 创建新会话，使用用户消息的前30个字符作为标题
            title = user_message[:30] + ("..." if len(user_message) > 30 else "")
            session = ChatSession(
                user_id=user_id,
                title=title
            )
            db.add(session)
            db.flush()

        # 保存用户消息
        user_msg = ChatMessage(
            session_id=session.id,
            role="user",
            content=user_message
        )
        db.add(user_msg)

        # 保存AI回复
        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=assistant_message,
            recommendations=recommendations,
            query_analysis=analysis
        )
        db.add(assistant_msg)

        # 更新会话时间
        session.updated_at = datetime.utcnow()

        db.commit()
        print(f"[CHAT] 对话已保存: session={session.id}")
        return session.id

    except Exception as e:
        db.rollback()
        print(f"[CHAT] 保存对话失败: {e}")
        return session_id or 0
    finally:
        db.close()


def _generate_general_response(message: str, analysis: Dict) -> str:
    """生成通用聊天响应 - 降级方法"""
    if any(word in message.lower() for word in ['电影', '影片', '推荐', '好看']):
        return "我是一个电影推荐助手！您可以告诉我您想看什么类型的电影，或者描述您当前的心情，我会为您推荐合适的电影。比如说「我想看轻松的喜剧片」或「推荐一些科幻电影」。"
    elif any(word in message.lower() for word in ['你好', 'hello', '嗨']):
        return "您好！我是您的智能电影推荐助手。我可以根据您的喜好为您推荐电影，您想看什么类型的电影呢？"
    elif any(word in message.lower() for word in ['谢谢', '感谢']):
        return "不客气！如果您还想要更多电影推荐，请随时告诉我您的需求。我会为您找到最适合的电影！"
    else:
        return "我是专门为您推荐电影的智能助手。您可以告诉我您想看的电影类型、心情或者具体需求，我会为您推荐最合适的电影！"


@router.get("/health")
async def chat_health_check():
    """聊天服务健康检查"""
    try:
        test_analysis = langchain_service.analyze_user_query("测试")
        return {
            "status": "healthy",
            "service": "langchain-chat-service",
            "langchain_status": "operational" if test_analysis else "degraded"
        }
    except Exception as e:
        return {
            "status": "degraded",
            "service": "langchain-chat-service",
            "error": str(e)
        }


@router.get("/sessions")
async def get_chat_sessions(
    authorization: Optional[str] = Header(None)
):
    """获取用户的聊天会话列表"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未认证")

    token = authorization[7:]
    user_data = verify_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="无效的认证令牌")

    try:
        user_id = int(user_data)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="无效的用户标识")

    db = SessionLocal()
    try:
        sessions = db.query(ChatSession).filter(
            ChatSession.user_id == user_id,
            ChatSession.is_active == True
        ).order_by(ChatSession.updated_at.desc()).all()

        return {
            "sessions": [s.to_dict() for s in sessions],
            "total": len(sessions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")
    finally:
        db.close()


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: int,
    authorization: Optional[str] = Header(None)
):
    """获取指定会话的聊天消息"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未认证")

    token = authorization[7:]
    user_data = verify_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="无效的认证令牌")

    try:
        user_id = int(user_data)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="无效的用户标识")

    db = SessionLocal()
    try:
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at).all()

        return {
            "session": session.to_dict(),
            "messages": [m.to_dict() for m in messages]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取消息失败: {str(e)}")
    finally:
        db.close()


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: int,
    authorization: Optional[str] = Header(None)
):
    """删除（软删除）聊天会话"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未认证")

    token = authorization[7:]
    user_data = verify_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="无效的认证令牌")

    try:
        user_id = int(user_data)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="无效的用户标识")

    db = SessionLocal()
    try:
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        session.is_active = False
        db.commit()
        return {"message": "会话已删除"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")
    finally:
        db.close()
