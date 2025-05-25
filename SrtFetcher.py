#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import logging
import time
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo # Requires Python 3.9+

# --- Configuration ---
API_URL = "https://lic.deepsrt.cc/webhook/get-srt-from-provider"
DEFAULT_CSV_FILE_PATH = "video_ids - Sheet1.csv" # 确保此文件与脚本在同一目录，或提供完整路径
LOG_FILE_PATH = "srt_fetcher_python.log" # 日志文件名
CST_TIMEZONE = ZoneInfo("Asia/Shanghai") # 中国标准时间

# --- Logger Setup with CST Timestamps ---
class CSTFormatter(logging.Formatter):
    """自定义日志格式化类，使用CST时区生成时间戳。"""
    def __init__(self, fmt=None, datefmt=None, style='%', validate=True, *, defaults=None):
        super().__init__(fmt, datefmt, style, validate, defaults=defaults)
        self.default_msec_format = '%s,%03d' # 确保毫秒的格式

    def formatTime(self, record, datefmt=None):
        # 将日志记录的创建时间转换为CST时区
        dt = datetime.fromtimestamp(record.created, tz=CST_TIMEZONE)
        if datefmt:
            s = dt.strftime(datefmt)
        else:
            # 默认时间格式: YYYY-MM-DD HH:MM:SS,ms +0800 (CST)
            s = f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}:{dt.second:02d},{int(dt.microsecond / 1000):03d} {dt.strftime('%z')}"
        return s

# 获取根logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # 设置logger的最低级别为DEBUG

# 控制台处理器 (INFO 级别及以上)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
console_formatter = CSTFormatter('[%(asctime)s] [%(levelname)s] - %(message)s',
                                 datefmt='%Y-%m-%d %H:%M:%S %Z') # 控制台时间格式可以简洁一些
ch.setFormatter(console_formatter)
logger.addHandler(ch)

# 文件处理器 (DEBUG 级别及以上)
try:
    fh = logging.FileHandler(LOG_FILE_PATH, encoding='utf-8', mode='a') # 追加模式
    fh.setLevel(logging.DEBUG)
    # 文件日志格式包含更详细的信息，如模块和行号
    file_formatter = CSTFormatter('[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s')
    fh.setFormatter(file_formatter)
    logger.addHandler(fh)
except IOError:
    logger.error(f"无法打开日志文件 {LOG_FILE_PATH} 进行写入。")


# --- Core Functions ---
def read_youtube_ids(file_path: str) -> list:
    """
    从CSV文件中读取YouTube ID。
    假设第一行是表头并跳过。
    """
    ids = []
    logger.info(f"尝试从文件读取YouTube ID: {file_path}")
    try:
        with open(file_path, mode='r', encoding='utf-8-sig') as csvfile: # utf-8-sig 处理BOM
            reader = csv.reader(csvfile)
            header = next(reader, None) # 读取并跳过表头
            if header:
                logger.debug(f"已跳过表头行: {header}")
            else:
                logger.warning(f"CSV文件 {file_path} 为空或没有表头。")
                return []

            for i, row in enumerate(reader, 1): # 从1开始计数行号（数据行）
                if row: # 确保行不为空
                    video_id = row[0].strip() # 取第一列并去除空白
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

def fetch_srt_data(youtube_id: str) -> str | None:
    """
    向API发送POST请求获取SRT数据，并记录详细的请求和响应信息。
    """
    payload = {
        "youtube_id": youtube_id,
        "fetch_only": "false"  # 根据您的示例，"false" 是一个字符串
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SRTFetcherPythonScript/1.0" # 建议添加User-Agent
    }

    logger.info(f"准备为YouTube ID发送请求: {youtube_id}")
    
    # 记录请求详情 (DEBUG级别)
    logger.debug(f"--> 请求目标 URL: {API_URL}")
    logger.debug(f"--> 请求方法: POST")
    logger.debug(f"--> 请求头: {json.dumps(headers, indent=2)}")
    logger.debug(f"--> 请求体: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=60) # 设置60秒超时

        # 记录响应详情 (DEBUG级别)
        logger.debug(f"<-- 响应状态码 for {youtube_id}: {response.status_code}")
        # 将响应头转换为字典再序列化，以便阅读
        response_headers_dict = dict(response.headers)
        logger.debug(f"<-- 响应头 for {youtube_id}: {json.dumps(response_headers_dict, indent=2, ensure_ascii=False)}")
        
        response_body_text = response.text
        # 避免日志中出现过大的响应体，可以截断或仅在特定条件下记录完整响应体
        log_response_body = response_body_text[:1000] + "..." if len(response_body_text) > 1000 else response_body_text
        logger.debug(f"<-- 响应体 for {youtube_id} (截断): {log_response_body}")


        if 200 <= response.status_code < 300:
            logger.info(f"成功获取YouTube ID {youtube_id} 的数据。状态码: {response.status_code}")
            return response_body_text # 返回完整的响应体
        else:
            logger.warning(f"获取YouTube ID {youtube_id} 数据失败。状态码: {response.status_code}. 响应体: {response_body_text[:500]}") # 记录部分错误响应
            return None

    except requests.exceptions.Timeout:
        logger.error(f"请求YouTube ID {youtube_id} 至URL {API_URL} 超时。", exc_info=False) # exc_info=False 避免完整堆栈
    except requests.exceptions.ConnectionError:
        logger.error(f"连接YouTube ID {youtube_id} 至URL {API_URL} 失败。", exc_info=False)
    except requests.exceptions.RequestException as e:
        logger.error(f"为YouTube ID {youtube_id} 发送请求时发生错误: {e}", exc_info=True)
    return None

# --- Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从CSV文件读取YouTube ID并获取SRT数据。")
    parser.add_argument(
        "csv_file",
        nargs="?", # 使参数变为可选
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
        total_ids = len(youtube_ids_list)
        logger.info(f"开始处理 {total_ids} 个YouTube ID...")
        
        for index, current_video_id in enumerate(youtube_ids_list):
            logger.info(f"正在处理第 {index + 1}/{total_ids} 个ID: {current_video_id}")
            api_response = fetch_srt_data(current_video_id)
            # 此处可以根据 api_response 做进一步处理，例如保存到文件
            # if api_response:
            #     with open(f"{current_video_id}.srt", "w", encoding="utf-8") as f:
            #         f.write(api_response)
            #     logger.info(f"YouTube ID {current_video_id} 的SRT数据已保存到 {current_video_id}.srt")

            if index < total_ids - 1: # 如果不是最后一个ID，则执行延迟
                if args.delay > 0:
                    logger.debug(f"暂停 {args.delay} 秒后处理下一个请求...")
                    time.sleep(args.delay)

        logger.info("所有YouTube ID处理完毕。")
    logger.info("SRT Fetcher (Python脚本) 运行结束。")
