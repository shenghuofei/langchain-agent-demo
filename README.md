# LangChain Agent Demo

这是一个使用 Python 和 LangChain 编写的命令行 Agent 示例。

Agent 通过 OpenAI 兼容接口调用大语言模型，并根据用户请求自动选择工具。
项目同时适用于 OpenAI API、企业内部 OpenAI-compatible 网关，以及其他兼容 ChatGPT/Responses API 的服务。

## 功能

- 普通中文对话
- 数学表达式计算
- 查询指定时区的当前时间
- 保存本地笔记
- 根据关键词搜索本地笔记
- 多轮对话上下文
- 使用 LangChain `create_agent` 创建 Agent
- 使用 OpenAI Responses API 处理工具调用

## 项目结构

```text
langchain-agent-demo/
├── main.py                  # Agent 和工具实现
├── requirements.txt         # Python 依赖
├── .env.example             # 环境变量模板，不包含真实密钥
├── .gitignore               # 忽略密钥、本地数据和缓存
├── data/
│   └── notes.json           # 本地笔记，运行时生成，不提交到 Git
└── README.md
```

## 环境要求

- Python 3.10 或更高版本
- 一个支持工具调用的 OpenAI-compatible 模型服务
- API Key
- 网关支持 `/v1/responses` 接口

当前示例默认使用：

```text
gpt-6.1-sol
```

这是一个网关侧的模型名称。你需要根据自己的 API Key 权限，替换成服务端实际可用的模型 ID。

## 安装

### 使用 Conda

```bash
conda create -n langchain-agent python=3.11 -y
conda activate langchain-agent
```

### 安装 Python 依赖

```bash
pip install -U -r requirements.txt
```

## 配置环境变量

复制配置模板：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
LLM_API_KEY=你的_API_Key
LLM_MODEL=gpt-6.1-sol
LLM_BASE_URL=https://your-llm-gateway.example.com
```

`LLM_BASE_URL` 可以填写网关根地址，也可以填写已经包含 `/v1` 的地址。程序会自动避免重复添加 `/v1`。

例如：

```env
LLM_BASE_URL=https://example.com
```

或者：

```env
LLM_BASE_URL=https://example.com/v1
```

程序也兼容旧版变量名：

```env
CLAUDE_API_KEY=你的_API_Key
CLAUDE_MODEL=gpt-6.1-sol
CLAUDE_BASE_URL=https://your-llm-gateway.example.com
```

新项目建议使用 `LLM_*` 变量。

## 运行

```bash
python main.py
```

启动后可以尝试：

```text
计算 (123.45 + 67.8) * 2
```

```text
现在上海几点？
```

```text
记住：我的项目名称是智能客服系统
```

```text
搜索智能客服
```

输入以下任意内容退出：

```text
exit
quit
q
```

## 工具说明

### `calculate`

使用 Python AST 对数学表达式进行受限解析，不直接执行 `eval`。
支持加、减、乘、除、整除、取模、幂运算和括号。

### `get_current_time`

使用 Python `zoneinfo` 查询指定时区的当前时间。
例如：

```text
查询东京现在的时间
```

### `save_note`

将笔记保存到本地：

```text
data/notes.json
```

该文件被 `.gitignore` 忽略，避免将个人或业务数据提交到 GitHub。

### `search_notes`

根据关键词搜索本地笔记的标题和内容。

## 网关兼容性

当前代码使用：

```python
ChatOpenAI(
    use_responses_api=True,
    output_version="responses/v1",
)
```

因此网关需要支持：

```text
POST /v1/responses
```

并且模型需要支持工具调用。

如果服务端只支持 `/v1/chat/completions`，同时模型要求关闭推理参数，可以将模型初始化调整为：

```python
model = ChatOpenAI(
    model=model_name,
    api_key=api_key,
    base_url=base_url,
    model_kwargs={
        "max_completion_tokens": 4096,
        "reasoning_effort": "none",
    },
    use_responses_api=False,
)
```

具体参数以网关管理员提供的接口文档为准。

## 常见错误

### API Key 无权访问模型

错误示例：

```text
key not allowed to access model
```

说明当前 API Key 没有该模型的访问权限。需要使用 API Key 能访问的模型 ID，或者申请新的权限。

如果网关支持模型列表接口，可以尝试：

```bash
curl -sS "$LLM_BASE_URL/v1/models" \
  -H "Authorization: Bearer $LLM_API_KEY"
```

### 模型不支持 `temperature`

部分推理模型不支持 `temperature`。当前示例不会主动传入 `temperature`。

### 工具调用和推理参数冲突

如果出现类似：

```text
Function tools with reasoning_effort are not supported
```

优先确认网关是否支持 `/v1/responses`。当前代码默认使用 Responses API。

### `/v1/responses` 返回 404

说明网关可能只实现了 Chat Completions API，需要联系网关管理员确认接口路径，或切换到服务端支持的调用方式。

## 安全注意事项

不要提交以下内容：

- `.env`
- 真实 API Key
- 用户数据或业务数据
- 私钥文件
- 内部数据库配置
- 真实的 `data/notes.json`

提交代码前检查：

```bash
git status --short
git diff --cached
git check-ignore -v .env data/notes.json
```

如果 API Key 曾经提交到 Git 历史，单纯删除文件并不能解决问题。应立即撤销旧 Key、生成新 Key，并清理 Git 历史。

## GitHub 上传

确认没有敏感文件后：

```bash
git init
git add .
git status
git commit -m "初始化 LangChain Agent 示例"
```

创建 GitHub 仓库后，再执行：

```bash
git branch -M main
git remote add origin https://github.com/你的用户名/你的仓库名.git
git push -u origin main
```

## 参考资料

- [LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain ChatOpenAI](https://docs.langchain.com/oss/python/integrations/chat/openai)
- [LangChain Tools](https://docs.langchain.com/oss/python/langchain/tools)
