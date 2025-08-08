"""
DSE AI Teacher API 主应用

本模块是DSE英文阅读理解Demo系统的后端入口，
集成了完整的API路由、中间件、错误处理等功能。

核心功能：
- DSE题目数据提供
- AI老师智能批改
- 实时批改结果查询
- 完善的错误处理和日志记录
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
import logging
import traceback
from datetime import datetime
import sys
import os

# 设置控制台输出编码为UTF-8
if sys.platform.startswith('win'):
    # Windows平台UTF-8编码设置
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from .core.config import get_settings
from .routes.dse import router as dse_router
from .routes.chat import router as chat_router
from .routes.tts import router as tts_router
from .models.dse_models import ErrorResponse

# 获取配置
settings = get_settings()

# 配置日志 - 修复Unicode编码问题
def setup_logging():
    """设置日志系统，处理Unicode字符"""
    # 创建自定义格式器，安全处理Unicode
    class SafeFormatter(logging.Formatter):
        def format(self, record):
            try:
                # 确保消息是字符串并处理Unicode
                if hasattr(record, 'msg') and record.msg:
                    # 安全地处理包含Unicode字符的消息
                    record.msg = str(record.msg).encode('utf-8', errors='replace').decode('utf-8')
                return super().format(record)
            except Exception:
                # 如果格式化失败，返回安全的替代消息
                record.msg = "[日志格式化错误 - 包含特殊字符]"
                return super().format(record)
    
    # 设置日志配置
    formatter = SafeFormatter(settings.LOG_FORMAT)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    if sys.platform.startswith('win'):
        console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
    
    # 文件处理器
    file_handler = logging.FileHandler(f"{settings.LOGS_DIR}/app.log", encoding='utf-8', errors='replace')
    file_handler.setFormatter(formatter)
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

setup_logging()

logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="""
    DSE英文阅读理解AI老师API
    
    提供完整的DSE Demo体验，包括：
    - 获取阅读理解题目数据
    - 提交答案进行AI批改
    - 查询批改结果和教学分析
    
    Built with ❤️ for education
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理器"""
    logger.warning(f"HTTP异常: {exc.status_code} - {exc.detail}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=True,
            message=exc.detail,
            code=f"HTTP_{exc.status_code}"
        ).dict()
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证异常处理器"""
    logger.warning(f"请求验证失败: {exc.errors()}")
    
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error=True,
            message="请求参数验证失败",
            detail=str(exc.errors()),
            code="VALIDATION_ERROR"
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理器"""
    logger.error(f"未处理的异常: {exc}")
    logger.error(f"异常堆栈: {traceback.format_exc()}")
    
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=True,
            message="服务器内部错误",
            detail="请联系管理员或稍后重试",
            code="INTERNAL_ERROR"
        ).dict()
    )


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """请求日志中间件"""
    start_time = datetime.now()
    
    # 记录请求
    logger.info(f"请求开始: {request.method} {request.url}")
    
    try:
        response = await call_next(request)
        
        # 记录响应
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"请求完成: {request.method} {request.url} - "
                   f"状态码: {response.status_code} - 耗时: {duration:.3f}s")
        
        return response
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"请求异常: {request.method} {request.url} - "
                    f"错误: {str(e)} - 耗时: {duration:.3f}s")
        raise


# 全局 OPTIONS 处理器
@app.options("/{full_path:path}")
async def options_handler(request: Request, full_path: str):
    """处理所有 OPTIONS 预检请求"""
    origin = request.headers.get("origin", "")
    logger.info(f"OPTIONS 请求 - 路径: {full_path}, Origin: {origin}")
    
    # 允许的来源列表
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080"
    ]
    
    # 检查来源是否被允许
    allow_origin = origin if origin in allowed_origins else "http://localhost:3000"
    
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": allow_origin,
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "86400",
        }
    )

# 注册路由
app.include_router(dse_router)
app.include_router(chat_router)
app.include_router(tts_router)


# 根路径
@app.get("/", tags=["System"])
async def root():
    """API根路径"""
    return {
        "message": "欢迎使用DSE AI Teacher API",
        "version": settings.VERSION,
        "docs_url": "/docs",
        "health_check": "/health"
    }


# 健康检查
@app.get("/health", tags=["System"])
async def health_check():
    """
    健康检查接口
    
    检查API服务状态和依赖项可用性
    """
    try:
        # 这里可以添加数据库、Redis等依赖项检查
        health_status = {
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.VERSION,
            "timestamp": datetime.now().isoformat(),
            "uptime": "运行中",
            "dependencies": {
                "data_files": "可用",
                "ai_service": "可用" if settings.OPENROUTER_API_KEY else "未配置"
            }
        }
        
        logger.info("健康检查通过")
        return health_status
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(
            status_code=503,
            detail="服务不可用"
        )


# 启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info(f"{settings.APP_NAME} v{settings.VERSION} 启动中...")
    logger.info(f"调试模式: {settings.DEBUG}")
    logger.info(f"API文档: http://{settings.HOST}:{settings.PORT}/docs")
    logger.info(f"CORS配置 - 允许的来源: {settings.ALLOWED_ORIGINS}")
    
    # 检查关键配置
    if not settings.OPENROUTER_API_KEY:
        logger.warning("WARNING: OPENROUTER_API_KEY 未配置，AI功能将使用降级模式")
    else:
        logger.info("SUCCESS: OpenRouter API 配置完成")


# 关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info(f"{settings.APP_NAME} 正在关闭...")


if __name__ == "__main__":
    import uvicorn
    
    logger.info("直接运行模式启动")
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )