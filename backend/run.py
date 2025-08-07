"""
DSE AI Teacher API 启动脚本

用于开发和生产环境的统一启动入口
"""

import uvicorn
import os
from app.core.config import get_settings

def main():
    """主启动函数"""
    settings = get_settings()
    
    # 确保日志目录存在
    os.makedirs(settings.LOGS_DIR, exist_ok=True)
    
    print(f"🚀 启动 {settings.APP_NAME} v{settings.VERSION}")
    print(f"📖 API文档: http://{settings.HOST}:{settings.PORT}/docs")
    print(f"🔧 调试模式: {settings.DEBUG}")
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )

if __name__ == "__main__":
    main()