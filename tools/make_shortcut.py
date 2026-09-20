"""创建桌面「卷宗」快捷方式（纯 Python，不依赖 COM）。"""
import os

import pylnk3

DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
LNK = os.path.join(DESKTOP, "卷宗.lnk")

pylnk3.for_file(
    r"C:\Users\54780\.workbuddy\binaries\python\envs\default\Scripts\pythonw.exe",
    LNK,
    arguments=r'"G:\私\新建文件夹\星火ai应用\juanzong\desktop.py"',
    work_dir=r"G:\私\新建文件夹\星火ai应用\juanzong",
    icon_file=r"G:\私\新建文件夹\星火ai应用\juanzong\assets\juanzong.ico",
    description="卷宗 - 隐私优先的本地长文档智能工作台（端侧离线）",
)
print("created:", os.path.exists(LNK), "->", LNK)
