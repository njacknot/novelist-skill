#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
章节字数检查脚本
检查指定章节文件的字数；默认只报告字数，传入最小字数时才作为硬门槛。
"""

import re
import sys
from pathlib import Path
from typing import Optional

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def count_chinese_words(text: str) -> int:
    """统计中文字数（排除标点符号和Markdown标记）"""
    # 移除Markdown标记
    text = re.sub(r'#{1,6}\s*', '', text)  # 标题
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # 粗体
    text = re.sub(r'\*(.*?)\*', r'\1', text)  # 斜体
    text = re.sub(r'~~(.*?)~~', r'\1', text)  # 删除线
    text = re.sub(r'`(.*?)`', r'\1', text)  # 行内代码
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)  # 链接

    # 统计中文字符（汉字）
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    return len(chinese_chars)


def extract_content_from_chapter(file_path: Path) -> str:
    """从章节文件中提取正文内容（排除标题等元数据）"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找正文开始位置（通常是第一个一级标题或二级标题之后）
    lines = content.split('\n')

    # 跳过开头的元数据（如 # 第XX章 标题）
    content_start = 0
    for i, line in enumerate(lines):
        if line.startswith('#') and '章' in line:
            content_start = i + 1
            break

    # 提取正文
    main_content = '\n'.join(lines[content_start:])
    return main_content


def _normalize_min_words(min_words: Optional[int]) -> Optional[int]:
    if min_words is None or min_words <= 0:
        return None
    return min_words


def check_chapter(file_path: str, min_words: Optional[int] = None) -> dict:
    """检查单个章节的字数"""
    path = Path(file_path)
    threshold = _normalize_min_words(min_words)

    if not path.exists():
        return {
            'file': str(path),
            'exists': False,
            'word_count': 0,
            'min_words': threshold,
            'status': 'error',
            'message': f'文件不存在: {file_path}'
        }

    main_content = extract_content_from_chapter(path)
    word_count = count_chinese_words(main_content)

    if threshold is None:
        status = 'pass'
        message = f'字数: {word_count} (仅报告，未设置硬下限)'
    else:
        status = 'pass' if word_count >= threshold else 'fail'
        message = f'字数: {word_count}' + (
            f' (✓ 达标)' if word_count >= threshold else f' (✗ 不足，需要至少 {threshold} 字)'
        )

    return {
        'file': str(path),
        'exists': True,
        'word_count': word_count,
        'min_words': threshold,
        'status': status,
        'message': message
    }


def check_all_chapters(directory: str, pattern: str = '第*.md', min_words: Optional[int] = None) -> list:
    """检查目录下所有符合模式的章节文件"""
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f'错误: 目录不存在 - {directory}')
        return []

    chapter_files = sorted(dir_path.glob(pattern))
    results = []

    for chapter_file in chapter_files:
        result = check_chapter(str(chapter_file), min_words)
        results.append(result)

    return results


def print_results(results: list, min_words: Optional[int] = None):
    """打印检查结果"""
    if not results:
        print('没有找到章节文件')
        return

    total_words = 0
    passed = 0
    failed = 0

    print('\n' + '=' * 60)
    print('章节字数检查报告')
    print('=' * 60)

    for result in results:
        if not result['exists']:
            print(f'\n❌ {result["file"]}')
            print(f'   {result["message"]}')
            continue

        total_words += result['word_count']
        if result['status'] == 'pass':
            passed += 1
            icon = '✅'
        else:
            failed += 1
            icon = '⚠️ '

        print(f'\n{icon} {Path(result["file"]).name}')
        print(f'   {result["message"]}')

    print('\n' + '-' * 60)
    print(f'总计: {len(results)} 章 | {passed} 章达标 | {failed} 章不足 | 总字数: {total_words:,}')
    print('-' * 60)

    threshold = _normalize_min_words(min_words)
    if failed > 0 and threshold is not None:
        print(f'\n⚠️  有 {failed} 章内容不足 {threshold} 字，建议使用扩充技巧:')
        print('   - 添加细节描写（环境、心理、动作）')
        print('   - 增加对话场景')
        print('   - 扩展人物内心活动')
        print('   - 补充背景故事')
        print(f'\n   参考: references/guides/content-expansion.md')
    elif threshold is None:
        print('\nℹ️  未设置硬性最低字数；本报告只统计字数，不阻断短章。')


def main():
    """主函数"""
    min_words = None

    if len(sys.argv) < 2:
        print('用法:')
        print('  检查单个章节: python check_chapter_wordcount.py <章节文件路径> [最小字数]')
        print('  检查所有章节: python check_chapter_wordcount.py --all <目录路径> [最小字数]')
        print('')
        print('示例:')
        print('  python check_chapter_wordcount.py novels/故事/第01章.md')
        print('  python check_chapter_wordcount.py novels/故事/第01章.md 3500')
        print('  python check_chapter_wordcount.py --all novels/故事')
        print('  python check_chapter_wordcount.py --all novels/故事 3500')
        return

    if sys.argv[1] == '--all':
        if len(sys.argv) < 3:
            print('错误: 使用 --all 时需要指定目录路径')
            return
        directory = sys.argv[2]
        min_words = int(sys.argv[3]) if len(sys.argv) > 3 else None
        results = check_all_chapters(directory, min_words=min_words)
        print_results(results, min_words)
    else:
        file_path = sys.argv[1]
        min_words = int(sys.argv[2]) if len(sys.argv) > 2 else None
        result = check_chapter(file_path, min_words)
        print_results([result], min_words)


if __name__ == '__main__':
    main()
