import csv, time 
import pandas as pd


def init_files(result_dir, checkpoint_file):
    """初始化存储目录和检查点文件"""
    result_dir.mkdir(parents=True, exist_ok=True)
    if not checkpoint_file.exists():
        with open(checkpoint_file, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(['task_id', "question", 'true_answer', 'response', "status", "timestamp"])


def load_processed(checkpoint_file):
    """增强版已处理记录加载"""
    processed = {}
    if checkpoint_file.exists():
        with open(checkpoint_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 使用task_id+问题哈希值作为唯一键
                unique_key = f"{row['task_id']}"
                processed[unique_key] = row['status']
    return processed


def save_result(question_data, response, result_dir, checkpoint_file, failed_checkpoint_file, is_error=False):
    """原子化保存结果"""
    timestamp = time.strftime("%Y%m%d%H%M%S")
    filename = "errors.parquet" if is_error else "results.parquet"

    # 构建完整数据记录
    record = {
        **question_data.to_dict(),  # 保留原始数据所有字段
        "task_success": True if is_error else False,
        'record_result': response
    }

    # 使用pandas追加模式写入Parquet（比CSV/JSON更高效）
    df = pd.DataFrame([record])
    output_path = result_dir / filename

    if output_path.exists():
        existing_df = pd.read_parquet(output_path)
        df = pd.concat([existing_df, df])
    df = df.applymap(str)
    df.to_parquet(output_path, index=False)

    # 更新检查点文件（新增原始数据索引）
    if not is_error:
        with open(checkpoint_file, 'a') as f:
            writer = csv.writer(f)
            writer.writerow([
                question_data['task_id'],  # 假设原始数据有唯一标识列
                question_data['question'],
                question_data['true_answer'] if 'true_answer' in question_data else None,
                response,
                "error" if is_error else "success",
                timestamp
            ])
    else:
        with open(failed_checkpoint_file, 'a') as f:
            writer = csv.writer(f)
            writer.writerow([
                question_data['task_id'],  # 假设原始数据有唯一标识列
                question_data['question'],
                question_data['true_answer'] if 'true_answer' in question_data else None,
                response,
                "error" if is_error else "success",
                timestamp
            ])
