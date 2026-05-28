"""
DeepSeek Monitor - 启动脚本
双击此文件或在终端运行: python run.py
"""
import sys
import os

# 确保当前目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import main

if __name__ == "__main__":
    main()
