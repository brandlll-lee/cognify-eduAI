# DSE AI Teacher API

DSE 英文阅读理解 AI 老师后端 API，提供完整的题目数据和智能批改服务。

## 🌟 功能特性

### 核心功能

- **题目数据获取**: 提供 DSE 真题阅读文章和题目数据
- **智能批改**: 基于 Claude 3.5 Sonnet 的 AI 老师批改系统
- **详细解析**: 针对错题提供原文引用和解题思路
- **能力分析**: 个性化的学习能力评估和建议

### 技术特性

- **高性能**: 基于 FastAPI 的异步 API 框架
- **类型安全**: 完整的 Pydantic 数据验证
- **错误处理**: 完善的异常处理和日志记录
- **文档完整**: 自动生成的 API 文档
- **可扩展**: 模块化设计，易于扩展

## 🛠️ 技术栈

- **框架**: FastAPI 0.116.1
- **数据验证**: Pydantic 2.11.7
- **HTTP 客户端**: httpx 0.28.1
- **AI 服务**: OpenRouter API (Claude 3.5 Sonnet)
- **配置管理**: pydantic-settings
- **文件处理**: aiofiles

## 📦 项目结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # 主应用入口
│   ├── core/
│   │   └── config.py        # 配置管理
│   ├── models/
│   │   └── dse_models.py    # 数据模型定义
│   ├── routes/
│   │   └── dse.py           # API路由
│   └── services/
│       └── ai_teacher.py    # AI老师服务
├── requirements.txt         # 项目依赖
├── run.py                  # 启动脚本
└── README.md              # 项目文档
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 环境配置

创建 `.env` 文件：

```env
# OpenRouter API密钥（必需）
OPENROUTER_API_KEY=your_openrouter_api_key_here

# 服务器配置
HOST=0.0.0.0
PORT=8000
DEBUG=true

# AI模型配置
DEFAULT_MODEL=anthropic/claude-3.5-sonnet
MODEL_TEMPERATURE=0.1

# 日志配置
LOG_LEVEL=INFO
```

### 3. 启动服务

```bash
# 使用启动脚本
python run.py

# 或者直接使用uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 访问 API

- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health
- **ReDoc 文档**: http://localhost:8000/redoc

## 📚 API 接口

### 获取 Demo 题目数据

```http
GET /api/dse/demo-questions
```

返回完整的 DSE 阅读理解题目数据，包括文章内容和 3 道真题。

### 提交答案进行批改

```http
POST /api/dse/submit
Content-Type: application/json

{
  "answers": [
    {
      "question_id": "q11",
      "type": "multiple-choice",
      "selected_option": "A"
    }
  ],
  "start_time": "2024-01-01T10:00:00Z",
  "end_time": "2024-01-01T10:30:00Z"
}
```

返回提交 ID，启动后台批改流程。

### 查询批改结果

```http
GET /api/dse/results/{submission_id}
```

根据提交 ID 查询批改进度和结果。

## 🤖 AI 老师功能

### 智能批改能力

- **多题型支持**: 选择题、填空题、时序排列题
- **精确评分**: 严格按照标准答案评分
- **详细解析**: 包含原文引用和解题思路

### 教学分析功能

- **能力评估**: 6 个维度的技能分析
- **个性化建议**: 针对薄弱环节的学习建议
- **错误分析**: 深入分析错误原因

### Prompt 设计特色

- **角色定位**: 专业的 DSE 英语老师身份
- **教学导向**: 不仅判断对错，更注重教学价值
- **结构化输出**: 标准 JSON 格式，便于前端展示

## 🔧 配置说明

### 核心配置项

| 配置项               | 说明                | 默认值                        | 必需 |
| -------------------- | ------------------- | ----------------------------- | ---- |
| `OPENROUTER_API_KEY` | OpenRouter API 密钥 | -                             | ✅   |
| `DEFAULT_MODEL`      | AI 模型名称         | `anthropic/claude-3.5-sonnet` | ❌   |
| `MODEL_TEMPERATURE`  | 模型温度参数        | `0.1`                         | ❌   |
| `HOST`               | 服务器主机          | `0.0.0.0`                     | ❌   |
| `PORT`               | 服务器端口          | `8000`                        | ❌   |

### 日志配置

系统会自动创建 `logs/app.log` 文件记录运行日志。日志级别可通过 `LOG_LEVEL` 环境变量配置。

## 🛡️ 错误处理

### 错误响应格式

```json
{
  "error": true,
  "message": "错误描述",
  "detail": "详细错误信息",
  "code": "ERROR_CODE"
}
```

### 常见错误码

- `VALIDATION_ERROR`: 请求参数验证失败
- `HTTP_404`: 资源未找到
- `HTTP_500`: 服务器内部错误
- `INTERNAL_ERROR`: 未处理的异常

## 🔄 降级策略

当 AI 服务不可用时，系统会自动启用降级模式：

- 提供基础的答案对比功能
- 返回简化的批改结果
- 确保系统可用性

## 📈 性能优化

### 异步处理

- 使用 FastAPI 的异步特性
- 批改过程在后台执行
- 支持并发请求处理

### 缓存策略

- 题目数据缓存（计划中）
- Redis 集成支持（预留）

## 🧪 开发指南

### 添加新题型

1. 在 `dse_models.py` 中扩展 `QuestionType` 枚举
2. 更新 `UserAnswer` 模型支持新答案格式
3. 在 `ai_teacher.py` 中添加对应的处理逻辑

### 自定义 AI 模型

1. 修改 `DEFAULT_MODEL` 配置
2. 调整 `MODEL_TEMPERATURE` 等参数
3. 根据需要优化 Prompt 模板

## 🐛 问题排查

### 常见问题

**Q: AI 批改失败怎么办？**
A: 检查 `OPENROUTER_API_KEY` 是否正确配置，查看日志文件获取详细错误信息。

**Q: 题目数据加载失败？**
A: 确保 `../data/` 目录下的 JSON 文件存在且格式正确。

**Q: 服务启动失败？**
A: 检查端口是否被占用，虚拟环境是否正确激活。

### 日志分析

```bash
# 查看实时日志
tail -f logs/app.log

# 搜索错误日志
grep "ERROR" logs/app.log
```

## 🚀 部署建议

### 生产环境

- 使用 Gunicorn 或 uWSGI 作为 WSGI 服务器
- 配置 Nginx 作为反向代理
- 设置环境变量而非.env 文件
- 启用日志轮转

### Docker 部署

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "run.py"]
```

## 📞 技术支持

如有问题或建议，请通过以下方式联系：

- 创建 Issue 进行问题反馈
- 查看 API 文档获取详细接口说明
- 检查日志文件进行问题排查

---

Built with ❤️ for education | DSE AI Teacher API v1.0.0
