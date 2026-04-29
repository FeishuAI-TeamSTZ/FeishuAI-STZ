"""feishu_integration — 飞书生态接入层（R2 接入工程师领地）。

入口：
    webhook            飞书事件接收（FastAPI router）
    message_handler    群消息事件 → cold_path
    doc_handler        文档变更事件 → cold_path
    okr_sync           OKR API（v1 fixture / v2 真接入）
    approval_sync      审批 API（v1 fixture）
    minutes_sync       妙记 API（v1 fixture）
    calendar_sync      日历 API（v1 fixture）
    bot_sender         Bot 推送卡片
    card_responder     用户卡片响应捕获

详见 docs/04-ENGUIDE.md §1 + §8.10。
"""
