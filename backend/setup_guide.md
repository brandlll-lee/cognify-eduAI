# DSE AI Teacher API 设置指南

## 环境配置

创建 `.env` 文件并配置以下环境变量：

```env
# OpenRouter API配置（必需）
OPENROUTER_API_KEY=your_openrouter_api_key_here

# 服务器配置
HOST=0.0.0.0
PORT=8000
DEBUG=true

# AI模型配置
DEFAULT_MODEL=anthropic/claude-3.5-sonnet
MODEL_TEMPERATURE=0.1

# 文件路径配置
DATA_DIR=../data

# 日志配置
LOG_LEVEL=INFO
```

## 快速启动

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 设置环境变量：

```bash
# Windows
set OPENROUTER_API_KEY=your_key_here

# Linux/Mac
export OPENROUTER_API_KEY=your_key_here
```

3. 启动服务：

```bash
# 方式1：使用启动脚本
python run.py

# 方式2：直接使用uvicorn
uvicorn app.main:app --reload --port 8001
```

4. 访问 API 文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 测试 API

使用 curl 测试 API：

```bash
# 健康检查
curl http://localhost:8000/health

# 获取题目数据
curl http://localhost:8000/api/dse/demo-questions
```

## 注意事项

1. 确保 `../data` 目录存在且包含必要的 JSON 文件
2. OpenRouter API 密钥是必需的，用于 AI 批改功能
3. 第一次启动时会自动创建 logs 目录
