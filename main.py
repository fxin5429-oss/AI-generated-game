#!/usr/bin/env python3
"""晨光跳跃 - Dawn Leap

一款用 pygame 写的 2D 像素平台跳跃游戏。所有美术与音效都由代码程序化生成。

用法:
    python main.py                  开始游戏（从主菜单）
    python main.py --level 2        直接进入第 2 关
    python main.py --no-audio       关闭声音
    python main.py --profile 300    跑 300 帧后统计性能并退出
"""
from game import main

if __name__ == "__main__":
    raise SystemExit(main())
