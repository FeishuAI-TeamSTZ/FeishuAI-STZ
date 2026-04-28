# 飞书 API 调研

本文档调研飞书开放平台 API，聚焦于记忆引擎可能用到的功能。

---

## 一、消息收发

消息是记忆引擎的核心数据源。群聊中的决策讨论需要实时捕获，同时系统也需要主动推送确认卡片。

### 1.1 接收群消息（事件订阅）

飞书支持 Webhook 推送，当有人在群里发消息时，会把消息推送到我们的服务。

使用场景：实时监听群聊，提取决策相关内容；或者在有人 @ 机器人时响应。

注意事项：
- 需要公网可访问的 HTTPS 地址
- 飞书要求 3 秒内返回 200，否则会重试
- 开发阶段可用 ngrok 做内网穿透

代码示例：

```
from flask import Flask, request

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def handle_message():
    event = request.json.get("event", {})
    chat_id = event.get("message", {}).get("chat_id")
    content = event.get("message", {}).get("content")

    msg_type = event.get("message", {}).get("msg_type")
    if msg_type == "text":
        import json
        text = json.loads(content).get("text", "")
        # TODO: 发送给记忆引擎处理
```

### 1.2 发送消息

用于向群里发送简单的文本通知。

使用场景：记忆被更新时通知相关人员；确认操作完成后回复。

代码示例：

```
import httpx

def send_message(chat_id, text):
    httpx.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text})
        }
    )
```

### 1.3 发送交互卡片

卡片比普通消息功能更丰富，可以加按钮、下拉菜单等。

使用场景：当检测到决策冲突时，发送带按钮的卡片让用户选择"保留原决策"或"更新为新决策"。

代码示例：

```
def send_confirm_card(chat_id, original, new):
    card = {
        "card": {
            "header": {"title": {"content": "⚠️ 决策冲突"}, "template": "red"},
            "elements": [
                {"tag": "div", "text": {"content": f"**原决策**：{original}\n**新讨论**：{new}"}},
                {"tag": "action", "actions": [
                    {"tag": "button", "text": {"content": "保留原决策"}, "type": "primary"},
                    {"tag": "button", "text": {"content": "更新为新决策"}, "type": "default"}
                ]}
            ]
        }
    }
    httpx.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}"},
        json={"receive_id": chat_id, "msg_type": "interactive", "content": json.dumps(card)}
    )
```

用户点击按钮后，飞书会回调我们指定的地址，我们需要处理回调并更新记忆。

---

## 二、用户信息

有时候需要知道"这条决策是谁说的"，或者"应该通知谁"。

### 2.1 查询用户

根据 open_id 查询用户基本信息（名字、头像、职位等）。

使用场景：显示决策责任人；发送通知时显示发送者名字。

代码示例：

```
def get_user(open_id):
    return httpx.get(
        f"https://open.feishu.cn/open-apis/contact/v3/users/{open_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"user_id_type": "open_id"}
    ).json()
```

---

## 三、文档和知识库

决策不能只存在数据库里，需要同步到飞书，方便相关人员查看和编辑。

### 3.1 读写飞书文档

可以创建新文档，也可以读取现有文档的内容。

使用场景：重要决策自动归档到飞书文档；读取飞书文档作为上下文输入给记忆引擎。

代码示例：

```
# 创建文档
def create_doc(title):
    resp = httpx.post(
        "https://open.feishu.cn/open-apis/doc/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": title}
    )
    return resp.json()["data"]["document"]["document_id"]

# 读取文档内容
def read_doc(doc_token):
    resp = httpx.get(
        f"https://open.feishu.cn/open-apis/doc/v1/documents/{doc_token}/blocks",
        headers={"Authorization": f"Bearer {token}"}
    )
```

### 3.2 知识库

知识库比普通文档更有条理，可以按主题组织节点。

使用场景：按项目或部门建立决策知识库，方便检索。

代码示例：

```
def add_to_wiki(title, content, parent_node_id):
    httpx.post(
        "https://open.feishu.cn/open-apis/wiki/v2/spaces",
        headers={"Authorization": f"Bearer {token}"},
        json={"obj_type": 2, "parent_node_id": parent_node_id, "title": title}
    )
```

---

## 四、日历和任务

决策最终要落地，需要转化为日历事件或待办任务。

### 4.1 创建日历事件

当决策涉及时间点时（比如"项目 A 5 月 15 号上线"），自动创建日历提醒。

使用场景：关键时间节点自动建日程；决策评审会议。

代码示例：

```
def create_calendar_event(title, start_time, attendees):
    httpx.post(
        "https://open.feishu.cn/open-apis/calendar/v4/calendars/primary/events",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "summary": title,
            "start_time": {"timestamp": str(int(start_time.timestamp()))},
            "end_time": {"timestamp": str(int(start_time.timestamp()) + 3600)},
            "attendees": [{"type": "user", "user_id": uid} for uid in attendees]
        }
    )
```

### 4.2 创建任务

将决策转化为待办，跟踪执行情况。

使用场景：需要某人跟进的事项；定期检查决策执行状态。

代码示例：

```
def create_task(title, due_date, assignee):
    httpx.post(
        "https://open.feishu.cn/open-apis/task/v2/tasks",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": title,
            "due": {"timestamp": str(int(due_date.timestamp()))},
            "members": [{"id": assignee, "type": "user", "role": "assignee"}]
        }
    )
```

---

## 五、认证

调用飞书 API 之前，需要先获取 access_token。

代码示例：

```
def get_token():
    resp = httpx.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": "cli_xxx", "app_secret": "xxx"}
    )
    return resp.json()["tenant_access_token"]
```

注意：token 有时效性（约 2 小时），频繁调用时注意刷新。

---

## 六、飞书 CLI 快速命令

如果不想写代码，可以直接用命令行操作飞书。适合调试和快速测试。

```
# 发送消息
lark-cli im +messages-send --chat-id "oc_xxx" --text "决策已记录"

# 查看日历
lark-cli calendar +agenda

# 创建文档
lark-cli docs +create --title "周报" --content "# 内容"

# 创建任务
lark-cli task +create --title "完成XX" --due "2024-05-01"

# 搜索用户
lark-cli contact users search --name "张三"
```

---

## 七、本项目可能用到的场景

| 场景 | 用到的 API | 说明 |
|------|-----------|------|
| 实时感知群聊决策 | 事件订阅 im.message.receive_v1 | 飞书主动推送，需要公网地址 |
| 冲突时确认 | 发送卡片 + 处理卡片回调 | 按钮点击后飞书回调我们 |
| 显示责任人 | contact/v3/users 查询用户 | 根据 open_id 获取用户信息 |
| 重要决策归档 | wiki 或 docs 创建文档 | 同步到飞书方便查看 |
| 决策涉及时间点 | calendar 创建事件 | 自动建日程提醒 |
| 转化为待办 | task 创建任务 | 跟踪执行 |

---

## 八、权限配置

接入飞书 API 之前，需要在飞书开放平台创建应用并申请权限。

| 权限 | 用途 |
|------|------|
| im:message | 读取群消息 |
| im:message:send_as_bot | 机器人发送消息 |
| contact:user.id:read | 查询用户信息 |
| docx:document:readonly | 读取文档内容 |
| wiki:space:create | 创建知识库节点 |
| calendar:event:create | 创建日历事件 |
| task:task:create | 创建待办任务 |

建议使用 `lark-cli auth login --recommend` 自动配置常用权限，会一步步引导你完成认证。