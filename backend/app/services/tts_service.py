"""
Minimax WebSocket Text-to-Speech服务
为AI教师聊天功能提供实时流式语音合成
基于官方WebSocket API文档实现
🔥 新增：任务管理器防止并发冲突
"""

import json
import logging
import asyncio
import ssl
import re
import uuid
from typing import AsyncGenerator, Optional, Dict, Set
import websockets
from ..core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TTSTaskManager:
    """TTS任务管理器 - 防止并发冲突"""
    
    def __init__(self):
        self.active_tasks: Set[str] = set()
        self.task_lock = asyncio.Lock()
        self.max_concurrent_tasks = 3  # 最大并发任务数
        
    async def can_start_task(self) -> bool:
        """检查是否可以启动新任务"""
        async with self.task_lock:
            return len(self.active_tasks) < self.max_concurrent_tasks
    
    async def register_task(self, task_id: str) -> bool:
        """注册新任务"""
        async with self.task_lock:
            if len(self.active_tasks) >= self.max_concurrent_tasks:
                return False
            self.active_tasks.add(task_id)
            logger.info(f"注册TTS任务 {task_id}，当前活跃任务数: {len(self.active_tasks)}")
            return True
    
    async def unregister_task(self, task_id: str):
        """注销任务"""
        async with self.task_lock:
            self.active_tasks.discard(task_id)
            logger.info(f"注销TTS任务 {task_id}，当前活跃任务数: {len(self.active_tasks)}")
    
    async def cancel_all_tasks(self):
        """取消所有任务"""
        async with self.task_lock:
            cancelled_count = len(self.active_tasks)
            self.active_tasks.clear()
            logger.info(f"取消了 {cancelled_count} 个活跃的TTS任务")


class TTSService:
    """Minimax WebSocket流式Text-to-Speech服务类"""
    
    def __init__(self):
        """初始化Minimax WebSocket TTS服务"""
        self.api_key = settings.MINIMAX_API_KEY
        self.group_id = settings.MINIMAX_GROUP_ID
        self.model = settings.MINIMAX_TTS_MODEL
        self.ws_url = "wss://api.minimaxi.com/ws/v1/t2a_v2"
        
        # 🔥 新增：任务管理器
        self.task_manager = TTSTaskManager()
        
        # 检查配置
        if not self.api_key or not self.group_id:
            logger.error("❌ Minimax TTS服务配置不完整:")
            logger.error(f"   MINIMAX_API_KEY: {'✅ 已配置' if self.api_key else '❌ 未配置'}")
            logger.error(f"   MINIMAX_GROUP_ID: {'✅ 已配置' if self.group_id else '❌ 未配置'}")
            logger.error("   请在环境变量或.env文件中配置这些参数")
            self._available = False
        else:
            self._available = True
            logger.info("✅ Minimax WebSocket TTS服务初始化成功")
            logger.info(f"   模型: {self.model}")
            logger.info(f"   WebSocket URL: {self.ws_url}")
    
    def is_available(self) -> bool:
        """检查TTS服务是否可用"""
        if not self._available:
            logger.warning("⚠️ TTS服务不可用 - 请检查MiniMax API配置")
        return self._available
    
    async def cancel_all_tasks(self):
        """取消所有活跃的TTS任务"""
        await self.task_manager.cancel_all_tasks()
    
    def _clean_text_for_speech(self, text: str) -> str:
        """
        清理文本，移除不适合语音合成的内容
        """
        if not text.strip():
            return ""
        
        # 移除Markdown格式
        # 移除代码块
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        # 移除行内代码
        text = re.sub(r'`([^`]*)`', r'\1', text)
        # 移除链接
        text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
        # 移除图片
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        # 移除粗体和斜体标记
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        # 移除markdown列表标记
        text = re.sub(r'^\s*[*\-+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
        # 移除HTML标签
        text = re.sub(r'<[^>]*>', '', text)
        
        # 移除表格内容（检测|符号密集的行）
        lines = text.split('\n')
        clean_lines = []
        for line in lines:
            # 如果一行中|符号过多，可能是表格，跳过
            if line.count('|') >= 3:
                continue
            # 跳过纯符号行
            if re.match(r'^[\s\-\|:=+*_]+$', line):
                continue
            clean_lines.append(line)
        
        text = '\n'.join(clean_lines)
        
        # 清理多余的空白字符
        text = re.sub(r'\n\s*\n', '\n', text)  # 多个换行合并为一个
        text = re.sub(r'\s+', ' ', text)  # 多个空格合并为一个
        text = text.strip()
        
        return text
    
    async def _establish_websocket_connection(self) -> Optional[websockets.WebSocketServerProtocol]:
        """
        建立WebSocket连接
        
        Returns:
            WebSocket连接对象或None（连接失败）
        """
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            # 创建SSL上下文（按照官方文档示例）
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            logger.debug(f"尝试连接WebSocket: {self.ws_url}")
            
            ws = await websockets.connect(
                self.ws_url, 
                extra_headers=headers,  # 🔥 修复：使用extra_headers而不是additional_headers
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5  # 🔥 添加关闭超时
            )
            
            # 等待连接确认
            connected_msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
            connected = json.loads(connected_msg)
            
            if connected.get("event") == "connected_success":
                logger.info("WebSocket连接成功")
                return ws
            else:
                logger.error(f"WebSocket连接失败: {connected}")
                await ws.close()
                return None
                
        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
            return None
    
    async def _start_tts_task(self, websocket, text: str, language_boost: str = "Chinese,Yue") -> bool:
        """
        发送任务开始请求
        
        Args:
            websocket: WebSocket连接
            text: 要合成的文本
            
        Returns:
            bool: 是否成功启动任务
        """
        try:
            start_msg = {
                "event": "task_start",
                "model": self.model,
                "language_boost": language_boost,
                "voice_setting": {
                    "voice_id": "female-shaonv-jingpin",  # 使用乔皮萌妹声音
                    "speed": 1.0,
                    "vol": 1.0,
                    "pitch": 0,
                    "emotion": "happy"
                },
                "audio_setting": {
                    "sample_rate": 32000,
                    "bitrate": 128000,
                    "format": "mp3",
                    "channel": 1
                }
            }
            
            logger.debug(f"发送task_start: {json.dumps(start_msg, ensure_ascii=False)}")
            await websocket.send(json.dumps(start_msg))
            
            # 等待任务启动确认
            response_msg = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            response = json.loads(response_msg)
            
            logger.debug(f"收到task_start响应: {response}")
            
            if response.get("event") == "task_started":
                logger.info("TTS任务启动成功")
                return True
            else:
                logger.error(f"TTS任务启动失败: {response}")
                return False
                
        except Exception as e:
            logger.error(f"启动TTS任务失败: {e}")
            return False
    
    async def _continue_tts_task(self, websocket, text: str, task_id: str) -> AsyncGenerator[bytes, None]:
        """
        发送继续请求并收集音频数据
        
        Args:
            websocket: WebSocket连接
            text: 要合成的文本
            task_id: 任务ID
            
        Yields:
            bytes: 音频数据块
        """
        try:
            # 检查任务是否仍然活跃
            if task_id not in self.task_manager.active_tasks:
                logger.warning(f"任务 {task_id} 已被取消，停止音频生成")
                return
            
            # 发送task_continue请求
            continue_msg = {
                "event": "task_continue",
                "text": text
            }
            
            logger.debug(f"发送task_continue: {json.dumps(continue_msg, ensure_ascii=False)}")
            await websocket.send(json.dumps(continue_msg))
            
            chunk_counter = 0
            
            # 接收音频数据流
            while True:
                try:
                    # 检查任务是否被取消
                    if task_id not in self.task_manager.active_tasks:
                        logger.warning(f"任务 {task_id} 已被取消，停止音频接收")
                        break
                    
                    response_msg = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    response = json.loads(response_msg)
                    
                    logger.debug(f"收到响应事件: {response.get('event', 'unknown')}")
                    
                    # 检查是否有音频数据
                    if "data" in response and "audio" in response["data"]:
                        audio_hex = response["data"]["audio"]
                        
                        if audio_hex:
                            chunk_counter += 1
                            logger.debug(f"音频块 #{chunk_counter}")
                            logger.debug(f"编码长度: {len(audio_hex)} 字节")
                            
                            # Hex解码音频数据
                            try:
                                audio_bytes = bytes.fromhex(audio_hex)
                                logger.debug(f"解码后音频长度: {len(audio_bytes)} 字节")
                                yield audio_bytes
                            except ValueError as e:
                                logger.error(f"音频数据Hex解码失败: {e}")
                                continue
                    
                    # 检查是否完成
                    if response.get("is_final", False):
                        logger.info(f"TTS合成完成，共产出 {chunk_counter} 个音频块")
                        break
                        
                except asyncio.TimeoutError:
                    logger.warning("WebSocket接收超时，结束流式传输")
                    break
                except json.JSONDecodeError as e:
                    logger.error(f"JSON解析失败: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"继续TTS任务失败: {e}")
    
    async def _close_websocket_connection(self, websocket):
        """
        关闭WebSocket连接
        
        Args:
            websocket: WebSocket连接
        """
        try:
            if websocket:
                # 检查连接状态
                if not websocket.closed:
                    try:
                        # 发送任务结束信号
                        finish_msg = {"event": "task_finish"}
                        await asyncio.wait_for(
                            websocket.send(json.dumps(finish_msg)), 
                            timeout=2.0
                        )
                    except Exception:
                        # 如果发送失败，连接可能已经关闭
                        pass
                
                # 关闭连接
                try:
                    await asyncio.wait_for(websocket.close(), timeout=3.0)
                    logger.debug("WebSocket连接已关闭")
                except Exception:
                    logger.debug("WebSocket连接关闭超时或已断开")
                    
        except Exception as e:
            logger.warning(f"关闭WebSocket连接时出错: {e}")
    
    async def synthesize_text_stream(self, text: str, language_boost: str = "Chinese,Yue") -> AsyncGenerator[bytes, None]:
        """
        流式语音合成主方法
        
        Args:
            text: 要合成的文本
            language_boost: 语言增强设置，如"Chinese,Yue"、"Chinese"、"Japanese"等
            
        Yields:
            bytes: 音频数据块
        """
        if not self._available:
            logger.warning("Minimax TTS服务不可用，跳过语音合成")
            return
        
        # 🔥 生成唯一任务ID
        task_id = str(uuid.uuid4())[:8]
        
        # 🔥 检查并发限制
        if not await self.task_manager.can_start_task():
            logger.warning(f"TTS并发任务已达上限，拒绝任务 {task_id}")
            return
        
        # 🔥 注册任务
        if not await self.task_manager.register_task(task_id):
            logger.warning(f"无法注册TTS任务 {task_id}")
            return
        
        try:
            # 清理文本
            cleaned_text = self._clean_text_for_speech(text)
            if not cleaned_text:
                logger.debug("文本清理后为空，跳过合成")
                return
                
            # 基本文本验证
            if len(cleaned_text.strip()) < 2:
                logger.debug(f"跳过过短文本: {cleaned_text}")
                return
                
            # 过滤纯符号文本
            if re.match(r'^[\s\-\|:=+*_.,!?;()【】\[\]{}""'']+$', cleaned_text):
                logger.debug(f"跳过纯符号文本: {cleaned_text}")
                return
            
            # 安全的日志输出
            try:
                safe_text = cleaned_text[:50].encode('ascii', errors='replace').decode('ascii')
                logger.info(f"开始TTS任务 {task_id}: {safe_text}...")
            except Exception:
                logger.info(f"开始TTS任务 {task_id}: [包含特殊字符]")
            
            websocket = None
            try:
                # 建立WebSocket连接
                websocket = await self._establish_websocket_connection()
                if not websocket:
                    logger.error(f"任务 {task_id} 无法建立WebSocket连接")
                    return
                
                # 启动TTS任务
                if not await self._start_tts_task(websocket, cleaned_text, language_boost):
                    logger.error(f"任务 {task_id} 无法启动TTS任务")
                    return
                
                # 处理音频流
                async for audio_chunk in self._continue_tts_task(websocket, cleaned_text, task_id):
                    yield audio_chunk
                    
            except Exception as e:
                logger.error(f"任务 {task_id} WebSocket TTS合成过程中发生错误: {e}")
            finally:
                # 确保连接关闭
                if websocket:
                    await self._close_websocket_connection(websocket)
                    
        finally:
            # 🔥 确保任务被注销
            await self.task_manager.unregister_task(task_id)


# 全局TTS服务实例
_tts_service = None

def get_tts_service() -> TTSService:
    """获取TTS服务单例"""
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service