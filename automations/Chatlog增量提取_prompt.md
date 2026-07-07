# Chatlog 每小时增量提取 - Automation Prompt

**Automation ID:** automation-1779420446485  
**Schedule:** 每小时 (FREQ=HOURLY;INTERVAL=1)  
**Status:** ACTIVE

---

## Prompt 内容

```
执行 chatlog.py 增量提取：运行 python "C:\Users\济南府\.workbuddy\skills/机械姬Soli/scripts/soli_memory/chatlog.py" extract，将系统 JSONL 中新对话记录提取到 skills/机械姬Soli/MEMORY/chatlog/ 目录。若 python 不可用则用 python3。完成后输出提取条数。然后运行 python "C:\Users\济南府\.workbuddy\skills\机械姬Soli\scripts\build_memory_viz.py" 无须其他额外操作。

不要写日记。
```

---

## 备注

- 此自动化任务负责增量提取 chatlog 到 `MEMORY/chatlog/` 目录
- 同时运行 `build_memory_viz.py` 构建记忆可视化
- 每小时执行一次，确保 chatlog 实时同步
- 脚本路径：`scripts/soli_memory/chatlog.py`
