# AI英语复述评测系统 - API文档与调用方式

**版本**: 1.0  
**基础URL**: `http://127.0.0.1:8000`  
**协议**: HTTP/HTTPS  
**数据格式**: JSON  

## 📋 API概述

AI英语复述评测系统提供RESTful API接口，支持英语复述练习的自动化评测。系统采用异步处理架构，通过语音识别和AI分析技术，为用户提供详细的复述质量评估和改进建议。

### 核心特性
- **异步处理**: 支持大文件音频的后台处理
- **智能分析**: 基于Google Gemini的深度语言分析
- **状态跟踪**: 完整的任务状态管理
- **批量评测**: 支持多句子的综合分析

### 认证方式
当前版本无需认证，直接调用API接口。

---

## 🔗 API接口列表

| 接口 | 方法 | 路径 | 描述 |
|------|------|------|------|
| 单句评测 | POST | `/evaluate-single-card` | 提交音频进行复述评测 |
| 查询结果 | GET | `/get-single-card-result/{round_id}/{card_id}` | 查询单句评测结果 |
| 总结报告 | GET | `/get-round-summary/{round_id}` | 获取整轮练习总结 |
| API文档 | GET | `/docs` | 交互式API文档 |

---

## 📝 接口详细规范

### 1. 单句评测接口

**接口描述**: 提交标准音频和用户复述音频，创建异步评测任务。

```http
POST /evaluate-single-card
Content-Type: multipart/form-data
```

#### 请求参数

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `round_id` | string | ✅ | 练习轮次标识符，用于关联多个句子 |
| `card_id` | string | ✅ | 句子卡片标识符，在同一轮次中唯一 |
| `practice_audio` | file | ✅ | 用户复述的音频文件（WAV格式） |
| `original_audio` | file | ✅ | 标准发音的音频文件（WAV格式） |

#### 响应格式

**成功响应** (202 Accepted):
```json
{
  "message": "Job submitted and is pending evaluation."
}
```

**错误响应**:
- **409 Conflict**: 任务已存在
```json
{
  "detail": "Job for this round_id and card_id already exists."
}
```

- **500 Internal Server Error**: 服务器内部错误
```json
{
  "detail": "Failed to create job record in database."
}
```

#### 调用示例

**Python requests**:
```python
import requests

url = "http://127.0.0.1:8000/evaluate-single-card"

# 准备文件和数据
files = {
    'practice_audio': open('user_recording.wav', 'rb'),
    'original_audio': open('standard_audio.wav', 'rb')
}
data = {
    'round_id': 'demo_round_001',
    'card_id': 'card_01'
}

# 发送请求
response = requests.post(url, files=files, data=data)
print(f"状态码: {response.status_code}")
print(f"响应: {response.json()}")

# 关闭文件
files['practice_audio'].close()
files['original_audio'].close()
```

**cURL**:
```bash
curl -X POST "http://127.0.0.1:8000/evaluate-single-card" \
  -F "round_id=demo_round_001" \
  -F "card_id=card_01" \
  -F "practice_audio=@user_recording.wav" \
  -F "original_audio=@standard_audio.wav"
```

---

### 2. 查询结果接口

**接口描述**: 查询单句评测任务的状态和结果。

```http
GET /get-single-card-result/{round_id}/{card_id}
```

#### 路径参数

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `round_id` | string | ✅ | 练习轮次标识符 |
| `card_id` | string | ✅ | 句子卡片标识符 |

#### 响应格式

**成功响应** (200 OK):
```json
{
  "round_id": "demo_round_001",
  "card_id": "card_01",
  "status": "COMPLETED",
  "result": {
    "evaluation_report": {
      "meaning_fidelity": {
        "assessment": "核心意思已准确表达，但遗漏了一个关键细节。",
        "missing_details": ["时间状语'yesterday'未在复述中体现"],
        "added_inaccuracies": []
      },
      "expression_comparison": {
        "summary": "您的表达清晰，但原文的表达更地道。",
        "original_highlight": "原文中的'tackle the issue'是一个非常地道的搭配。",
        "user_highlight": "您使用的'deal with the problem'也是一个很好的同义替换。"
      },
      "fluency_and_rhythm": {
        "assessment": "整体节奏因逐词朗读而显得生硬，缺少自然的连贯性。"
      },
      "critical_pronunciation_errors": [
        {
          "word": "three",
          "issue": "'three'中的/θ/音发得更像/s/，可能会被听成'see'。"
        }
      ],
      "overall_score": 75
    },
    "source_data": {
      "original_asr": {
        "text": "I need to tackle this issue today.",
        "words": [...]
      },
      "practice_asr": {
        "text": "I need to deal with this problem.",
        "words": [...]
      }
    }
  },
  "error_message": null
}
```

#### 任务状态说明

| 状态 | 描述 |
|------|------|
| `PENDING` | 任务已提交，等待处理 |
| `PROCESSING` | 正在处理中（语音识别和AI分析） |
| `COMPLETED` | 处理完成，结果可用 |
| `FAILED` | 处理失败，查看error_message |

**错误响应**:
- **404 Not Found**: 任务不存在
```json
{
  "detail": "Job not found."
}
```

#### 调用示例

**Python requests**:
```python
import requests
import time

def poll_result(round_id, card_id, max_wait=300):
    url = f"http://127.0.0.1:8000/get-single-card-result/{round_id}/{card_id}"
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        response = requests.get(url)
        if response.status_code == 200:
            result = response.json()
            status = result['status']
            
            if status == 'COMPLETED':
                print("评测完成！")
                return result
            elif status == 'FAILED':
                print(f"评测失败: {result['error_message']}")
                return result
            else:
                print(f"当前状态: {status}，继续等待...")
                time.sleep(10)  # 等待10秒后重试
        else:
            print(f"查询失败: {response.status_code}")
            break
    
    print("查询超时")
    return None

# 使用示例
result = poll_result('demo_round_001', 'card_01')
if result and result['status'] == 'COMPLETED':
    score = result['result']['evaluation_report']['overall_score']
    print(f"评测得分: {score}")
```

---

### 3. 总结报告接口

**接口描述**: 获取整轮练习的综合分析报告，包含模式识别和改进建议。

```http
GET /get-round-summary/{round_id}
```

#### 路径参数

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `round_id` | string | ✅ | 练习轮次标识符 |

#### 响应格式

**成功响应** (200 OK):
```json
{
  "performance_overview": {
    "comment": "本轮在意义传达上表现良好，但在语音连贯性方面需要改进。",
    "final_score": 78
  },
  "key_patterns_analysis": [
    {
      "pattern_id": 1,
      "observation": "在多个句子中，您将带有连读的语块复述为孤立的单词，遗漏了关键的语法信息。",
      "possible_cause": "这很可能是因为您自身的口语习惯倾向于'逐词朗读'，导致您的听觉系统对母语者自然的连读现象不敏感。"
    },
    {
      "pattern_id": 2,
      "observation": "对于包含弱读音节的功能词（如'the', 'of', 'to'），您倾向于按重读方式复述。",
      "possible_cause": "因为您不习惯弱读这些词，所以当听到时，大脑可能无法快速解码其在句中的实际作用。"
    }
  ],
  "vocabulary_and_expression_focus": {
    "items": [
      {
        "en": "tackle the issue",
        "zh": "解决问题",
        "note": "一个地道的动词短语，您成功意译为'deal with'，表达准确。"
      },
      {
        "en": "connected speech",
        "zh": "连读语音",
        "note": "您对此概念的理解需要加强，这影响了听力理解。"
      }
    ],
    "native_speech_insight": "本轮原句中普遍存在辅音+元音连读现象，这是提升听力理解和口语自然度的关键。(可搜索: 'Connected Speech Linking')"
  }
}
```

**错误响应**:
- **404 Not Found**: 没有完成的评测
```json
{
  "detail": "No completed evaluations found for this round yet."
}
```

- **503 Service Unavailable**: Gemini服务不可用
```json
{
  "detail": "Gemini client is not available."
}
```

#### 调用示例

**Python requests**:
```python
import requests

def get_round_summary(round_id):
    url = f"http://127.0.0.1:8000/get-round-summary/{round_id}"
    
    try:
        response = requests.get(url, timeout=180)  # 3分钟超时
        if response.status_code == 200:
            summary = response.json()
            print(f"整轮得分: {summary['performance_overview']['final_score']}")
            print(f"总体评价: {summary['performance_overview']['comment']}")
            
            # 显示关键模式分析
            for pattern in summary['key_patterns_analysis']:
                print(f"\n模式 {pattern['pattern_id']}:")
                print(f"观察: {pattern['observation']}")
                print(f"原因: {pattern['possible_cause']}")
            
            return summary
        else:
            print(f"获取总结失败: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.Timeout:
        print("请求超时，总结分析可能需要更长时间")
        return None
    except Exception as e:
        print(f"请求异常: {e}")
        return None

# 使用示例
summary = get_round_summary('demo_round_001')
```

---

### 4. API文档接口

**接口描述**: 访问FastAPI自动生成的交互式API文档。

```http
GET /docs
```

#### 功能特性
- **交互式测试**: 直接在浏览器中测试API
- **参数验证**: 实时参数格式检查
- **响应预览**: 查看完整的响应结构
- **认证支持**: 支持API密钥等认证方式

#### 访问方式
直接在浏览器中访问: `http://127.0.0.1:8000/docs`

---

## 🚀 完整调用流程示例

### Python完整示例

```python
import requests
import time
import json

class RetellingEvaluator:
    def __init__(self, base_url="http://127.0.0.1:8000"):
        self.base_url = base_url
    
    def submit_evaluation(self, round_id, card_id, practice_audio_path, original_audio_path):
        """提交评测任务"""
        url = f"{self.base_url}/evaluate-single-card"
        
        with open(practice_audio_path, 'rb') as practice_file, \
             open(original_audio_path, 'rb') as original_file:
            
            files = {
                'practice_audio': practice_file,
                'original_audio': original_file
            }
            data = {
                'round_id': round_id,
                'card_id': card_id
            }
            
            response = requests.post(url, files=files, data=data)
            return response.status_code == 202
    
    def wait_for_result(self, round_id, card_id, max_wait=300):
        """等待评测结果"""
        url = f"{self.base_url}/get-single-card-result/{round_id}/{card_id}"
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            response = requests.get(url)
            if response.status_code == 200:
                result = response.json()
                if result['status'] == 'COMPLETED':
                    return result
                elif result['status'] == 'FAILED':
                    raise Exception(f"评测失败: {result['error_message']}")
                else:
                    time.sleep(10)
            else:
                raise Exception(f"查询失败: {response.status_code}")
        
        raise TimeoutError("等待结果超时")
    
    def get_summary(self, round_id):
        """获取总结报告"""
        url = f"{self.base_url}/get-round-summary/{round_id}"
        response = requests.get(url, timeout=180)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"获取总结失败: {response.status_code} - {response.text}")
    
    def evaluate_round(self, round_id, audio_pairs):
        """评测一轮完整的练习"""
        print(f"开始评测轮次: {round_id}")
        
        # 1. 提交所有任务
        for card_id, (practice_path, original_path) in audio_pairs.items():
            print(f"提交 {card_id}...")
            success = self.submit_evaluation(round_id, card_id, practice_path, original_path)
            if not success:
                print(f"提交 {card_id} 失败")
                continue
        
        # 2. 等待所有结果
        results = {}
        for card_id in audio_pairs.keys():
            print(f"等待 {card_id} 结果...")
            try:
                result = self.wait_for_result(round_id, card_id)
                results[card_id] = result
                score = result['result']['evaluation_report']['overall_score']
                print(f"{card_id} 完成，得分: {score}")
            except Exception as e:
                print(f"{card_id} 处理失败: {e}")
        
        # 3. 获取总结报告
        if results:
            print("生成总结报告...")
            try:
                summary = self.get_summary(round_id)
                print(f"整轮得分: {summary['performance_overview']['final_score']}")
                return results, summary
            except Exception as e:
                print(f"获取总结失败: {e}")
                return results, None
        
        return results, None

# 使用示例
if __name__ == "__main__":
    evaluator = RetellingEvaluator()
    
    # 定义音频文件对
    audio_pairs = {
        'card_01': ('sample_audio/practice_1.wav', 'sample_audio/original_1.wav'),
        'card_02': ('sample_audio/practice_2.wav', 'sample_audio/original_2.wav'),
        'card_03': ('sample_audio/practice_3.wav', 'sample_audio/original_3.wav')
    }
    
    # 执行评测
    results, summary = evaluator.evaluate_round('demo_round_001', audio_pairs)
    
    # 输出结果
    print("\n=== 详细结果 ===")
    for card_id, result in results.items():
        if result:
            report = result['result']['evaluation_report']
            print(f"{card_id}: {report['overall_score']}分")
            print(f"  意义保真度: {report['meaning_fidelity']['assessment']}")
    
    if summary:
        print("\n=== 总结报告 ===")
        print(f"整体表现: {summary['performance_overview']['comment']}")
        for pattern in summary['key_patterns_analysis']:
            print(f"模式{pattern['pattern_id']}: {pattern['observation']}")
```

---

## ⚠️ 错误处理和最佳实践

### 常见错误码

| 状态码 | 错误类型 | 处理建议 |
|--------|----------|----------|
| 400 | 请求参数错误 | 检查参数格式和必填字段 |
| 404 | 资源不存在 | 确认round_id和card_id正确 |
| 409 | 任务冲突 | 任务已存在，可直接查询结果 |
| 500 | 服务器内部错误 | 检查服务器日志，重试请求 |
| 503 | 服务不可用 | AI服务暂时不可用，稍后重试 |

### 最佳实践

#### 1. 音频文件要求
- **格式**: WAV格式（推荐）
- **采样率**: 16kHz或更高
- **时长**: 建议10-60秒
- **质量**: 清晰无噪音

#### 2. 轮询策略
```python
# 推荐的轮询间隔
POLL_INTERVALS = {
    'initial': 10,    # 前30秒每10秒查询一次
    'medium': 30,     # 30秒-2分钟每30秒查询一次
    'long': 60        # 2分钟后每60秒查询一次
}

def smart_poll(round_id, card_id, max_wait=300):
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        elapsed = time.time() - start_time
        
        # 动态调整轮询间隔
        if elapsed < 30:
            interval = POLL_INTERVALS['initial']
        elif elapsed < 120:
            interval = POLL_INTERVALS['medium']
        else:
            interval = POLL_INTERVALS['long']
        
        # 查询结果
        result = check_result(round_id, card_id)
        if result['status'] in ['COMPLETED', 'FAILED']:
            return result
        
        time.sleep(interval)
    
    raise TimeoutError("轮询超时")
```

#### 3. 并发处理
```python
import asyncio
import aiohttp

async def submit_multiple_evaluations(audio_pairs, round_id):
    """并发提交多个评测任务"""
    async with aiohttp.ClientSession() as session:
        tasks = []
        for card_id, (practice_path, original_path) in audio_pairs.items():
            task = submit_evaluation_async(session, round_id, card_id, practice_path, original_path)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
```

#### 4. 错误重试机制
```python
import time
from functools import wraps

def retry(max_attempts=3, delay=1, backoff=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            current_delay = delay
            
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts == max_attempts:
                        raise e
                    
                    print(f"第{attempts}次尝试失败: {e}，{current_delay}秒后重试")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            return None
        return wrapper
    return decorator

@retry(max_attempts=3, delay=2, backoff=2)
def robust_api_call(url, **kwargs):
    response = requests.get(url, **kwargs)
    response.raise_for_status()
    return response.json()
```

---

## 🔧 故障排除

### 常见问题

#### Q1: 提交任务后长时间没有结果
**可能原因**:
- 音频文件过大或格式不支持
- AssemblyAI或Gemini API服务异常
- 服务器资源不足

**解决方案**:
1. 检查音频文件格式和大小
2. 查看服务器日志
3. 确认API密钥配置正确
4. 适当增加超时时间

#### Q2: 总结报告生成失败
**可能原因**:
- 没有足够的完成评测
- Gemini API调用超时
- 数据格式异常

**解决方案**:
1. 确保至少有一个COMPLETED状态的评测
2. 增加请求超时时间到180秒
3. 检查单句评测结果的数据完整性

#### Q3: 音频上传失败
**可能原因**:
- 文件路径错误
- 文件权限问题
- 网络连接异常

**解决方案**:
1. 确认文件存在且可读
2. 检查网络连接
3. 尝试较小的音频文件

### 调试技巧

#### 1. 启用详细日志
```python
import logging

# 配置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 记录API调用
def log_api_call(method, url, **kwargs):
    logging.info(f"{method} {url}")
    if 'data' in kwargs:
        logging.debug(f"Data: {kwargs['data']}")
    
    response = requests.request(method, url, **kwargs)
    logging.info(f"Response: {response.status_code}")
    
    return response
```

#### 2. 健康检查
```python
def health_check(base_url="http://127.0.0.1:8000"):
    """检查API服务健康状态"""
    try:
        # 检查API文档页面
        response = requests.get(f"{base_url}/docs", timeout=5)
        if response.status_code == 200:
            print("✅ API服务正常")
            return True
        else:
            print(f"❌ API服务异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接API服务: {e}")
        return False

# 使用前先检查
if health_check():
    # 执行API调用
    pass
else:
    print("请先启动API服务: python main.py")
```

---

## 📚 附录

### 环境配置

#### 服务器端配置
```bash
# 1. 安装依赖
pip install fastapi uvicorn assemblyai google-generativeai

# 2. 配置环境变量
export ASSEMBLYAI_API_KEY="your_assemblyai_key"
export GEMINI_API_KEY="your_gemini_key"
export GEMINI_MODEL_NAME="gemini-1.5-flash"

# 3. 启动服务
python main.py
```

#### 客户端依赖
```bash
pip install requests aiohttp  # 基础HTTP客户端
pip install asyncio           # 异步支持
```

### 性能参考

| 操作 | 预期时间 | 超时设置 |
|------|----------|----------|
| 任务提交 | < 1秒 | 30秒 |
| 语音识别 | 10-30秒 | 60秒 |
| AI分析 | 30-90秒 | 120秒 |
| 总结报告 | 60-120秒 | 180秒 |

### 版本更新日志

**v1.0** (当前版本)
- 基础API功能实现
- 支持单句评测和总结报告
- 异步处理架构
- 完整的错误处理机制

---

## 📞 技术支持

如有技术问题，请：
1. 查看服务器日志文件
2. 确认API密钥配置
3. 检查网络连接状态
4. 参考本文档的故障排除部分

**API文档地址**: `http://127.0.0.1:8000/docs`  
**项目仓库**: 请联系项目维护者获取源码访问权限