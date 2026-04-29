"""memory_engine — 决策原子记忆引擎核心包（R1 内核工程师领地）。

七大机制：
    M1 全源跨系统一致性检测（extractor.py + consensus.py）
    M2 演化判定（evolution_judge.py + state_machine.py）
    M3 Reflect 自改进（reflect_agent.py）
    M4 Actor-Aware 溯源（types.py + config.py）
    M5 Hot/Cold 双路径（hot_path.py + cold_path.py）
    M6 卡片分层 + 闸门（cards.py）
    M7 五维自适应遗忘（decay.py）

详见 docs/04-ENGUIDE.md §8 接口契约总表。
"""

__version__ = "0.1.0"
