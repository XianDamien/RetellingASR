# main.py (理念对齐最终版)

import assemblyai as aai
import google.generativeai as genai
import asyncio
import json
import os
import sqlite3
import logging
import fastapi
from fastapi import File, UploadFile, HTTPException, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid
import uvicorn
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- 1. 定义所有配置变量 ---
DB_FILE = "evaluation_jobs.db"
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "在此处替换为您的 AssemblyAI API 密钥")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "在此处替换为您的 Google Gemini API 密钥")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")

# --- 2. 配置日志 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 3. 配置API库 ---
if ASSEMBLYAI_API_KEY and not ASSEMBLYAI_API_KEY.startswith("在此处"):
    aai.settings.api_key = ASSEMBLYAI_API_KEY
    logging.info("✅ AssemblyAI API 密钥已配置")
else:
    logging.warning("⚠️ AssemblyAI API 密钥未正确设置")

if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("在此处"):
    genai.configure(api_key=GEMINI_API_KEY)
    logging.info("✅ Gemini API 密钥已配置")
else:
    logging.warning("⚠️ Gemini API 密钥未正确设置")

# --- 4. 创建全局客户端 ---
transcriber_client = aai.Transcriber() if aai.settings.api_key else None
gemini_model = None
if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("在此处"):
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    gemini_model = genai.GenerativeModel(
        GEMINI_MODEL_NAME,
        safety_settings=safety_settings
    )

if not transcriber_client:
    logging.warning("AssemblyAI 客户端未创建，因为 API 密钥未设置。")
if not gemini_model:
    logging.warning("Gemini 模型客户端未创建，因为 API 密钥未设置。")

# --- 5. 数据库初始化 ---
def init_db():
    if not os.path.exists(DB_FILE):
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE jobs (
                    round_id TEXT, card_id TEXT, status TEXT,
                    result TEXT, error_message TEXT,
                    PRIMARY KEY (round_id, card_id)
                )""")
        logging.info("数据库已初始化。")
init_db()

# --- FastAPI 应用实例 ---
app = fastapi.FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# --- 核心功能函数 ---

# 【已移除】calculate_missing_words 函数已被移除，因为它不符合“功能对等”的评估理念。

def build_single_card_gemini_prompt(original_asr_data: dict, practice_asr_data: dict) -> str:
    # 【已更新】使用最新的、以“意义保真度”和“功能对等”为核心的Prompt
    return f"""
你是一位AI语言教练，专注于分析用户的**复述 (Retelling)** 练习。你的核心任务是评估用户在**脱离文本**的情况下，对原句**核心意义的理解、整合与重构能力**。你的反馈应鼓励有效的**意译 (paraphrasing)**，而不是死板地抠字眼。你的反馈必须简洁、数据驱动、直击要点。注意所有的回答必须用中文回答。

**输入数据:**

1. `original_asr_data`: 标准发音的ASR数据。
    
2. `practice_asr_data`: 用户复述的ASR数据。
    

**你的任务：** 严格按照以下JSON结构，生成一份侧重于意义和表达的诊断报告。

#### **【核心】JSON输出结构:**

**1. `meaning_fidelity` (意义保真度)**

- `assessment`: (string) 一句话总结用户复述的核心意思是否准确。例如：“核心意思已准确表达，但遗漏了一个关键细节。”或“完美地转述了原文的核心信息和语气。”
    
- `missing_details`: (string[]) 一个数组，列出用户复述时**遗漏的关键信息点**。
    
- `added_inaccuracies`: (string[]) 一个数组，列出用户复述时**添加的不准确信息**。
    

**2. `expression_comparison` (表达方式对比)**

- `summary`: (string) 对比两种表达方式的总体评价。例如：“您的表达清晰，但原文的表达更地道。”或“您的转述非常精彩，甚至比原文更简洁！”
    
- `original_highlight`: (string) 点出**原文中1个最精妙或地道的词汇/表达**，并简要说明其妙处。例如：“原文中的'tackle the issue'是一个非常地道的搭配，比常见的'solve the problem'更生动。”
    
- `user_highlight`: (string) 如果用户的意译中有亮点，给予肯定。例如：“您使用的'deal with the problem'也是一个很好的同义替换。”
    

**3. `fluency_and_rhythm` (流畅度与节奏)**

- `assessment`: (string) **一针见血地指出核心节奏模式**。例如：“整体节奏因**逐词朗读**而显得生硬，缺少自然的连贯性。”
    

**4. `critical_pronunciation_errors` (关键发音错误)**

- (object[]) 一个对象数组，**只列出1-2个最严重、足以影响理解**的发音问题。如果不存在此类问题，则返回空数组 `[]`。
    
    - `word`: (string) 问题单词。
        
    - `issue`: (string) 简洁的修正建议，例如：“'three'中的/θ/音发得更像/s/，可能会被听成'see'。”
        

**5. `overall_score` (综合评分)**

- (int) 0到100的综合评分。评分权重：**意义保真度 (50%)**，流畅度与节奏 (30%)，表达方式 (20%)。
    

**输入数据示例:** `original_asr_data`: {json.dumps(original_asr_data, indent=2)} `practice_asr_data`: {json.dumps(practice_asr_data, indent=2)}

请现在开始你的分析，并确保输出是一个可以被程序直接解析的、格式正确的 JSON 对象。
"""

async def process_and_store_evaluation(practice_audio_path: str, original_audio_path: str, round_id: str, card_id: str):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("UPDATE jobs SET status = ? WHERE round_id = ? AND card_id = ?", ("PROCESSING", round_id, card_id))
        logging.info(f"[{round_id}/{card_id}] 状态更新为 PROCESSING。")
    except Exception as e:
        logging.error(f"[{round_id}/{card_id}] 更新状态为 PROCESSING 时数据库出错: {e}")
        return

    try:
        if not transcriber_client or not gemini_model:
            raise Exception("API clients are not initialized due to missing keys.")

        logging.info(f"[{round_id}/{card_id}] 开始并行转录音频...")
        practice_task = asyncio.to_thread(transcriber_client.transcribe, practice_audio_path)
        original_task = asyncio.to_thread(transcriber_client.transcribe, original_audio_path)
        practice_transcript, original_transcript = await asyncio.gather(practice_task, original_task)

        if practice_transcript.status == aai.TranscriptStatus.error or original_transcript.status == aai.TranscriptStatus.error:
            raise Exception(f"ASR Error - Practice: {practice_transcript.error}, Original: {original_transcript.error}")

        original_asr_data = {"text": original_transcript.text, "words": [word.dict() for word in original_transcript.words]}
        practice_asr_data = {"text": practice_transcript.text, "words": [word.dict() for word in practice_transcript.words]}
        
        # 【已移除】不再需要计算和传递 missing_words
        logging.info(f"[{round_id}/{card_id}] 构建 Prompt 并调用 Gemini...")
        prompt = build_single_card_gemini_prompt(original_asr_data, practice_asr_data)
        
        logging.info(f"[{round_id}/{card_id}] 开始调用 Gemini API (超时设置为120秒)...")
        request_options = {"timeout": 120} 
        response = await gemini_model.generate_content_async(
            prompt,
            request_options=request_options
        )
        logging.info(f"[{round_id}/{card_id}] Gemini API 调用成功返回。")
        
        cleaned_response = response.text.strip().lstrip("```json").rstrip("```").strip()
        evaluation_report = json.loads(cleaned_response)

        # 【已更新】存储的数据中不再包含多余的 source_data.missing_words
        full_card_data = { 
            "evaluation_report": evaluation_report, 
            "source_data": { 
                "original_asr": original_asr_data, 
                "practice_asr": practice_asr_data
            } 
        }
        
        with sqlite3.connect(DB_FILE) as conn:
            result_json = json.dumps(full_card_data)
            conn.execute("UPDATE jobs SET status = ?, result = ? WHERE round_id = ? AND card_id = ?", ("COMPLETED", result_json, round_id, card_id))
        logging.info(f"[{round_id}/{card_id}] 评测成功，结果已存入数据库。")

    except Exception as e:
        logging.error(f"[{round_id}/{card_id}] 处理后台任务时发生严重错误: {e}", exc_info=True)
        try:
            with sqlite3.connect(DB_FILE) as conn:
                error_msg = str(e)
                conn.execute("UPDATE jobs SET status = ?, error_message = ? WHERE round_id = ? AND card_id = ?", ("FAILED", error_msg, round_id, card_id))
        except Exception as db_e:
            logging.error(f"[{round_id}/{card_id}] 记录 FAILED 状态到数据库时再次出错: {db_e}")
            
    finally:
        logging.info(f"[{round_id}/{card_id}] 开始清理临时文件...")
        if os.path.exists(practice_audio_path): os.remove(practice_audio_path)
        if os.path.exists(original_audio_path): os.remove(original_audio_path)
        logging.info(f"[{round_id}/{card_id}] 后台任务处理流程结束。")


# --- FastAPI 端点 ---

@app.post("/evaluate-single-card", status_code=202)
async def evaluate_single_card(
    background_tasks: BackgroundTasks,
    round_id: str = Form(...),
    card_id: str = Form(...),
    practice_audio: UploadFile = File(...),
    original_audio: UploadFile = File(...)
):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("INSERT INTO jobs (round_id, card_id, status) VALUES (?, ?, ?)", (round_id, card_id, "PENDING"))
    except sqlite3.IntegrityError:
         return JSONResponse(status_code=409, content={"detail": "Job for this round_id and card_id already exists."})
    except Exception as e:
        logging.error(f"创建任务记录失败: {e}")
        raise HTTPException(status_code=500, detail="Failed to create job record in database.")

    temp_dir = "temp_audio"
    os.makedirs(temp_dir, exist_ok=True)
    unique_suffix = str(uuid.uuid4())
    practice_audio_path = os.path.join(temp_dir, f"{round_id}_{card_id}_practice_{unique_suffix}.wav")
    original_audio_path = os.path.join(temp_dir, f"{round_id}_{card_id}_original_{unique_suffix}.wav")
    
    with open(practice_audio_path, "wb") as f: f.write(await practice_audio.read())
    with open(original_audio_path, "wb") as f: f.write(await original_audio.read())
    
    background_tasks.add_task(process_and_store_evaluation, practice_audio_path, original_audio_path, round_id, card_id)
    
    return {"message": "Job submitted and is pending evaluation."}


@app.get("/get-single-card-result/{round_id}/{card_id}")
async def get_single_card_result(round_id: str, card_id: str):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM jobs WHERE round_id = ? AND card_id = ?", (round_id, card_id))
            job = cursor.fetchone()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")

    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    
    return {
        "round_id": job["round_id"],
        "card_id": job["card_id"],
        "status": job["status"],
        "result": json.loads(job["result"]) if job["result"] else None,
        "error_message": job["error_message"]
    }


@app.get("/get-round-summary/{round_id}")
async def get_round_summary(round_id: str):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT card_id, result FROM jobs WHERE round_id = ? AND status = ?", (round_id, "COMPLETED"))
            completed_jobs = cursor.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query for summary failed: {e}")

    if not completed_jobs:
        raise HTTPException(status_code=404, detail="No completed evaluations found for this round yet.")

    card_data = {
        job["card_id"]: json.loads(job["result"])["evaluation_report"] 
        for job in completed_jobs
    }

    # 【已更新】使用最新的、以“听口关联”和“模式分析”为核心的汇总Prompt
    summary_prompt = f"""
你是一位顶级的AI语言诊断分析师，深刻理解 **“听口不分家”** 的语言学习原理。你的任务是基于所有单句的ASR对比数据，进行模式识别和根本原因分析，找出用户在**信息理解**和**口语表达**上的系统性关联。你的反馈必须高度凝练、数据驱动，并以一个结构化的JSON对象输出。注意所有的回答必须用中文回答。

**输入数据:** 你将收到一个名为 `card_data` 的JSON对象，它包含了本轮所有句子的诊断报告和原始ASR数据。

**核心任务与分析逻辑:**

1. **模式识别**: 跨句子聚合分析用户的复述错误（信息遗漏、替换）和口语产出特点（发音、流畅度）。
    
2. **听口关联分析**: 找出用户的**听力理解难点**（例如，听不懂连读、弱读）与其**口语产出习惯**（例如，自己也不会连读、弱读）之间的强关联，并明确指出这可能是“因为你不会这样说，所以你很难听懂”的根本原因。
    
3. **精简输出**: 只输出最关键的模式分析和值得关注的语言点，避免提供宽泛的提升建议。
    

### **【核心】最终输出的JSON结构定义:**

**1. `performance_overview` (本轮表现快照)**

- `comment`: (string) 一句话总结本轮在“意义传达”上的整体表现。
    
- `final_score`: (int) 0到100的最终综合评分。
    

**2. `key_patterns_analysis` (核心模式分析)**

- (object[]) 一个对象数组，**按重要性列出1-3个最关键的听口关联模式**。
    
    - `pattern_id`: (int) 模式序号。
        
    - `observation`: (string) 对观察到的现象进行客观描述。例如：“在多个句子中，您将带有连读的语块（如'jumps over'）复述为孤立的单词（如'jump over'），遗漏了关键的语法信息（三单的's'）。”
        
    - `possible_cause`: (string) **一针见血地指出听力与口语的可能关联**。例如：“这很可能是因为您自身的口语习惯倾向于‘逐词朗读’，导致您的听觉系统对母语者自然的连读现象不敏感。**因为您不习惯这样说，所以当听到时，大脑可能无法快速解码。**”
        

**3. `vocabulary_and_expression_focus` (重点词汇与表达)**

- `items`: (object[]) 一个对象数组，**只列出3-4个本轮最值得关注的词汇或短语**，结合用户的实际表达进行分析。
    
    - `en`: (string) 英文原文。
        
    - `zh`: (string) 中文释义。
        
    - `note`: (string) **简短的分析或提示**。例如：“一个地道的动词短语，您成功意译为'deal with'，表达准确。” 或 “您对此词的发音/s/不清晰，这可能是您未能准确复述的原因之一。”
        
- `native_speech_insight`: (string) **一句话点出本轮最值得学习的母语者语音技巧**，并提供搜索关键词。例如：“本轮原句中普遍存在**辅音+元音连读**现象，这是提升听力理解和口语自然度的关键。(可搜索: 'Connected Speech Linking')”
    

**学生本轮练习的深度诊断数据如下:**

```
{json.dumps(card_data, indent=2, ensure_ascii=False)}
```

请严格按照以上要求，开始你的深度聚合分析，并输出最终的汇总报告JSON。
    """
    
    logging.info(f"[{round_id}] 构建宏观汇总 Prompt 并调用 Gemini...")
    if not gemini_model:
        raise HTTPException(status_code=503, detail="Gemini client is not available.")

    try:
        logging.info(f"[{round_id}] 开始调用 Gemini API for summary (超时设置为180秒)...")
        request_options = {"timeout": 180}
        response = await gemini_model.generate_content_async(
            summary_prompt,
            request_options=request_options
        )
        logging.info(f"[{round_id}] Gemini summary API 调用成功返回。")
    except Exception as e:
        logging.error(f"[{round_id}] 生成汇总报告时 Gemini 调用失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate summary from Gemini: {e}")

    cleaned_response = response.text.strip().lstrip("```json").rstrip("```").strip()
    return json.loads(cleaned_response)

# --- 启动应用 ---
if __name__ == "__main__":
    logging.info(f"--- 句子复述 AI 评测服务 (数据库版) ---")
    logging.info(f"将使用 Gemini 模型: {GEMINI_MODEL_NAME}")
    logging.info("访问 http://127.0.0.1:8000/docs 查看 API 文档。")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
