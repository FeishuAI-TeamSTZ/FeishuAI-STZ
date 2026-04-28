# TC001 抗干扰召回测试数据
# 测试目标：验证大噪声环境下长期记忆的召回能力

# 核心决策（系统需要在7天后仍能正确召回）
CORE_DECISION = {
    "decision_id": "dec_001",
    "content": "项目A上线日期定在2026-05-15",
    "source": "飞书群聊",
    "sender": "@TechLead",
    "timestamp": "2026-04-20 14:30:00",
    "provenance": "USER_STATED",
    "key": "项目A上线日期",
    "expected_answer": "2026-05-15"
}

# 噪声消息集（1000条，实际生成100条样例）
NOISE_MESSAGES = [
    # 日常闲聊 (30%)
    {"id": "msg_001", "content": "大家下午好呀，今天天气真不错 ☀️", "type": "日常闲聊", "timestamp": "2026-04-20 15:00:00"},
    {"id": "msg_002", "content": "收到，已读不回 😎", "type": "日常闲聊", "timestamp": "2026-04-20 15:20:00"},
    {"id": "msg_003", "content": "👍👍👍", "type": "表情", "timestamp": "2026-04-20 15:35:00"},
    {"id": "msg_004", "content": "哈哈哈哈哈笑死我了", "type": "日常闲聊", "timestamp": "2026-04-20 16:00:00"},
    {"id": "msg_005", "content": "周末有人要一起吃饭吗？", "type": "日常闲聊", "timestamp": "2026-04-20 16:30:00"},
    {"id": "msg_006", "content": "有人知道附近哪家咖啡好喝吗", "type": "日常闲聊", "timestamp": "2026-04-20 17:00:00"},
    {"id": "msg_007", "content": "这个表情包太可爱了", "type": "日常闲聊", "timestamp": "2026-04-20 17:30:00"},
    {"id": "msg_008", "content": "下班一起去打球吗？", "type": "日常闲聊", "timestamp": "2026-04-20 18:00:00"},
    {"id": "msg_009", "content": "好的收到", "type": "日常闲聊", "timestamp": "2026-04-20 18:30:00"},
    {"id": "msg_010", "content": "👍", "type": "表情", "timestamp": "2026-04-20 19:00:00"},
    {"id": "msg_011", "content": "辛苦大家了", "type": "日常闲聊", "timestamp": "2026-04-20 19:30:00"},
    {"id": "msg_012", "content": "明天见", "type": "日常闲聊", "timestamp": "2026-04-20 20:00:00"},
    {"id": "msg_013", "content": "这个方案不错", "type": "日常闲聊", "timestamp": "2026-04-21 09:00:00"},
    {"id": "msg_014", "content": "👍👍", "type": "表情", "timestamp": "2026-04-21 09:30:00"},
    {"id": "msg_015", "content": "好的", "type": "日常闲聊", "timestamp": "2026-04-21 10:00:00"},
    {"id": "msg_016", "content": "收到通知", "type": "日常闲聊", "timestamp": "2026-04-21 10:30:00"},
    {"id": "msg_017", "content": "这个思路可以", "type": "日常闲聊", "timestamp": "2026-04-21 11:00:00"},
    {"id": "msg_018", "content": "👌", "type": "表情", "timestamp": "2026-04-21 11:30:00"},
    {"id": "msg_019", "content": "了解", "type": "日常闲聊", "timestamp": "2026-04-21 12:00:00"},
    {"id": "msg_020", "content": "好的好的", "type": "日常闲聊", "timestamp": "2026-04-21 12:30:00"},
    {"id": "msg_021", "content": "👍", "type": "表情", "timestamp": "2026-04-21 13:00:00"},
    {"id": "msg_022", "content": "明白了", "type": "日常闲聊", "timestamp": "2026-04-21 13:30:00"},
    {"id": "msg_023", "content": "收到", "type": "日常闲聊", "timestamp": "2026-04-21 14:00:00"},
    {"id": "msg_024", "content": "OK", "type": "日常闲聊", "timestamp": "2026-04-21 14:30:00"},
    {"id": "msg_025", "content": "👍👍👍", "type": "表情", "timestamp": "2026-04-21 15:00:00"},
    {"id": "msg_026", "content": "大家加油", "type": "日常闲聊", "timestamp": "2026-04-21 15:30:00"},
    {"id": "msg_027", "content": "这个建议不错", "type": "日常闲聊", "timestamp": "2026-04-21 16:00:00"},
    {"id": "msg_028", "content": "👍", "type": "表情", "timestamp": "2026-04-21 16:30:00"},
    {"id": "msg_029", "content": "好的", "type": "日常闲聊", "timestamp": "2026-04-21 17:00:00"},
    {"id": "msg_030", "content": "明白", "type": "日常闲聊", "timestamp": "2026-04-21 17:30:00"},

    # 技术讨论 (30%)
    {"id": "msg_031", "content": "这个接口文档写得真详细，点赞👍", "type": "技术讨论", "timestamp": "2026-04-20 15:05:00"},
    {"id": "msg_032", "content": "项目B的代码评审谁有空看一下？", "type": "技术讨论", "timestamp": "2026-04-20 15:10:00"},
    {"id": "msg_033", "content": "哪位大神知道这个bug怎么解？", "type": "技术讨论", "timestamp": "2026-04-20 15:45:00"},
    {"id": "msg_034", "content": "这段代码写得真烂，谁写的？", "type": "技术讨论", "timestamp": "2026-04-20 15:30:00"},
    {"id": "msg_035", "content": "建议用这个库来处理", "type": "技术讨论", "timestamp": "2026-04-20 16:15:00"},
    {"id": "msg_036", "content": "这个设计模式用得不错", "type": "技术讨论", "timestamp": "2026-04-20 16:45:00"},
    {"id": "msg_037", "content": "有没有人熟悉React的？", "type": "技术讨论", "timestamp": "2026-04-20 17:15:00"},
    {"id": "msg_038", "content": "这个bug我之前遇到过", "type": "技术讨论", "timestamp": "2026-04-20 17:45:00"},
    {"id": "msg_039", "content": "可以用缓存优化一下", "type": "技术讨论", "timestamp": "2026-04-20 18:15:00"},
    {"id": "msg_040", "content": "这个日志需要加密处理", "type": "技术讨论", "timestamp": "2026-04-20 18:45:00"},
    {"id": "msg_041", "content": "API文档更新了", "type": "技术讨论", "timestamp": "2026-04-21 08:30:00"},
    {"id": "msg_042", "content": "这个函数需要加异常处理", "type": "技术讨论", "timestamp": "2026-04-21 09:15:00"},
    {"id": "msg_043", "content": "数据库索引加了吗？", "type": "技术讨论", "timestamp": "2026-04-21 10:15:00"},
    {"id": "msg_044", "content": "这个配置需要放到环境变量里", "type": "技术讨论", "timestamp": "2026-04-21 11:15:00"},
    {"id": "msg_045", "content": "单元测试覆盖率要提到80%", "type": "技术讨论", "timestamp": "2026-04-21 12:15:00"},
    {"id": "msg_046", "content": "这个需求有点复杂", "type": "技术讨论", "timestamp": "2026-04-21 13:15:00"},
    {"id": "msg_047", "content": "需要做性能优化", "type": "技术讨论", "timestamp": "2026-04-21 14:15:00"},
    {"id": "msg_048", "content": "这个分支可以合并了", "type": "技术讨论", "timestamp": "2026-04-21 15:15:00"},
    {"id": "msg_049", "content": "建议用异步处理", "type": "技术讨论", "timestamp": "2026-04-21 16:15:00"},
    {"id": "msg_050", "content": "这段逻辑可以抽象成公共方法", "type": "技术讨论", "timestamp": "2026-04-21 17:15:00"},
    {"id": "msg_051", "content": "需要加重试机制", "type": "技术讨论", "timestamp": "2026-04-21 18:15:00"},
    {"id": "msg_052", "content": "这个接口需要限流", "type": "技术讨论", "timestamp": "2026-04-22 09:00:00"},
    {"id": "msg_053", "content": "日志级别要调整一下", "type": "技术讨论", "timestamp": "2026-04-22 10:00:00"},
    {"id": "msg_054", "content": "这个异常需要特殊处理", "type": "技术讨论", "timestamp": "2026-04-22 11:00:00"},
    {"id": "msg_055", "content": "可以考虑用观察者模式", "type": "技术讨论", "timestamp": "2026-04-22 12:00:00"},
    {"id": "msg_056", "content": "这段代码可以简化", "type": "技术讨论", "timestamp": "2026-04-22 13:00:00"},
    {"id": "msg_057", "content": "需要加监控告警", "type": "技术讨论", "timestamp": "2026-04-22 14:00:00"},
    {"id": "msg_058", "content": "建议用设计模式重构一下", "type": "技术讨论", "timestamp": "2026-04-22 15:00:00"},
    {"id": "msg_059", "content": "这个配置需要加密存储", "type": "技术讨论", "timestamp": "2026-04-22 16:00:00"},
    {"id": "msg_060", "content": "需要做容量规划", "type": "技术讨论", "timestamp": "2026-04-22 17:00:00"},

    # 其他决策 (30%) - 注意：这些决策与项目A无关
    {"id": "msg_061", "content": "周会改到周三下午3点，大家注意一下", "type": "其他决策", "timestamp": "2026-04-20 15:15:00", "related_key": "周会时间"},
    {"id": "msg_062", "content": "数据库连接池大小调整到50", "type": "其他决策", "timestamp": "2026-04-20 15:25:00", "related_key": "数据库配置"},
    {"id": "msg_063", "content": "项目C的里程碑是6月1日", "type": "其他决策", "timestamp": "2026-04-20 15:40:00", "related_key": "项目C里程碑"},
    {"id": "msg_064", "content": "报销流程简化了，以后直接在系统提交", "type": "其他决策", "timestamp": "2026-04-20 16:20:00", "related_key": "报销流程"},
    {"id": "msg_065", "content": "下午2点有技术分享会", "type": "其他决策", "timestamp": "2026-04-20 16:50:00", "related_key": "技术分享"},
    {"id": "msg_066", "content": "下周一集体团建，大家安排好时间", "type": "其他决策", "timestamp": "2026-04-20 17:20:00", "related_key": "团建"},
    {"id": "msg_067", "content": "服务器带宽升级到500Mbps", "type": "其他决策", "timestamp": "2026-04-20 17:50:00", "related_key": "服务器配置"},
    {"id": "msg_068", "content": "密码策略更新为90天更换一次", "type": "其他决策", "timestamp": "2026-04-20 18:20:00", "related_key": "安全策略"},
    {"id": "msg_069", "content": "茶水间新增咖啡机一台", "type": "其他决策", "timestamp": "2026-04-20 18:50:00", "related_key": "办公设施"},
    {"id": "msg_070", "content": "代码规范文档已更新，请大家学习", "type": "其他决策", "timestamp": "2026-04-20 19:20:00", "related_key": "代码规范"},
    {"id": "msg_071", "content": "端午假期安排：6月1日-3日", "type": "其他决策", "timestamp": "2026-04-21 08:00:00", "related_key": "假期安排"},
    {"id": "msg_072", "content": "VPN需要重新配置，请联系IT", "type": "其他决策", "timestamp": "2026-04-21 08:45:00", "related_key": "IT服务"},
    {"id": "msg_073", "content": "门禁系统升级，周末无法刷卡", "type": "其他决策", "timestamp": "2026-04-21 09:45:00", "related_key": "门禁系统"},
    {"id": "msg_074", "content": "打印机换位置了，在走廊尽头", "type": "其他决策", "timestamp": "2026-04-21 10:45:00", "related_key": "办公设施"},
    {"id": "msg_075", "content": "新员工入职培训下周三开始", "type": "其他决策", "timestamp": "2026-04-21 11:45:00", "related_key": "入职培训"},
    {"id": "msg_076", "content": "会议室A改名为主题空间", "type": "其他决策", "timestamp": "2026-04-21 12:45:00", "related_key": "会议室"},
    {"id": "msg_077", "content": "停车位重新分配了，请查收邮件", "type": "其他决策", "timestamp": "2026-04-21 13:45:00", "related_key": "停车位"},
    {"id": "msg_078", "content": "空调使用规定：温度不低于26度", "type": "其他决策", "timestamp": "2026-04-21 14:45:00", "related_key": "空调使用"},
    {"id": "msg_079", "content": "快递统一寄到前台，不要送进办公区", "type": "其他决策", "timestamp": "2026-04-21 15:45:00", "related_key": "快递管理"},
    {"id": "msg_080", "content": "公司无线网络密码变更，请联系IT获取", "type": "其他决策", "timestamp": "2026-04-21 16:45:00", "related_key": "网络配置"},
    {"id": "msg_081", "content": "项目D的需求评审会延期到下周一", "type": "其他决策", "timestamp": "2026-04-21 17:45:00", "related_key": "项目D"},
    {"id": "msg_082", "content": "服务器维护窗口：每周日凌晨2-4点", "type": "其他决策", "timestamp": "2026-04-22 08:00:00", "related_key": "服务器维护"},
    {"id": "msg_083", "content": "供应商合同续签流程更新", "type": "其他决策", "timestamp": "2026-04-22 09:30:00", "related_key": "合同管理"},
    {"id": "msg_084", "content": "办公室绿植更换为人工植物", "type": "其他决策", "timestamp": "2026-04-22 10:30:00", "related_key": "办公环境"},
    {"id": "msg_085", "content": "考勤系统升级，请重新绑定手机", "type": "其他决策", "timestamp": "2026-04-22 11:30:00", "related_key": "考勤系统"},
    {"id": "msg_086", "content": "年度体检安排在5月中旬", "type": "其他决策", "timestamp": "2026-04-22 12:30:00", "related_key": "员工福利"},
    {"id": "msg_087", "content": "内部培训课时可兑换奖励", "type": "其他决策", "timestamp": "2026-04-22 13:30:00", "related_key": "培训奖励"},
    {"id": "msg_088", "content": "办公软件正版化检查开始了", "type": "其他决策", "timestamp": "2026-04-22 14:30:00", "related_key": "合规检查"},
    {"id": "msg_089", "content": "项目E启动会定于下周三下午", "type": "其他决策", "timestamp": "2026-04-22 15:30:00", "related_key": "项目E"},
    {"id": "msg_090", "content": "差旅报销标准调整，请查阅新政策", "type": "其他决策", "timestamp": "2026-04-22 16:30:00", "related_key": "差旅报销"},

    # 噪声字符/乱码 (10%)
    {"id": "msg_091", "content": "asdfghjkl", "type": "乱码", "timestamp": "2026-04-20 15:50:00"},
    {"id": "msg_092", "content": "哈哈哈哈哈哈哈哈哈哈哈哈", "type": "乱码", "timestamp": "2026-04-20 16:10:00"},
    {"id": "msg_093", "content": "😀😀😀😀😀", "type": "乱码", "timestamp": "2026-04-20 16:40:00"},
    {"id": "msg_094", "content": "test123456", "type": "乱码", "timestamp": "2026-04-20 17:10:00"},
    {"id": "msg_095", "content": "qwertyuiop", "type": "乱码", "timestamp": "2026-04-20 17:40:00"},
    {"id": "msg_096", "content": "👍👍👍👍👍", "type": "乱码", "timestamp": "2026-04-20 18:10:00"},
    {"id": "msg_097", "content": "...........", "type": "乱码", "timestamp": "2026-04-20 18:40:00"},
    {"id": "msg_098", "content": "！！！", "type": "乱码", "timestamp": "2026-04-20 19:10:00"},
    {"id": "msg_099", "content": "1234567890", "type": "乱码", "timestamp": "2026-04-20 19:40:00"},
    {"id": "msg_100", "content": "?????", "type": "乱码", "timestamp": "2026-04-20 20:10:00"},
]

# 查询用例
QUERIES = [
    {
        "query": "项目A什么时候上线？",
        "expected_key": "项目A上线日期",
        "expected_value": "2026-05-15",
        "pass_condition": "回答包含2026-05-15"
    },
    {
        "query": "项目A的deadline是哪天？",
        "expected_key": "项目A上线日期",
        "expected_value": "2026-05-15",
        "pass_condition": "回答包含2026-05-15"
    },
    {
        "query": "我们和项目A相关的计划是什么？",
        "expected_key": "项目A上线日期",
        "expected_value": "2026-05-15",
        "pass_condition": "回答包含2026-05-15"
    }
]

# 测试配置
TEST_CONFIG = {
    "total_noise_count": 1000,  # 目标噪声总数
    "noise_generated_count": 100,  # 已生成的样例数量
    "simulation_days": 7,  # 模拟时间流逝天数
    "pass_threshold": 0.9,  # 通过阈值（90%查询返回正确答案即通过）
    "expected_main_arch_pass_rate": 0.9,  # 主架构预期通过率
    "expected_baseline_pass_rate": 0.3,  # Baseline预期通过率
}