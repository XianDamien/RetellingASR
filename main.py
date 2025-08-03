
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
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")

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
    # --- 新增：定义安全设置 ---
    # 将所有安全分类的拦截阈值设为 BLOCK_NONE (不拦截)
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    # --- 修改：在创建模型时应用安全设置 ---
    gemini_model = genai.GenerativeModel(
        GEMINI_MODEL_NAME,
        safety_settings=safety_settings # 应用设置
    )

if not transcriber_client:
    logging.warning("AssemblyAI 客户端未创建，因为 API 密钥未设置。")
if not gemini_model:
    logging.warning("Gemini 模型客户端未创建，因为 API 密钥未设置。")

# --- 5. 数据库初始化 ---
def init_db():
    if not os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE jobs (
                round_id TEXT, card_id TEXT, status TEXT,
                result TEXT, error_message TEXT,
                PRIMARY KEY (round_id, card_id)
            )""")
        conn.commit()
        conn.close()
        logging.info("数据库已初始化。")
init_db()

# --- FastAPI 应用实例 ---
app = fastapi.FastAPI()
# 允许所有来源的 CORS 请求，方便前端开发
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# --- 核心功能函数 ---
def calculate_missing_words(original_text: str, practice_text: str) -> list[str]:
    if not original_text: return []
    original_words = set(original_text.lower().split())
    practice_words = set(practice_text.lower().split())
    return sorted(list(original_words - practice_words))

def build_single_card_gemini_prompt(original_asr_data: dict, practice_asr_data: dict, missing_words: list[str]) -> str:
    # ... (您的 prompt 构建函数保持不变) ...
    return f"""
你是一位顶级的英语口语诊断专家，擅长通过对比分析标准发音和学生发音的详细语音数据（ASR）来提供精准反馈，注意所有的回答必须用中文回答。
你会收到两份核心的 ASR 数据包：
1. `original_asr_data`: 这是标准发音的音频转录和语音数据。
2. `practice_asr_data`: 这是学生复述的音频转录和语音数据。
此外，你还会收到一个 `missing_words` 列表。
你的任务是：像一位数据驱动的教练一样，对这两份数据进行深度对比分析，并严格按照以下维度和步骤，生成一份 JSON 格式的诊断报告。

**分析步骤与 JSON 输出结构：**
1.  **内容完整度 (Content Completion)**: 参考 `missing_words` 列表，在报告中清晰列出遗漏的单词。如果列表为空，则给予肯定。
2.  **发音准确性 (Pronunciation Accuracy)**: 遍历 `practice_asr_data.words` 数组。对于其中 `confidence` 较低（如低于 0.85）的单词，将其与 `original_asr_data` 中对应的单词进行对比，指出可能发错的单词，并提供正确的发音提示。
3.  **流利度与节奏 (Fluency & Rhythm)**: 对比 `practice_asr_data` 和 `original_asr_data` 中单词间停顿。找出不自然的停顿或仓促的连接，并对整体语速和节奏模仿度做出评价。
4.  **地道表达与词汇解析 (Expression & Vocabulary)**: 阅读 `original_asr_data.text`，识别并解释其中可能对学生构成难点的地道表达、高级词汇或特定背景词汇。
5.  **综合评分 (Overall Score) **: 基于以上所有维度的对比分析，给出一个0到100的综合分数（发音40%，流利度与节奏30%，内容完整度30%）。

**输入数据示例:**
`original_asr_data`: {json.dumps(original_asr_data, indent=2)}
`practice_asr_data`: {json.dumps(practice_asr_data, indent=2)}
`missing_words`: {json.dumps(missing_words)}

请现在开始你的分析，并确保输出是一个可以被程序直接解析的、格式正确的 JSON 对象。
"""

async def process_and_store_evaluation(practice_audio_path: str, original_audio_path: str, round_id: str, card_id: str):
    # ... (您的重构版后台处理函数保持不变) ...
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("UPDATE jobs SET status = ? WHERE round_id = ? AND card_id = ?", ("PROCESSING", round_id, card_id))
            conn.commit()
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
        missing_words = calculate_missing_words(original_transcript.text or "", practice_transcript.text or "")
        
        logging.info(f"[{round_id}/{card_id}] 构建 Prompt 并调用 Gemini...")
        prompt = build_single_card_gemini_prompt(original_asr_data, practice_asr_data, missing_words)
        
        # --- 新增的超时控制和日志 ---
        logging.info(f"[{round_id}/{card_id}] 开始调用 Gemini API (超时设置为120秒)...")
        request_options = {"timeout": 120} 
        response = await gemini_model.generate_content_async(
            prompt,
            request_options=request_options
        )
        logging.info(f"[{round_id}/{card_id}] Gemini API 调用成功返回。")
        
        cleaned_response = response.text.strip().lstrip("```json").rstrip("```").strip()
        evaluation_report = json.loads(cleaned_response)

        full_card_data = { "evaluation_report": evaluation_report, "source_data": { "original_asr": original_asr_data, "practice_asr": practice_asr_data, "missing_words": missing_words } }
        
        with sqlite3.connect(DB_FILE) as conn:
            result_json = json.dumps(full_card_data)
            conn.execute("UPDATE jobs SET status = ?, result = ? WHERE round_id = ? AND card_id = ?", ("COMPLETED", result_json, round_id, card_id))
            conn.commit()
        logging.info(f"[{round_id}/{card_id}] 评测成功，结果已存入数据库。")

    except Exception as e:
        logging.error(f"[{round_id}/{card_id}] 处理后台任务时发生严重错误: {e}", exc_info=True)
        try:
            with sqlite3.connect(DB_FILE) as conn:
                error_msg = str(e)
                conn.execute("UPDATE jobs SET status = ?, error_message = ? WHERE round_id = ? AND card_id = ?", ("FAILED", error_msg, round_id, card_id))
                conn.commit()
        except Exception as db_e:
            logging.error(f"[{round_id}/{card_id}] 记录 FAILED 状态到数据库时再次出错: {db_e}")
            
    finally:
        logging.info(f"[{round_id}/{card_id}] 开始清理临时文件...")
        if os.path.exists(practice_audio_path): os.remove(practice_audio_path)
        if os.path.exists(original_audio_path): os.remove(original_audio_path)
        logging.info(f"[{round_id}/{card_id}] 后台任务处理流程结束。")


# --- FastAPI 端点 (全部已修正为使用数据库) ---

@app.post("/evaluate-single-card", status_code=202)
async def evaluate_single_card(
    background_tasks: BackgroundTasks,
    round_id: str = Form(...),
    card_id: str = Form(...),
    practice_audio: UploadFile = File(...),
    original_audio: UploadFile = File(...)
):
    # 1. 在数据库中创建任务记录
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("INSERT INTO jobs (round_id, card_id, status) VALUES (?, ?, ?)", (round_id, card_id, "PENDING"))
            conn.commit()
    except sqlite3.IntegrityError: # 防止重复提交
         return JSONResponse(status_code=409, content={"detail": "Job for this round_id and card_id already exists."})
    except Exception as e:
        logging.error(f"创建任务记录失败: {e}")
        raise HTTPException(status_code=500, detail="Failed to create job record in database.")

    # 2. 保存音频文件并启动后台任务
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
    """从数据库获取单个卡片的评测结果。"""
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
    """从数据库获取一轮练习的所有已完成结果，并生成最终汇总报告。"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT card_id, result FROM jobs WHERE round_id = ? AND status = ?", (round_id, "COMPLETED"))
            completed_jobs = cursor.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query for summary failed: {e}")

    if not completed_jobs:
        raise HTTPException(status_code=404, detail="No completed evaluations found for this round yet.")

    # 解析所有已完成任务的结果
    card_data = {job["card_id"]: json.loads(job["result"]) for job in completed_jobs}

    summary_prompt = f"""
你是一位经验丰富的英语教学总监，你正在审查一位学生在一轮复述练习中的所有表现。
    你的助教（AI诊断专家）已经为每个句子提供了基于原始音频和学生音频对比的深度诊断报告。
    你的任务是：
    1.  **回顾所有诊断**: 仔细阅读下面提供的每一张卡片的JSON格式诊断报告和源数据。
    2.  **总结列出经常读错的音标**: 从所有卡片的**对比数据**中，识别出学生经常读错的音标，并列出这些音标。
    3.  **总结列出出现错误的典型语块**: 从所有卡片的**对比数据**中，识别出学生经常读错的语块，并列出这些语块。
    4.  **分析原音频的连读风格、列出重点词汇和语块表达**: 分析原音频的连读风格、列出重点词汇和语块表达。
    5.  **评分与总结**：根据错误的音标、单词，以及整体的流畅度问题，给出从具体音标原因诊断到母语者连读弱读技巧的总结，以及详细列出需要重点加强、可执行的音标、连读弱读技巧的计划。
    6.  **格式化输出**: 将你的分析结果以一个结构化的JSON对象返回。
    **学生本轮练习的深度诊断数据如下:**
    {json.dumps(card_data, indent=2, ensure_ascii=False)}
    请严格按照以上要求，输出最终的汇总报告JSON。

    """
    
    logging.info(f"[{round_id}] 构建宏观汇总 Prompt 并调用 Gemini...")
    if not gemini_model:
        raise HTTPException(status_code=503, detail="Gemini client is not available.")

    # --- 为汇总报告的API调用也添加超时控制 ---
    try:
        logging.info(f"[{round_id}] 开始调用 Gemini API for summary (超时设置为120秒)...")
        request_options = {"timeout": 120}
        response = await gemini_model.generate_content_async(
            summary_prompt,
            request_options=request_options
        )
        logging.info(f"[{round_id}] Gemini summary API 调用成功返回。")
    except Exception as e:
        logging.error(f"[{round_id}] 生成汇总报告时 Gemini 调用失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate summary from Gemini: {e}")
    
    # 这里我们不再清理数据库，以便后续查询和调试
    # 如需清理，可添加 DELETE FROM jobs WHERE round_id = ? 语句

    cleaned_response = response.text.strip().lstrip("```json").rstrip("```").strip()
    return json.loads(cleaned_response)

# --- 启动应用 ---
if __name__ == "__main__":
    logging.info(f"--- 句子复述 AI 评测服务 (数据库版) ---")
    logging.info(f"将使用 Gemini 模型: {GEMINI_MODEL_NAME}")
    logging.info("访问 http://127.0.0.1:8000/docs 查看 API 文档。")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)