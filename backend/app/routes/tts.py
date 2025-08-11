"""
TTS (Text-to-Speech) 语音合成路由
为AI教师聊天功能提供实时语音合成API
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from typing import Optional
import logging
import asyncio
import json

from ..services.tts_service import get_tts_service
from ..core.config import get_settings

router = APIRouter(
    prefix="/api/tts",
    tags=["TTS"],
    responses={
        500: {"description": "语音合成服务内部错误"},
        503: {"description": "语音合成服务不可用"}
    }
)

logger = logging.getLogger(__name__)
settings = get_settings()
tts_service = get_tts_service()


class TTSRequest(BaseModel):
    """TTS请求模型"""
    text: str
    voice: Optional[str] = "zh-HK-HiuMaanNeural"  # 默认使用粤语女声
    language_boost: Optional[str] = "Chinese,Yue"  # 默认粤语增强


class TTSResponse(BaseModel):
    """TTS响应模型"""
    success: bool
    message: str
    audio_url: Optional[str] = None


@router.post("/synthesize-stream")
async def synthesize_stream(request: TTSRequest):
    """
    流式语音合成API
    
    接收文本，返回流式音频数据
    """
    logger.info(f"收到TTS流式合成请求: {request.text[:50]}...")
    
    if not tts_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="语音合成服务不可用，请检查Azure Speech配置"
        )
    
    if not request.text.strip():
        raise HTTPException(
            status_code=400,
            detail="文本内容不能为空"
        )
    
    try:
        async def generate_audio():
            """生成音频流"""
            async for audio_chunk in tts_service.synthesize_text_stream(request.text, request.language_boost):
                yield audio_chunk
        
        return StreamingResponse(
            generate_audio(),
            media_type="audio/wav",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Methods": "*",
            }
        )
        
    except Exception as e:
        logger.error(f"TTS流式合成失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="语音合成失败，请稍后重试"
        )


@router.post("/synthesize")
async def synthesize_audio(request: TTSRequest):
    """
    单次语音合成API
    
    接收文本，返回完整音频文件
    """
    # 安全的日志输出，避免Unicode错误
    try:
        safe_text = request.text[:50].encode('ascii', errors='replace').decode('ascii')
        logger.info(f"收到TTS合成请求: {safe_text}...")
    except Exception:
        logger.info("收到TTS合成请求: [包含特殊字符]")
    
    if not tts_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="语音合成服务不可用，请检查Azure Speech配置"
        )
    
    if not request.text.strip():
        raise HTTPException(
            status_code=400,
            detail="文本内容不能为空"
        )
    
    try:
        # 使用流式合成收集完整音频数据
        audio_data = b""
        chunk_count = 0  # 🔥 DEBUG: 统计块数量
        
        logger.debug(f"开始收集音频数据流...")
        async for chunk in tts_service.synthesize_text_stream(request.text, request.language_boost):
            chunk_count += 1
            chunk_size = len(chunk) if chunk else 0
            logger.debug(f"收到第{chunk_count}个音频块，大小: {chunk_size} bytes")
            audio_data += chunk
        
        logger.info(f"音频数据收集完成，总块数: {chunk_count}，总大小: {len(audio_data)} bytes")
        
        if not audio_data:
            logger.error(f"语音合成失败：未生成音频数据。文本长度: {len(request.text)}, 块数: {chunk_count}")
            raise HTTPException(
                status_code=500,
                detail="语音合成失败，未生成音频数据"
            )
        
        logger.info(f"返回音频数据，大小: {len(audio_data)} bytes")
        return Response(
            content=audio_data,
            media_type="audio/mpeg",  # 🔥 修复：使用正确的MP3 MIME类型
            headers={
                "Content-Disposition": "attachment; filename=synthesized_audio.mp3",
                "Cache-Control": "no-cache",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Methods": "*",
                "Content-Length": str(len(audio_data)),  # 🔥 添加内容长度
            }
        )
        
    except Exception as e:
        logger.error(f"TTS合成失败: {str(e)}")
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail="语音合成失败，请稍后重试"
        )


@router.post("/cancel")
async def cancel_all_tts_tasks():
    """
    取消所有活跃的TTS任务
    
    当用户点击停止按钮时调用
    """
    logger.info("收到取消所有TTS任务的请求")
    
    if not tts_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="TTS服务不可用"
        )
    
    try:
        await tts_service.cancel_all_tasks()
        return {
            "success": True,
            "message": "已取消所有活跃的TTS任务",
            "timestamp": logger.handlers[0].formatter.formatTime(logger.makeRecord(
                name="tts", level=20, pathname="", lineno=0,
                msg="", args=(), exc_info=None
            )) if logger.handlers else None
        }
        
    except Exception as e:
        logger.error(f"取消TTS任务失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="取消TTS任务失败"
        )


@router.get("/health")
async def tts_health():
    """
    TTS服务健康检查
    """
    try:
        is_available = tts_service.is_available()
        
        return {
            "status": "healthy" if is_available else "unavailable",
            "service": "Azure Text-to-Speech",
            "timestamp": logger.handlers[0].formatter.formatTime(logger.makeRecord(
                name="tts", level=20, pathname="", lineno=0,
                msg="", args=(), exc_info=None
            )) if logger.handlers else None,
            "azure_speech_configured": bool(settings.AZURE_SPEECH_KEY and settings.AZURE_SPEECH_REGION),
            "voice": "zh-HK-HiuMaanNeural"
        }
        
    except Exception as e:
        logger.error(f"TTS健康检查失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="TTS服务健康检查失败"
        )


@router.get("/voices")
async def get_available_voices():
    """
    获取可用的语音列表
    """
    # 返回支持的粤语语音列表
    voices = [
        {
            "name": "zh-HK-HiuMaanNeural",
            "display_name": "曉曼 (粵語,女聲)",
            "gender": "Female",
            "locale": "zh-HK",
            "description": "溫柔女聲，適合AI教師角色"
        },
        {
            "name": "zh-HK-WanLungNeural", 
            "display_name": "雲龍 (粵語,男聲)",
            "gender": "Male",
            "locale": "zh-HK",
            "description": "沉穩男聲"
        }
    ]
    
    return {
        "voices": voices,
        "default": "zh-HK-HiuMaanNeural",
        "service_available": tts_service.is_available()
    }