# TC002 矛盾覆写测试数据
# 测试目标：验证决策迭代时返回最新版本的准确率

# 迭代决策序列（3次迭代）
DECISION_SEQUENCE = [
    {
        "id": "dec_002_v1",
        "content": "周报每周五发给张三",
        "source": "飞书群聊",
        "sender": "@Manager",
        "timestamp": "2026-04-15 10:00:00",
        "expected_state": "ARCHIVED",  # 被v2覆盖
        "evolution_type": "ROOT",
    },
    {
        "id": "dec_002_v2",
        "content": "周报以后发给李四，不用发张三了",
        "source": "飞书群聊",
        "sender": "@Manager",
        "timestamp": "2026-04-16 10:00:00",  # v1之后1天
        "expected_state": "ARCHIVED",  # 被v3覆盖
        "evolution_type": "SUPERSEDES",
        "parent_id": "dec_002_v1",
    },
    {
        "id": "dec_002_v3",
        "content": "周报调整为每周四发给李四，抄送给张三",
        "source": "飞书群聊",
        "sender": "@Manager",
        "timestamp": "2026-04-17 10:00:00",  # v2之后1天
        "expected_state": "ACTIVE",
        "evolution_type": "SUPERSEDES",
        "parent_id": "dec_002_v2",
    },
]

# 查询用例
QUERIES = [
    {
        "query": "周报现在要发给谁？",
        "expected_value": "李四（主送），张三（抄送）",
        "expected_answer_segments": ["李四", "每周四"],
        "fail_answer_segments": ["每周五", "只发张三", "发给张三"],
        "pass_condition": "回答明确包含'李四'且包含'每周四'，且不包含'每周五'",
    },
    {
        "query": "周报的发件频率变了吗？",
        "expected_value": "从周五改为周四",
        "pass_condition": "回答包含'周四'",
    },
    {"query": "周报还抄送谁？", "expected_value": "张三", "pass_condition": "回答包含'张三'"},
    {"query": "原来周报发给谁？", "expected_value": "张三", "pass_condition": "回答包含'张三'"},
]

# 边界场景测试
BOUNDARY_CASES = [
    {
        "name": "跨源矛盾",
        "description": "群聊说发给李四、文档写发给王五",
        "setup": [
            {
                "id": "dec_bc1_v1",
                "content": "周报每周五发给李四",
                "source": "飞书群聊",
                "source_type": "USER_STATED",
            },
            {
                "id": "dec_bc1_v2",
                "content": "周报每周五发给王五",
                "source": "飞书文档",
                "source_type": "DOC_SYNCED",
            },
        ],
        "expected_resolution": "按provenance权重仲裁：USER_STATED(1.0) > DOC_SYNCED(0.85)",
        "expected_final_value": "李四",
    },
    {
        "name": "时序错乱",
        "description": "新决策先收到、旧决策后收到（事件乱序）",
        "setup": [
            {
                "id": "dec_bc2_v1",
                "content": "周报发给李四",
                "logical_time": "2026-04-17 10:00:00",
                "receive_time": "2026-04-20 09:00:00",
            },
            {
                "id": "dec_bc2_v2",
                "content": "周报发给王五",
                "logical_time": "2026-04-15 10:00:00",
                "receive_time": "2026-04-20 10:00:00",
            },
        ],
        "expected_resolution": "按logical_timestamp（消息原始时间）仲裁",
        "expected_final_value": "李四",
    },
    {
        "name": "软冲突",
        "description": "A说主要发给张三、B说也抄送李四",
        "setup": [
            {"id": "dec_bc3_v1", "content": "周报主要发给张三", "source": "飞书群聊"},
            {"id": "dec_bc3_v2", "content": "周报也抄送李四", "source": "飞书群聊"},
        ],
        "expected_resolution": "判REFINES而非SUPERSEDES，v1保持ACTIVE",
        "expected_final_value": "主送张三，抄送李四",
    },
    {
        "name": "多跳覆盖",
        "description": "A→B→C三次迭代",
        "setup": [
            {"id": "dec_bc4_v1", "content": "周报发给张三", "evolution": "ROOT"},
            {
                "id": "dec_bc4_v2",
                "content": "周报改发给李四",
                "evolution": "SUPERSEDES",
                "parent": "dec_bc4_v1",
            },
            {
                "id": "dec_bc4_v3",
                "content": "周报改发给王五",
                "evolution": "SUPERSEDES",
                "parent": "dec_bc4_v2",
            },
        ],
        "expected_resolution": "A、B均为ARCHIVED，仅C为ACTIVE",
        "expected_final_value": "王五",
    },
]

# 测试配置
TEST_CONFIG = {
    "iteration_count": 3,
    "time_intervals": [
        {"from": "v1", "to": "v2", "days": 1},
        {"from": "v2", "to": "v3", "days": 1},
    ],
    "pass_threshold": 0.95,
    "expected_main_arch_pass_rate": 0.95,
    "expected_baseline_pass_rate": 0.4,
}
