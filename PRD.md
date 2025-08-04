# **AI英语复述评测系统 - 产品需求文档 (PRD)**

版本: 1.0

日期: 2025年8月4日

### **1. 项目愿景与核心理念**

#### **1.1. 项目概述**

本项目旨在开发一个基于AI的自动化英语口语复述 (Retelling) 评测系统。它通过对比“标准音频”和“用户复述音频”，为语言学习者提供深度、个性化的反馈，帮助他们高效提升在真实交流场景下的听力理解与口语表达能力。

#### **1.2. 核心教学哲学**

本系统摒弃了传统的、死板的“词对词”评估标准。我们的核心理念根植于现代语言教学法，强调：

- **功能对等 (Functional Equivalence)**: 我们评估的不是用户是否精确复制了原文的“形态”，而是其复述是否在“功能”和“意义”上与原文对等。有效的**意译 (Paraphrasing)** 将受到鼓励和赞扬。
    
- **交际能力优先 (Communicative Competence First)**: 系统的首要目标是提升用户的实际沟通效率。反馈将优先关注那些最影响意义传达和听者理解的问题。
    
- **听口不分家 (The Listening-Speaking Connection)**: 我们坚信，听力理解的障碍往往源于自身的口语产出习惯。系统将致力于揭示用户“听不懂”和“说不对”之间的深层关联，提供根本性的诊断。
    
- **做减法 (Less is More)**: AI的反馈不应是信息过载的“错误清单”，而应是高度凝练、聚焦于核心模式的“诊断报告”，为用户指明下一阶段**最重要的一件事**。
    

#### **1.3. 目标用户**

处于中高级阶段（B1及以上）的英语学习者，他们不再满足于基础的单词和语法学习，希望通过“复述”这种高阶练习，打磨自己的听力理解、信息整合及口语表达能力，使之更接近母语者的流利度和地道性。

### **2. 系统架构与工作流程**

#### **2.1. 高层架构**

本系统采用前后端分离的客户端-服务器架构。

- **后端 (Backend)**: 基于 Python 和 FastAPI 构建，负责处理API请求、文件存储、数据库交互以及与第三方AI服务的通信。
    
- **数据库 (Database)**: 使用 SQLite 进行持久化存储，追踪每一个评测任务的状态和结果。
    
- **第三方服务 (AI Services)**:
    
    - **AssemblyAI**: 用于高精度的语音转文字 (ASR)，提供详细的单词时间戳和置信度数据。
        
    - **Google Gemini**: 作为核心分析引擎，负责执行我们精心设计的Prompt，进行单句诊断和宏观总结。
        

#### **2.2. 核心工作流程**

系统的工作流程分为两个主要阶段：**单句分析**（异步后台处理）和**总结报告**（同步请求处理）。

##### **阶段一：单句复述分析 (Asynchronous Single-Card Analysis)**

1. **任务提交**: 客户端调用 `POST /evaluate-single-card`，上传标准音频和用户复述音频。
    
2. **任务入库**: 服务器立即在数据库中创建一条状态为 `PENDING` 的任务记录，并返回 `202 Accepted`，告知客户端任务已接收。
    
3. **后台处理**:
    
    - 服务器启动一个后台任务，将数据库中的任务状态更新为 `PROCESSING`。
        
    - **并行ASR**: 将两个音频文件并行发送给 AssemblyAI 进行语音识别。
        
    - **AI微观诊断**: 待ASR结果返回后，调用 `build_single_card_gemini_prompt` 构建**单句分析Prompt**，并请求 Gemini 进行分析。此Prompt的核心是评估**意义保真度**和**表达方式**。
        
    - **结果存储**: 将 Gemini 返回的详细JSON诊断报告存入数据库，并将任务状态更新为 `COMPLETED`。若中途失败，则状态更新为 `FAILED` 并记录错误信息。
        
4. **客户端轮询**: 客户端通过定期调用 `GET /get-single-card-result/{id}` 来查询任务状态，直到获取到 `COMPLETED` 或 `FAILED` 的最终结果。
    

##### **阶段二：总结分析报告 (Synchronous Summary Report)**

1. **请求触发**: 当一轮练习（例如3个句子）全部完成后，客户端调用 `GET /get-round-summary/{round_id}`。
    
2. **数据聚合**: 服务器从数据库中查询出该 `round_id` 下所有已完成的单句诊断报告。
    
3. **AI宏观分析**:
    
    - 系统将所有单句报告聚合，并调用 `build_summary_gemini_prompt` 构建**总结分析Prompt**。
        
    - 此Prompt的核心是进行**模式识别**和**听口关联分析**，找出系统性问题并给出聚焦的练习建议。
        
4. **返回报告**: 服务器将 Gemini 返回的宏观总结JSON报告直接返回给客户端。
    

#### **2.3. Mermaid 流程图**

```
sequenceDiagram
    participant Client as 客户端
    participant Server as FastAPI服务器
    participant AssemblyAI
    participant Gemini
    participant DB as 数据库

    Note over Client, DB: --- 阶段一: 单句复述评测 (异步) ---
    Client->>+Server: POST /evaluate-single-card (音频)
    Server->>+DB: INSERT job (status='PENDING')
    DB-->>-Server: OK
    Server-->>-Client: 202 Accepted (任务已提交)
    
    Note over Server: 启动后台任务
    Server->>+DB: UPDATE job SET status='PROCESSING'
    DB-->>-Server: OK
    
    par
        Server->>+AssemblyAI: 转录 practice_audio
        AssemblyAI-->>-Server: practice_asr_data
    and
        Server->>+AssemblyAI: 转录 original_audio
        AssemblyAI-->>-Server: original_asr_data
    end

    Server->>+Gemini: 请求单句分析 (基于意义保真度)
    Gemini-->>-Server: 单句JSON报告
    
    Server->>+DB: UPDATE job SET status='COMPLETED', result=...
    DB-->>-Server: OK
    
    loop 客户端轮询
        Client->>+Server: GET /get-single-card-result/{id}
        Server-->>-Client: 返回任务状态 (e.g., 'COMPLETED')
    end

    Note over Client, DB: --- 阶段二: 获取总结报告 (同步) ---
    Client->>+Server: GET /get-round-summary/{round_id}
    Server->>+DB: SELECT result FROM completed_jobs
    DB-->>-Server: 返回所有单句报告
    
    Server->>+Gemini: 请求总结分析 (基于模式识别)
    Gemini-->>-Server: 最终总结JSON报告
    Server-->>-Client: 返回最终总结报告
```

### **3. AI Prompt 核心策略**

#### **3.1. 单句分析Prompt (`build_single_card_gemini_prompt`)**

- **核心目标**: 评估单次复述的沟通效果。
    
- **输入**: `original_asr_data`, `practice_asr_data`。
    
- **输出JSON结构**:
    
    - `meaning_fidelity`: 评估核心意义的保真度，列出遗漏或不准的关键信息点。
        
    - `expression_comparison`: 对比用户和原文的表达方式，赞扬成功的意译，并点出原文的地道之处。
        
    - `fluency_and_rhythm`: 指出核心的节奏模式（如“逐词朗读”）。
        
    - `critical_pronunciation_errors`: 只列出1-2个最影响理解的发音问题。
        
    - `overall_score`: 综合评分，权重向“意义保真度”倾斜。
        

#### **3.2. 总结分析Prompt (`get_round_summary`)**

- **核心目标**: 进行跨句子的模式识别和听口关联分析。
    
- **输入**: 该回合所有单句分析的JSON报告。
    
- **输出JSON结构**:
    
    - `performance_overview`: 对本轮沟通目标的达成情况做快照式总结。
        
    - `key_patterns_analysis`: **只列出1-3个最关键的听口关联模式**，并一针见血地指出其可能的根本原因（例如，“因为您不习惯连读，所以听不懂连读”）。
        
    - `vocabulary_and_expression_focus`: 列出3-4个最值得关注的词汇或短语，并结合用户表达进行简要分析。
        
    - `native_speech_insight`: 点出本轮最值得学习的母语者语音技巧，并提供**搜索关键词**，鼓励用户自主探索。
        

### **4. 技术栈**

- **后端框架**: FastAPI
    
- **Web服务器**: Uvicorn
    
- **数据库**: SQLite
    
- **ASR服务**: AssemblyAI Python SDK
    
- **AI分析服务**: Google Gemini Python SDK
    
- **核心依赖**: `asyncio`, `requests`, `uuid`