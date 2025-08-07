# Azure 语音服务安装和配置指南

基于 Microsoft 官方文档：

- [Azure AI Speech Service](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-to-text)
- [语音识别实现](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-recognize-speech?pivots=programming-language-python)
- [语音合成实现](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-speech-synthesis?pivots=programming-language-python)

## 🚀 快速安装

### 方法 1：自动安装脚本

```bash
cd backend
python install_dependencies.py
```

### 方法 2：手动安装

```bash
cd backend
# 激活虚拟环境
.\hkeduai\Scripts\activate

# 安装Azure语音SDK
pip install azure-cognitiveservices-speech>=1.40.0

# 安装其他依赖
pip install -r requirements.txt

# 验证安装
python test_azure_sdk.py
```

## 🔧 Azure 语音服务配置

### 1. 创建 Azure 语音资源

1. 登录 [Azure Portal](https://portal.azure.com)
2. 创建新的"语音服务"资源
3. 获取密钥和区域信息

### 2. 配置环境变量

复制 `env_example.txt` 为 `.env`：

```bash
copy env_example.txt .env
```

编辑 `.env` 文件，填入 Azure 配置：

```env
# Azure Speech Services配置
AZURE_SPEECH_KEY="your_actual_speech_key_here"
AZURE_SPEECH_REGION="eastasia"  # 或你的实际区域

# 语音服务配置
SPEECH_LANGUAGE="zh-CN"
SPEECH_VOICE_NAME="zh-CN-XiaoxiaoNeural"
```

### 3. 支持的语言和语音

根据[官方语言支持文档](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support)：

**语音识别支持的语言：**

- `zh-CN` - 中文（简体）
- `en-US` - 英语（美国）
- `zh-HK` - 中文（香港）
- `zh-TW` - 中文（台湾）

**语音合成支持的声音：**

- `zh-CN-XiaoxiaoNeural` - 中文女声（推荐）
- `zh-CN-YunxiNeural` - 中文男声
- `zh-CN-YunyangNeural` - 中文男声

## 🧪 测试验证

### 1. 基础依赖测试

```bash
python test_azure_sdk.py
```

### 2. 启动后端服务

```bash
uvicorn app.main:app --reload --port 8001
```

### 3. 测试语音功能

访问前端应用，点击语音通话按钮进行测试。

## 🐛 常见问题排除

### 问题 1：`ModuleNotFoundError: No module named 'azure'`

**解决方案：**

```bash
pip install azure-cognitiveservices-speech>=1.40.0
```

### 问题 2：语音合成初始化失败

**可能原因：**

- Azure 密钥或区域配置错误
- 网络连接问题
- 权限问题

**解决方案：**

1. 验证 Azure 配置
2. 检查网络连接
3. 确认 Azure 资源权限

### 问题 3：语音识别无响应

**可能原因：**

- 音频格式不匹配
- 麦克风权限问题
- WebSocket 连接问题

**解决方案：**

1. 检查浏览器麦克风权限
2. 验证 WebSocket 连接
3. 查看浏览器控制台错误

## 📊 性能优化

基于[官方性能指导](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-lower-speech-synthesis-latency)：

### 语音合成延迟优化

- 使用 MP3 格式：`Audio16Khz32KBitRateMonoMp3`
- 启用压缩传输：`SynthEnableCompressedAudioTransmission`
- 合理设置音频格式

### 语音识别性能优化

- 调整分段超时：`Speech_SegmentationSilenceTimeoutMs`
- 禁用音频日志：`SpeechServiceConnection_EnableAudioLogging`
- 使用合适的采样率：16kHz

## 📖 相关文档

- [Azure 语音服务概述](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-to-text)
- [实时语音识别](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-recognize-speech?pivots=programming-language-python)
- [语音合成指南](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-speech-synthesis?pivots=programming-language-python)
- [性能优化指南](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-lower-speech-synthesis-latency)
- [语言和语音支持](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support)

## 🎯 下一步

1. 运行安装脚本：`python install_dependencies.py`
2. 配置环境变量：编辑 `.env` 文件
3. 运行测试：`python test_azure_sdk.py`
4. 启动服务：`uvicorn app.main:app --reload --port 8001`
5. 测试语音功能
