from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional, List, Union
import os
import json


class Settings(BaseSettings):
    """应用程序配置"""
    # 基本设置
    APP_NAME: str = "DSE AI Teacher API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    DEBUG: bool = True  # 🔥 临时开启DEBUG模式以诊断TTS问题
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    
    # CORS配置
    ALLOWED_ORIGINS: Union[List[str], str] = [
        "https://764d2c34aed5.ngrok-free.app"
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080"
    ]
    
    # OpenRouter API配置
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    
    # Azure Speech服务配置 (已弃用，替换为Minimax)
    AZURE_SPEECH_KEY: Optional[str] = None
    AZURE_SPEECH_REGION: Optional[str] = None
    
    # Minimax TTS服务配置
    MINIMAX_API_KEY: Optional[str] = None
    MINIMAX_GROUP_ID: Optional[str] = None
    MINIMAX_TTS_MODEL: str = "speech-02-hd"
    
    # AI模型配置
    DEFAULT_MODEL: str = "qwen/qwen3-235b-a22b"
    MODEL_MAX_TOKENS: int = 4000
    MODEL_TEMPERATURE: float = 0.1
    
    # 文件路径配置
    DATA_DIR: str = "../data"
    LOGS_DIR: str = "logs"
    
    # 安全配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # 数据库配置（预留）
    DATABASE_URL: Optional[str] = None
    
    # Redis配置（预留）
    REDIS_URL: Optional[str] = None
    
    # 日志配置
    LOG_LEVEL: str = "DEBUG"  # 🔥 临时设置为DEBUG以诊断TTS问题
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    @field_validator('ALLOWED_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """解析 CORS 原点配置"""
        # 默认允许的来源
        default_origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8080",
            "http://127.0.0.1:8080"
        ]
        
        # 如果 v 是 None 或未定义，返回默认值
        if v is None:
            return default_origins
            
        # 如果是字符串类型
        if isinstance(v, str):
            if v.strip() == "":
                # 空字符串，返回默认值
                return default_origins
            try:
                # 尝试解析为 JSON
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                else:
                    return [str(parsed)]
            except json.JSONDecodeError:
                # 如果不是有效的 JSON，将其视为单个 origin
                return [v.strip()]
        
        # 如果已经是列表，直接返回
        if isinstance(v, list):
            return v
            
        # 其他情况返回默认值
        return default_origins

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 忽略额外的环境变量
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 确保日志目录存在
        os.makedirs(self.LOGS_DIR, exist_ok=True)


# 全局配置实例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取配置实例（单例模式）"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings 