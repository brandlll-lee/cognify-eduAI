#!/usr/bin/env python3
"""
自动安装Azure语音服务依赖
基于Microsoft官方文档推荐的包版本
"""

import subprocess
import sys
import os

def run_command(command):
    """运行命令并显示输出"""
    print(f"🔄 执行：{command}")
    try:
        result = subprocess.run(command, shell=True, check=True, 
                              capture_output=True, text=True)
        print(f"✅ 成功：{result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 失败：{e.stderr.strip()}")
        return False

def install_azure_dependencies():
    """安装Azure语音服务依赖"""
    print("🚀 开始安装Azure语音服务依赖")
    print("=" * 50)
    
    # 核心依赖包列表（基于官方文档）
    packages = [
        "azure-cognitiveservices-speech>=1.40.0",  # Azure语音SDK
        "webrtcvad>=2.0.10",                       # 语音活动检测
        "numpy>=1.24.0",                           # 数值计算
        "scipy>=1.10.0",                           # 科学计算
        "fastapi>=0.116.1",                        # Web框架
        "uvicorn>=0.35.0",                         # ASGI服务器
        "websockets>=11.0",                        # WebSocket支持
        "pydantic>=2.11.7",                        # 数据验证
        "pydantic-settings>=2.10.1",               # 配置管理
        "httpx>=0.28.1",                           # HTTP客户端
        "python-dotenv>=1.1.1",                    # 环境变量
        "aiofiles>=23.2.1",                        # 异步文件操作
        "asyncio-mqtt>=0.14.0"                     # MQTT异步支持
    ]
    
    success_count = 0
    
    for package in packages:
        print(f"\n📦 安装 {package}")
        if run_command(f"pip install {package}"):
            success_count += 1
        else:
            print(f"⚠️  {package} 安装失败，继续安装其他包...")
    
    print(f"\n📊 安装结果：{success_count}/{len(packages)} 成功")
    
    if success_count == len(packages):
        print("🎉 所有依赖安装成功！")
        return True
    else:
        print("⚠️  部分依赖安装失败，请手动检查")
        return False

def verify_installation():
    """验证安装结果"""
    print("\n🔍 验证安装结果")
    print("=" * 50)
    
    try:
        import azure.cognitiveservices.speech as speechsdk
        print(f"✅ Azure语音SDK v{speechsdk.__version__}")
    except ImportError:
        print("❌ Azure语音SDK导入失败")
        return False
    
    try:
        import webrtcvad
        print("✅ WebRTC VAD")
    except ImportError:
        print("❌ WebRTC VAD导入失败")
    
    try:
        import numpy as np
        print(f"✅ NumPy v{np.__version__}")
    except ImportError:
        print("❌ NumPy导入失败")
    
    print("✅ 基础验证完成")
    return True

def main():
    """主函数"""
    print("🔧 Azure语音服务依赖安装器")
    print("基于Microsoft官方文档：")
    print("https://learn.microsoft.com/en-us/azure/ai-services/speech-service/")
    print("=" * 70)
    
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ 需要Python 3.8或更高版本")
        return 1
    
    print(f"✅ Python版本：{sys.version}")
    
    # 升级pip
    print("\n🔄 升级pip...")
    run_command("python -m pip install --upgrade pip")
    
    # 安装依赖
    if install_azure_dependencies():
        print("\n🎯 运行验证测试...")
        if verify_installation():
            print("\n🎉 安装和验证完成！")
            print("现在可以运行：python test_azure_sdk.py")
            return 0
        else:
            print("\n⚠️  验证失败，请检查安装")
            return 1
    else:
        print("\n❌ 安装失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())