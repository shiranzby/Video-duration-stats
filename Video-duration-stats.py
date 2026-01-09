import os
import sys
import concurrent.futures
from collections import defaultdict
from moviepy.video.io.VideoFileClip import VideoFileClip

def get_video_duration(video_path):
    """获取单个视频的时长"""
    try:
        with VideoFileClip(video_path) as video:
            duration = video.duration
            print(f"文件: {video_path}, 时长: {duration:.2f} 秒")
            return video_path, duration
    except Exception as e:
        print(f"无法处理文件 {video_path}，错误: {e}")
        return video_path, 0

def calculate_folder_durations(folder_path):
    """
    计算每个目录（含子目录）的总视频时长
    """
    video_paths = []

    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(".mp4"):
                video_paths.append(os.path.join(root, file))

    if not video_paths:
        print("❌ 没有找到 mp4 文件")
        return {}

    folder_duration_map = defaultdict(float)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(get_video_duration, p) for p in video_paths]
        for future in concurrent.futures.as_completed(futures):
            video_path, duration = future.result()
            current_dir = os.path.dirname(video_path)

            # 向上逐级累加
            while True:
                folder_duration_map[current_dir] += duration
                if os.path.normpath(current_dir) == os.path.normpath(folder_path):
                    break
                parent = os.path.dirname(current_dir)
                if parent == current_dir:
                    break
                current_dir = parent

    folder_duration_map = merge_single_video_subfolder(folder_duration_map)
    return folder_duration_map

def merge_single_video_subfolder(folder_duration_map):
    """
    如果父文件夹只有一个包含视频的子文件夹，则合并到父文件夹显示
    """
    parent_map = defaultdict(list)
    for folder in folder_duration_map.keys():
        parent = os.path.dirname(folder)
        parent_map[parent].append(folder)

    merged_map = dict(folder_duration_map)

    for parent, children in parent_map.items():
        # 修复逻辑：如果父级本身不在统计范围内（比如是根目录的父级），则跳过，防止根目录被移除
        if parent not in merged_map:
            continue

        video_children = [c for c in children if folder_duration_map.get(c, 0) > 0]
        if len(video_children) == 1:
            child = video_children[0]
            # 修复逻辑：父级在前面的累加步骤中已经包含了子级的时长，不需要再次相加，只需移除子级显示即可
            merged_map.pop(child, None)

    return merged_map

def format_duration(seconds):
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    
    parts = []
    # 保持显示小时，即使是0小时，以维持格式整齐（除非你想完全隐藏）
    # 如果想完全隐藏0小时，可以将下面改成 if h > 0:
    parts.append(f"{h}小时")
    
    # 只有当分钟大于0时才显示
    if m > 0:
        parts.append(f"{m}分")
    
    # 只有当秒数大于0时才显示
    if s > 0:
        parts.append(f"{s}秒")
        
    # 如果总时长为0，parts可能只有一个"0小时"，或者如果不加小时可能为空
    if not parts:
        return "0秒"
        
    return " ".join(parts)

def build_tree(folder_durations, root_folder):
    """
    构建目录树，返回父->子字典
    """
    tree = defaultdict(list)
    folders = list(folder_durations.keys())
    folders.sort(key=lambda x: x.count(os.sep))  # 浅层先
    for folder in folders:
        parent = os.path.dirname(folder)
        if folder != root_folder:
            tree[parent].append(folder)
    return tree

def print_tree(folder_durations, root_folder, tree, current=None, level=0):
    """
    递归打印终端和生成 Markdown 顺序
    """
    if current is None:
        current = root_folder

    duration_text = format_duration(folder_durations.get(current, 0))
    print(f"{'#' * (level + 1)} {os.path.basename(current)}  {duration_text}")

    # 按名字排序子文件夹输出
    for child in sorted(tree.get(current, []), key=lambda x: os.path.basename(x)):
        print_tree(folder_durations, root_folder, tree, child, level + 1)

def export_markdown(folder_durations, root_folder):
    """
    导出 Markdown 文件，按树状顺序
    """
    folder_name = os.path.basename(root_folder.rstrip(os.sep))
    output_md = f"{folder_name}时长统计.md"
    tree = build_tree(folder_durations, root_folder)

    lines = []

    def add_lines(current=root_folder, level=0):
        duration_text = format_duration(folder_durations.get(current, 0))
        lines.append(f"{'#' * (level + 1)} {os.path.basename(current)}  {duration_text}")
        for child in sorted(tree.get(current, []), key=lambda x: os.path.basename(x)):
            add_lines(child, level + 1)

    add_lines()

    with open(output_md, "w", encoding="utf-8") as f:
        f.write("\n\n".join(lines))

    print(f"\n📄 已生成 Markdown 文件：{os.path.abspath(output_md)}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        root_folder = sys.argv[1]
    else:
        root_folder = input("请输入文件夹路径：")

    if not os.path.exists(root_folder):
        print(f"❌ 路径不存在：{root_folder}")
        sys.exit(1)

    folder_durations = calculate_folder_durations(root_folder)

    print("\n📊 各目录视频总时长统计：\n")
    tree = build_tree(folder_durations, root_folder)
    print_tree(folder_durations, root_folder, tree)

    export_markdown(folder_durations, root_folder)