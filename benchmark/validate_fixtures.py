#!/usr/bin/env python3
"""快速验证 benchmark/fixtures 中的测试数据是否正确加载。

用法（在仓库根目录）：
    python -m benchmark.validate_fixtures
    # 或
    python benchmark/validate_fixtures.py
"""
import sys
from pathlib import Path

# 允许直接 `python benchmark/validate_fixtures.py` 运行（脚本模式）
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.fixtures.tc001_anti_interference import (  # noqa: E402
    CORE_DECISION,
    NOISE_MESSAGES,
    QUERIES as TC001_QUERIES,
    TEST_CONFIG as TC001_CONFIG,
)
from benchmark.fixtures.tc002_contradiction import (  # noqa: E402
    DECISION_SEQUENCE,
    BOUNDARY_CASES,
    TEST_CONFIG as TC002_CONFIG,
)

print('=' * 60)
print('TC001 抗干扰召回测试数据概览')
print('=' * 60)
print(f'核心决策: {CORE_DECISION["content"]}')
print(f'关键字段: {CORE_DECISION["key"]}')
print(f'预期答案: {CORE_DECISION["expected_answer"]}')
print(f'噪声消息数量: {len(NOISE_MESSAGES)} 条')
print()
print('噪声分布:')
types = {}
for msg in NOISE_MESSAGES:
    t = msg['type']
    types[t] = types.get(t, 0) + 1
for t, c in types.items():
    print(f'  {t}: {c} 条')
print()
print(f'查询用例数量: {len(TC001_QUERIES)} 条')
print('查询示例:')
for q in TC001_QUERIES[:2]:
    print(f'  Q: {q["query"]}')
    print(f'    预期值: {q["expected_value"]}')
print()
print('=' * 60)
print('TC002 矛盾覆写测试数据概览')
print('=' * 60)
print(f'迭代决策数量: {len(DECISION_SEQUENCE)} 条')
print()
print('迭代序列:')
for d in DECISION_SEQUENCE:
    print(f'  {d["id"]}: {d["content"]}')
    print(f'    预期状态: {d["expected_state"]}')
print()
print(f'边界场景数量: {len(BOUNDARY_CASES)} 条')
print('边界场景:')
for bc in BOUNDARY_CASES:
    print(f'  {bc["name"]}: {bc["description"]}')
print()
print('=' * 60)
print('测试配置')
print('=' * 60)
print(f'TC001: 噪声目标{TC001_CONFIG["total_noise_count"]}条，模拟{TC001_CONFIG["simulation_days"]}天')
print(f'TC001: 通过阈值{TC001_CONFIG["pass_threshold"]*100}%')
print(f'TC002: 迭代{TC002_CONFIG["iteration_count"]}次，通过阈值{TC002_CONFIG["pass_threshold"]*100}%')
print()
print('✅ 测试数据加载成功！')