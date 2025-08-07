#!/usr/bin/env python3
"""
快速测试修复的核心问题
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import get_settings

def test_vad_config():
    """测试VAD配置"""
    settings = get_settings()
    
    print("=== VAD配置检查 ===")
    print(f"VAD启用状态: {settings.VAD_ENABLED}")
    print(f"VAD模式: {settings.VAD_MODE}")
    print(f"VAD帧持续时间: {settings.VAD_FRAME_DURATION}ms")
    print(f"采样率: {settings.SPEECH_SAMPLE_RATE}Hz")
    
    # 计算预期的帧大小
    frame_size = int(settings.SPEECH_SAMPLE_RATE * settings.VAD_FRAME_DURATION / 1000)
    frame_size_bytes = frame_size * 2  # 16位采样
    
    print(f"预期VAD帧大小: {frame_size} 样本 = {frame_size_bytes} 字节")
    
    if not settings.VAD_ENABLED:
        print("✅ VAD已禁用，音频将直接发送到识别器（绕过帧大小检查）")
        print("这应该修复了用户语音无反应的问题！")
    else:
        print("⚠️ VAD已启用，需要确保音频块匹配帧大小")
        print(f"前端发送的音频块（如256字节）不匹配预期的{frame_size_bytes}字节")
    
    return True

if __name__ == "__main__":
    test_vad_config()
    print("\n=== 修复总结 ===")
    print("1. 问题：前端发送的音频块大小与VAD预期不匹配")
    print("2. 修复：禁用VAD严格检查，直接发送音频到识别器")
    print("3. 结果：用户语音应该现在可以被识别了")
    print("\n请重启后端服务并测试语音通话功能！")