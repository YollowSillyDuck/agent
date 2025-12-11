简介
---
该仓库包含一个为智能客服设计的领域特定语言 (DSL) 的词法/语法解析器（`lexer.py`、`parser.py`），以及一个简单的运行时 agent (`agent.py`)。运行时支持规则匹配优先，然后在规则未命中的情况下回退到 LLM（OpenAI）做意图识别。

快速开始
---
1. 创建并激活 Python 虚拟环境（可选）

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
```

2. 安装依赖

```powershell
pip install -r requirements.txt
```

3. （可选）配置 OpenAI API Key

```powershell
$env:OPENAI_API_KEY = "sk-..."
```

4. 运行 agent（示例）

```powershell
python agent.py examples/food.dsl
```

交互说明
---
启动后可在交互命令行输入任意文本，agent 会先用 DSL 中 `patterns` 做匹配；未命中时会调用 LLM 进行意图识别，然后返回意图和响应。

DSL 语法概述
---
示例意图定义：

```
intent GREETING priority 10 {
    patterns: ["你好", "hi", "/hello/i"];
    response: "你好，我是客服小助手";
}
```

- `intent` 后跟名称，可选 `priority`，大括号内包含 `patterns:`（数组）、`response:`（文本或代码块）和可选的 `next_state:`。
- pattern 可以是字符串或 `/.../` 形式的正则表达式。

扩展与注意事项
---
- `agent.py` 中对 code 类型响应仅作原样返回；如果需要执行 DSL 中的代码响应，请扩展为安全的沙箱执行器。
- `parser.py` 已改为从本目录加载 `lexer.py`。
- 若要改进意图识别，请在 DSL 中提供更丰富的 `patterns` 或使用更强的 LLM 模型。
 - 可选：集成第三方 AI 进行“文本规范化”。如果你想把非结构化用户输入先交给 AI 做清洗/规范化，设置环境变量 `ARK_API_KEY`（或在代码中传入 key），agent 会在意图识别前调用该 normalizer。
        - 示例环境变量：
            - `ARK_API_KEY`: API Key（Bearer token）。
            - `ARK_API_URL`（可选）：覆盖默认的 `https://ark.cn-beijing.volces.com/api/v3/chat/completions`。
        - 使用时：安装 `requests`（已列入 `requirements.txt`），然后直接运行 `python agent.py ...` 即可（agent 会自动在启动时检测并创建 normalizer，如果 `ARK_API_KEY` 存在）。
 - Agent 与 DSL 已解耦：`agent.py` 不再内置与特定 intent 绑定的数据处理逻辑。要为特定意图添加数据驱动逻辑，请在外部注册 handler（参考 `handlers_example.py`）。
     - 注册方法：在你的应用代码中设置 `agent.handlers['INTENT_NAME'] = handler_func`。
     - handler 签名：`handler(agent, user_input, intent)`，可返回字符串（response）或字典来更新整个结果对象。
 - 模糊匹配：agent 提供基础的模糊匹配支持，示例 handler 使用 `agent.fuzzy_match(a, b)` 在账号名、类型、ID 等字段上做相似度比较，从而能容忍错别字与口语化表达。
