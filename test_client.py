# test_client.py (最终修正版)

import requests
import time
import uuid
import json
import os

# --- 1. 配置 ---
BASE_URL = "http://127.0.0.1:8000"
AUDIO_FILES = {
    "card_01": {
        "original": "sample_audio/original_1.wav",
        "practice": "sample_audio/practice_1.wav"
    },
    "card_02": {
        "original": "sample_audio/original_2.wav",
        "practice": "sample_audio/practice_2.wav"
    },
    "card_03": {
        "original": "sample_audio/original_3.wav",
        "practice": "sample_audio/practice_3.wav"
    }
}

def run_full_demo():
    """运行完整的演示，包括提交任务、智能轮询、显示单卡和汇总报告"""
    
    round_id = f"demo_round_{str(uuid.uuid4())[:8]}"
    print(f"=== 句子复述 AI 评测服务演示 (数据库版) ===")
    print(f"会话ID: {round_id}")
    print(f"测试服务器: {BASE_URL}")
    
    # [步骤 1] 检查音频文件
    print(f"\n[步骤 1] 检查音频文件...")
    for card_id, files in AUDIO_FILES.items():
        for file_type, file_path in files.items():
            if not os.path.exists(file_path):
                print(f"❌ 错误: 找不到文件 {file_path}")
                return
            print(f"  ✅ {card_id}_{file_type}: {file_path}")
    
    # [步骤 2] 提交所有卡片进行评测
    print(f"\n[步骤 2] 提交卡片创建评测任务...")
    submitted_cards = []
    for card_id, files in AUDIO_FILES.items():
        try:
            print(f"  📤 正在提交 {card_id}...")
            with open(files["original"], "rb") as orig_file, open(files["practice"], "rb") as prac_file:
                files_data = {"original_audio": orig_file, "practice_audio": prac_file}
                data = {"round_id": round_id, "card_id": card_id}
                response = requests.post(f"{BASE_URL}/evaluate-single-card", files=files_data, data=data, timeout=30)
                response.raise_for_status() # 如果服务器返回错误 (如500), 则会抛出异常
                print(f"  ✅ {card_id} 提交成功: {response.json().get('message')}")
                submitted_cards.append(card_id)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409: # 捕捉我们设置的“任务已存在”冲突
                print(f"  ⚠️ {card_id} 提交警告: {e.response.json().get('detail')}")
            else:
                print(f"  ❌ {card_id} 提交时发生HTTP错误: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"  ❌ {card_id} 提交时发生未知错误: {e}")
    
    if not submitted_cards:
        print("\n❌ 没有成功提交任何卡片，演示结束。")
        return
    
    # [步骤 3] 智能轮询，获取逐句结果
    print(f"\n[步骤 3] 智能轮询获取评测结果...")
    finished_cards = {}
    max_wait_seconds = 600 # 最长等待10分钟
    poll_interval_seconds = 30 # 每30秒查询一次
    start_time = time.time()

    while len(finished_cards) < len(submitted_cards) and (time.time() - start_time) < max_wait_seconds:
        print(f"\n--- {int(time.time() - start_time)}s / {max_wait_seconds}s ---")
        for card_id in submitted_cards:
            if card_id in finished_cards:
                continue # 如果已完成，则跳过

            try:
                response = requests.get(f"{BASE_URL}/get-single-card-result/{round_id}/{card_id}", timeout=10)
                response.raise_for_status()
                
                job = response.json()
                status = job.get("status")
                
                if status == "COMPLETED":
                    print(f"  ✅ {card_id}: 评测完成！")
                    print("-" * 20 + f" [{card_id}] 详细报告 " + "-" * 20)
                    print(json.dumps(job.get("result", {}).get("evaluation_report"), indent=2, ensure_ascii=False))
                    print("-" * 55 + "\n")
                    finished_cards[card_id] = "COMPLETED"

                elif status == "FAILED":
                    print(f"  ❌ {card_id}: 评测失败！")
                    print(f"     错误原因: {job.get('error_message')}")
                    finished_cards[card_id] = "FAILED"
                
                else: # PENDING or PROCESSING
                    print(f"  ⏳ {card_id}: 状态为 {status}... 正在处理中。")

            except requests.exceptions.HTTPError as e:
                print(f"  ❌ 查询 {card_id} 时发生HTTP错误: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                print(f"  ❌ 查询 {card_id} 时发生未知错误: {e}")
        
        if len(finished_cards) < len(submitted_cards):
            time.sleep(poll_interval_seconds)

    # [步骤 4] 获取并显示最终汇总报告
    print("\n[步骤 4] 所有任务处理完毕，获取最终汇总报告...")
    successful_cards = [cid for cid, status in finished_cards.items() if status == "COMPLETED"]
    
    if not successful_cards:
        print("❌ 没有成功完成的评测，无法生成汇总报告。")
    else:
        try:
            # 【核心修正】将汇总报告的超时时间从30秒大幅增加到180秒（3分钟）
            summary_timeout = 180
            print(f"  ℹ️  正在请求汇总报告，请耐心等待（最长 {summary_timeout} 秒）...")
            response = requests.get(f"{BASE_URL}/get-round-summary/{round_id}", timeout=summary_timeout)
            response.raise_for_status()
            summary_report = response.json()
            
            print("\n" + "="*60)
            print("📋 AI 生成的最终汇总报告:")
            print("="*60)
            print(json.dumps(summary_report, indent=2, ensure_ascii=False))
            print("="*60)
            
        except requests.exceptions.ReadTimeout:
            print(f"❌ 获取汇总报告超时（超过 {summary_timeout} 秒）。服务器仍在处理，但客户端已停止等待。")
            print("   这通常意味着汇总分析任务非常复杂，您可以尝试再次运行或进一步优化Prompt。")
        except requests.exceptions.HTTPError as e:
             print(f"❌ 获取汇总报告失败: {e.response.status_code} - {e.response.text}")
        except Exception as e:
             print(f"❌ 获取汇总报告时发生未知错误: {e}")

    print(f"\n🏁 演示完成！会话ID: {round_id}")

def test_server_connectivity():
    """测试服务器连接"""
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            print("✅ 服务器连接正常")
            return True
        else:
            print(f"❌ 服务器响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接到服务器: {e}")
        return False

if __name__ == "__main__":
    print("🚀 开始测试...")
    if test_server_connectivity():
        run_full_demo()
    else:
        print("\n💡 请先在另一个终端运行: python main.py")