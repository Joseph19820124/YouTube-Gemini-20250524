#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import logging
import time
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo # Requires Python 3.9+
import requests

# --- Configuration ---
API_URL = "https://lic.deepsrt.cc/webhook/get-srt-from-provider"
DEFAULT_CSV_FILE_PATH = "video_ids - Sheet1.csv"
LOG_FILE_PATH = "srt_fetcher_python.log"
CST_TIMEZONE = ZoneInfo("Asia/Shanghai")

# --- Logger Setup with CST Timestamps ---
class CSTFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, style='%', validate=True, *, defaults=None):
        super().__init__(fmt, datefmt, style, validate, defaults=defaults)
        self.default_msec_format = '%s,%03d'

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=CST_TIMEZONE)
        if datefmt:
            s = dt.strftime(datefmt)
        else:
            s = f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}:{dt.second:02d},{int(dt.microsecond / 1000):03d} {dt.strftime('%z')}"
        return s

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
console_formatter = CSTFormatter('[%(asctime)s] [%(levelname)s] - %(message)s',
                                 datefmt='%Y-%m-%d %H:%M:%S %Z')
ch.setFormatter(console_formatter)
logger.addHandler(ch)

try:
    fh = logging.FileHandler(LOG_FILE_PATH, encoding='utf-8', mode='a')
    fh.setLevel(logging.DEBUG)
    file_formatter = CSTFormatter('[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s')
    fh.setFormatter(file_formatter)
    logger.addHandler(fh)
except IOError:
    logger.error(f"无法打开日志文件 {LOG_FILE_PATH} 进行写入。")

# --- Core Functions ---
def read_youtube_ids(file_path: str) -> list:
    ids = []
    logger.info(f"尝试从文件读取YouTube ID: {file_path}")
    try:
        with open(file_path, mode='r', encoding='utf-8-sig') as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader, None)
            if header:
                logger.debug(f"已跳过表头行: {header}")
            else:
                logger.warning(f"CSV文件 {file_path} 为空或没有表头。")
                return []
            for i, row in enumerate(reader, 1):
                if row:
                    video_id = row[0].strip()
                    if video_id:
                        ids.append(video_id)
                        logger.debug(f"读取到Video ID: {video_id}")
                    else:
                        logger.warning(f"CSV文件 {file_path} 第 {i+1} 行（数据行 {i}）的ID为空。")
                else:
                     logger.warning(f"CSV文件 {file_path} 第 {i+1} 行（数据行 {i}）为空行。")
        logger.info(f"成功从 {file_path} 读取 {len(ids)} 个Video ID。")
    except FileNotFoundError:
        logger.error(f"CSV文件未找到: {file_path}")
    except Exception as e:
        logger.error(f"读取CSV文件 {file_path} 时发生错误: {e}", exc_info=True)
    return ids

# <<< 修改点：增加 current_index 和 total_count 参数 >>>
def fetch_srt_data(youtube_id: str, current_index: int, total_count: int) -> str | None:
    payload = {
        "youtube_id": youtube_id,
        "fetch_only": "false"
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SRTFetcherPythonScript/1.0"
    }

    # <<< 修改点：创建日志前缀，包含循环因子 >>>
    log_prefix = f"[处理 {current_index}/{total_count} - ID: {youtube_id}]"

    logger.info(f"{log_prefix} 准备发送请求...") # 控制台可见，现在也带了前缀

    # --- 构造并记录模拟的 CURL 命令 (DEBUG级别, 主要写入文件) ---
    curl_headers_str = ""
    for key, value in headers.items():
        curl_headers_str += f" -H \"{key}: {value}\""
    
    pretty_payload_for_curl_log = json.dumps(payload, indent=2, ensure_ascii=False)
    
    curl_command_log = f"""{log_prefix}
vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv
模拟CURL命令 (供参考)
--------------------------------------------------------------------------------
curl -X POST \\{curl_headers_str} \\
-d '{json.dumps(payload)}' \\
{API_URL}
--------------------------------------------------------------------------------
请求体 (美化格式):
{pretty_payload_for_curl_log}
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
"""
    logger.debug(curl_command_log)

    # --- 记录实际发送的请求细节 (DEBUG级别) ---
    logger.debug(f"{log_prefix} --> 实际请求目标 URL: {API_URL}")
    logger.debug(f"{log_prefix} --> 实际请求方法: POST")
    logger.debug(f"{log_prefix} --> 实际请求头 (美化):\n{json.dumps(headers, indent=2, ensure_ascii=False)}")
    logger.debug(f"{log_prefix} --> 实际请求体 (美化):\n{json.dumps(payload, indent=2, ensure_ascii=False)}")

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)

        # --- 记录接收到的响应细节 (DEBUG级别, 主要写入文件) ---
        logger.debug(f"{log_prefix} <-- 响应状态码: {response.status_code}")
        
        response_headers_dict = dict(response.headers)
        logger.debug(f"{log_prefix} <-- 响应头 (美化):\n{json.dumps(response_headers_dict, indent=2, ensure_ascii=False)}")
        
        response_body_text = response.text
        log_entry_for_response_body = f"{log_prefix} <-- 响应体:\n"
        try:
            parsed_json_response = json.loads(response_body_text)
            pretty_response_body = json.dumps(parsed_json_response, indent=2, ensure_ascii=False)
            log_entry_for_response_body += pretty_response_body
        except json.JSONDecodeError:
            log_entry_for_response_body += response_body_text
        logger.debug(log_entry_for_response_body)

        # --- 控制台INFO级别日志，简洁报告结果 ---
        response_snippet = response_body_text[:150] + '...' if len(response_body_text) > 150 else response_body_text
        if 200 <= response.status_code < 300:
            logger.info(f"{log_prefix} 成功 (状态码: {response.status_code}). 响应片段: {response_snippet}")
            return response_body_text
        else:
            logger.warning(f"{log_prefix} 失败 (状态码: {response.status_code}). 响应片段: {response_snippet}")
            return None

    except requests.exceptions.Timeout:
        logger.error(f"{log_prefix} 请求URL {API_URL} 超时。", exc_info=False)
    except requests.exceptions.ConnectionError:
        logger.error(f"{log_prefix} 连接URL {API_URL} 失败。", exc_info=False)
    except requests.exceptions.RequestException as e:
        logger.error(f"{log_prefix} 发送请求时发生错误: {e}", exc_info=True)
    return None

# --- Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从CSV文件读取YouTube ID并获取SRT数据。")
    parser.add_argument(
        "csv_file",
        nargs="?",
        default=DEFAULT_CSV_FILE_PATH,
        help=f"包含YouTube ID的CSV文件路径。默认为: '{DEFAULT_CSV_FILE_PATH}'"
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=1,
        help="每个请求之间的延迟时间（秒）。默认为1秒。"
    )
    args = parser.parse_args()

    logger.info("SRT Fetcher (Python脚本) 开始运行...")
    logger.info(f"将使用CSV文件: {args.csv_file}")
    logger.info(f"日志将输出到控制台 (INFO级别及以上) 和文件: {LOG_FILE_PATH} (DEBUG级别及以上)")
    logger.info(f"请求之间的延迟设置为: {args.delay} 秒")

    youtube_ids_list = read_youtube_ids(args.csv_file)

    if not youtube_ids_list:
        logger.warning("没有需要处理的YouTube ID。脚本退出。")
    else:
        total_ids_count = len(youtube_ids_list) # <<< 修改点：变量名更清晰 >>>
        logger.info(f"开始处理 {total_ids_count} 个YouTube ID...")
        
        for index, current_video_id in enumerate(youtube_ids_list):
            # 下面这行INFO日志主要用于控制台实时显示当前处理到哪个ID，本身已包含循环因子
            logger.info(f"主循环: 正在处理第 {index + 1}/{total_ids_count} 个ID: {current_video_id}")
            
            # <<< 修改点：传递 current_index 和 total_count 给 fetch_srt_data >>>
            api_response = fetch_srt_data(current_video_id, index + 1, total_ids_count)
            
            if index < total_ids_count - 1:
                if args.delay > 0:
                    logger.debug(f"暂停 {args.delay} 秒后处理下一个请求...")
                    time.sleep(args.delay)

        logger.info("所有YouTube ID处理完毕。")
    logger.info("SRT Fetcher (Python脚本) 运行结束。")
