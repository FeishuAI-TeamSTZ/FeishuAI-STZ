# 飞书 API 调研

## 一、消息收发

### 1.1 接收群消息（事件订阅）

飞书支持 Webhook 推送消息到我们的服务。

```python
from flask import Flask, request

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def handle_message():
    event = request.json.get("event", {})
    chat_id = event.get("message", {}).get("chat_id")
    content = event.get("message", {}).get("content")  # JSON 字符串
    
    # 解析消息
    import json
    msg_type = event.get("message", {}).get("msg_type")
    if msg_type == "text":
        text = json.loads(content).get("text", "")
        # TODO: 发送给记忆引擎处理
```

### 1.2 发送消息

```python
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

当检测到决策冲突时，发送带按钮的卡片让用户确认。

```python
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
    httpx.post("https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {token}"},
        json={"receive_id": chat_id, "msg_type": "interactive", "content": json.dumps(card)})
```

---

## 二、用户信息

### 2.1 查询用户

根据名字或 ID 查询用户信息（用于显示决策责任人）。

```python
def get_user(open_id):
    return httpx.get(
        f"https://open.feishu.cn/open-apis/contact/v3/users/{open_id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"user_id_type": "open_id"}
    ).json()
```

---

## 三、文档和知识库

### 3.1 读写飞书文档

将重要决策同步到飞书文档。

```python
# 创建文档
def create_doc(title):
    resp = httpx.post(
        "https://open.feishu.cn/open-apis/doc/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": title}
    )
    return resp.json()["data"]["document"]["document_id"]

# 读取文档内容（用于上下文输入）
def read_doc(doc_token):
    resp = httpx.get(
        f"https://open.feishu.cn/open-apis/doc/v1/documents/{doc_token}/blocks",
        headers={"Authorization": f"Bearer {token}"}
    )
    # 解析 blocks 获取文本内容
```

### 3.2 知识库

```python
# 添加到知识库
def add_to_wiki(title, content, parent_node_id):
    httpx.post(
        "https://open.feishu.cn/open-apis/wiki/v2/spaces",
        headers={"Authorization": f"Bearer {token}"},
        json={"obj_type": 2, "parent_node_id": parent_node_id, "title": title}
    )
```

---

## 四、日历和任务

### 4.1 创建日历事件

当决策涉及时间点时，自动创建日历提醒。

```python
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

```python
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

```python
def get_token():
    resp = httpx.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": "cli_xxx", "app_secret": "xxx"}
    )
    return resp.json()["tenant_access_token"]
```

---

## 六、飞书 CLI 快速命令

```bash
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

| 场景 | 用到的 API |
|------|-----------|
| 实时感知群聊决策 | 事件订阅 im.message.receive_v1 |
| 冲突时确认 | 发送卡片 + 处理卡片回调 |
| 显示责任人 | contact/v3/users 查询用户 |
| 重要决策归档 | wiki 或 docs 创建文档 |
| 决策涉及时间点 | calendar 创建事件 |
| 转化为待办 | task 创建任务 |

---

## 八、权限配置

需要在飞书开放平台申请以下权限：

- `im:message` - 读取和发送消息
- `im:message:send_as_bot` - 机器人发消息
- `contact:user.id:read` - 读取用户 ID
- `docx:document:readonly` - 读取文档
- `wiki:space:create` - 创建知识库节点
- `calendar:event:create` - 创建日历事件
- `task:task:create` - 创建任务

建议使用 `lark-cli auth login --recommend` 自动配置常用权限。
