"""
主应用程序入口
"""
import sys

# 修复Windows控制台编码问题
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.data.database import engine, Base
from app.routers import movies, users, chat
from app.core.config import settings

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="智能电影推荐系统 - 支持多种推荐算法和用户行为学习",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(movies.router)
app.include_router(users.router)
app.include_router(chat.router)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "app_name": settings.APP_NAME
    }


if __name__ == "__main__":
    print(f" 启动 {settings.APP_NAME} v{settings.VERSION}")
    print(f" 访问地址: http://localhost:8000")
    print(f" API文档: http://localhost:8000/docs")
    print(f" 功能: 多算法推荐 + 用户行为学习 + 个性化推荐")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )