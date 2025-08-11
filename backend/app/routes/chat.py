"""
聊天API路由

本模块实现与AI老师的聊天功能，包括：
- 流式聊天响应
- OpenRouter API集成
- 蘭老師人设和粤语响应

设计原则：
- 流式响应：支持打字机效果
- 异步处理：高性能聊天体验
- 错误处理：完善的异常处理
- 人设一致：蘭老師香港中学英语教师身份
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, AsyncGenerator
import json
import logging
import asyncio
import httpx
from datetime import datetime

from ..core.config import get_settings
from ..core.multilingual_prompts import get_system_prompt, is_supported_language # 🔥 新增：导入多语言提示词

# 创建路由器
router = APIRouter(
    prefix="/api/chat",
    tags=["Chat"],
    responses={
        404: {"description": "资源未找到"},
        500: {"description": "服务器内部错误"}
    }
)

# 日志记录器
logger = logging.getLogger(__name__)

# 获取配置
settings = get_settings()

# 请求和响应模型
class ChatMessage(BaseModel):
    role: str  # "user" 或 "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    conversation_history: List[ChatMessage] = []
    language_boost: str = "Chinese,Yue"  # 🔥 新增：语言增强设置，默认粤语

class ChatResponse(BaseModel):
    response: str
    timestamp: datetime

# 蘭老師系统提示词
TEACHER_SYSTEM_PROMPT = """你係蘭老師，一位經驗豐富嘅香港中學英文老師，專門教授DSE英文科。

**身份特點：**
- 香港中學英文科資深教師，有15年DSE教學經驗
- 溫柔、耐心、專業，深受學生喜愛
- 擅長用簡潔而有用嘅方式解釋英文知識

**語言風格：**
- 主要使用香港粤語（繁體中文）回應
- 語氣親切友善，如同真正嘅老師
- 用詞準確，邏輯清晰

**回應原則（平衡版）：**
- **適中長度**：回答控制在4-6句話，既唔太長又唔太短
- **結構清晰**：簡潔解釋 + 實用例子 + 簡單總結
- **重點突出**：突出1-2個核心要點，但要解釋清楚
- **實用導向**：每個回答都要有實際幫助，唔好太空泛
- **適度展開**：比純粹解釋多少少，但唔好長篇大論

**標準回應模板：**
- **詞彙問題**：解釋意思 + 同義詞對比 + 1-2個實用例子 + 使用提醒
- **語法問題**：簡單規則說明 + 正確示範 + 常見錯誤提醒
- **題目討論**：指出問題 + 解釋原因 + 正確做法 + 實用貼士
- **技巧查詢**：核心方法 + 具體步驟 + 實際應用例子

**題目上下文處理：**
當學生提供題目上下文時，提供：
1. **問題診斷**：指出具體錯誤或要點
2. **原因分析**：用2-3句話說明為何如此
3. **正確方法**：提供具體改進建議
4. **延伸提醒**：簡單補充相關注意事項

**表格使用指引：**
- 比較2個或以上概念時可用表格
- 表格要實用，包含關鍵信息
- 配合文字說明，唔好單純用表格

**回應長度指引：**
- 目標：150-300字（約4-6句話）
- 確保每句話都有價值，唔好廢話
- 簡潔但要講清楚，學生睇完就明白
- 避免過短（少於2句話）或過長（超過500字）

**互動策略：**
- 回答要完整但留有適度空間讓學生追問
- 適當鼓勵學生提出後續問題
- 平衡解答深度同互動性

記住：做一個**簡潔而有用**嘅老師，每個回答都要讓學生真正學到嘢！"""


async def stream_openrouter_response(messages: List[Dict[str, str]], language_boost: str = "Chinese,Yue") -> AsyncGenerator[str, None]:
    """
    调用OpenRouter API获取流式响应
    
    Args:
        messages: 对话消息列表
        language_boost: 语言增强设置，用于选择对应的系统提示词
        
    Yields:
        str: 流式响应的文本片段
    """
    if not settings.OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OpenRouter API密钥未配置"
        )
    
    # 准备API请求
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "DSE AI Teacher"
    }
    
    # 🔥 根据语言设置获取对应的系统提示词
    system_prompt = get_system_prompt(language_boost)
    logger.info(f"使用语言设置: {language_boost}")
    
    # 构建消息列表（包含多语言系统提示词）
    api_messages = [
        {"role": "system", "content": system_prompt}
    ] + messages
    
    payload = {
        "model": "google/gemini-2.5-flash-lite",  # 使用免费的Gemini模型
        "messages": api_messages,
        "stream": True,
        "temperature": 0.7,
        "max_tokens": 15000,
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # 移除 "data: " 前缀
                        
                        if data_str.strip() == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and data["choices"]:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            continue
                            
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenRouter API调用失败: {e.response.status_code}")
        yield f"抱歉，AI服务暂时不可用，请稍后重试。"
        return
    
    except httpx.TimeoutException:
        logger.error("OpenRouter API调用超时")
        yield f"抱歉，AI服务响应超时，请重试。"
        return
    
    except Exception as e:
        logger.error(f"调用OpenRouter API时发生异常: {str(e)}")
        yield f"抱歉，AI服务出现异常：{str(e)}"
        return


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    流式聊天接口
    
    接收用户消息，返回蘭老師的流式响应
    """
    logger.info(f"收到聊天请求: {request.message[:50]}...")
    
    try:
        # 构建对话消息列表
        messages = []
        
        # 添加历史对话
        for msg in request.conversation_history:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # 添加当前用户消息
        messages.append({
            "role": "user",
            "content": request.message
        })
        
        # 定义流式响应生成器
        async def generate_response():
            try:
                buffer = ""
                async for chunk in stream_openrouter_response(messages, request.language_boost):
                    buffer += chunk
                    # 发送Server-Sent Events格式的数据
                    yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                    
                # 发送完成信号
                yield f"data: {json.dumps({'content': '', 'done': True, 'full_response': buffer})}\n\n"
                
            except Exception as e:
                logger.error(f"流式响应生成错误: {str(e)}")
                error_msg = "抱歉，我暫時無法回應你嘅問題，請稍後再試。"
                yield f"data: {json.dumps({'content': error_msg, 'done': True, 'error': True})}\n\n"
        
        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Methods": "*",
            }
        )
        
    except Exception as e:
        logger.error(f"聊天接口发生错误: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"聊天服务出现错误: {str(e)}"
        )