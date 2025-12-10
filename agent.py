#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DSL 运行时与智能客服 Agent

功能：
- 加载并解析 DSL 脚本（使用现有的 `parser.DSLParser`）
- 根据脚本构建意图表
- 对用户输入先做基于规则的匹配（字符串/正则），未命中时回退到 LLM 进行意图识别
- 执行意图对应的响应（文本或代码响应的简单处理），并可管理简单的状态机

使用方法：
1) 安装依赖：`pip install -r requirements.txt`
2) 将 `OPENAI_API_KEY` 写入环境变量以启用线上意图识别（可选）
3) 运行：`python agent.py examples/food.dsl`

"""
import os
import re
import json
from typing import Dict, Any, List, Optional

try:
    import openai
except Exception:
    openai = None

from parser import DSLParser


class LLMClient:
    """简单封装：当设置了 OPENAI_API_KEY 时调用 OpenAI，否则使用本地 mock。"""
    def __init__(self, model: str = 'gpt-3.5-turbo'):
        self.model = model
        self.api_key = os.environ.get('OPENAI_API_KEY')
        if self.api_key and openai:
            openai.api_key = self.api_key

    def detect_intent(self, user_input: str, intents: Dict[str, List[str]]) -> str:
        """返回最可能的 intent 名称，或 'FALLBACK'。"""
        # 如果没有 API Key，则使用简单启发式：寻找包含关键词
        if not self.api_key or openai is None:
            # 词串匹配与 regex
            low = user_input.lower()
            for name, patterns in intents.items():
                for p in patterns:
                    if not p:
                        continue
                    if p.startswith('/') and p.endswith('/'):
                        try:
                            if re.search(p[1:-1], user_input):
                                return name
                        except re.error:
                            continue
                    else:
                        if p.lower() in low:
                            return name
            return 'FALLBACK'

        # 使用 OpenAI 进行分类
        prompt = self._build_prompt(user_input, intents)
        try:
            resp = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an intent classification assistant. Reply with the single intent name that best matches the user input, or FALLBACK if none."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=32,
                temperature=0
            )
            text = resp['choices'][0]['message']['content'].strip()
            # 解析返回，取第一个匹配的 intent 名称
            for token in re.split(r"\s|,|\n", text):
                if token in intents or token == 'FALLBACK':
                    return token
            # 回退到简单返回
            return text.split()[0]
        except Exception:
            return 'FALLBACK'

    def _build_prompt(self, user_input: str, intents: Dict[str, List[str]]) -> str:
        parts = [f"User Input: {user_input}", "Intents (name: examples):"]
        for name, patterns in intents.items():
            parts.append(f"- {name}: {patterns}")
        parts.append("Return only the best matching intent name or FALLBACK.")
        return '\n'.join(parts)


class DSLAgent:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.parser = DSLParser()
        self.intents: Dict[str, Dict[str, Any]] = {}
        self.state: Optional[str] = None
        self.llm = llm_client or LLMClient()
        # 调试开关，设置为 True 可打印匹配过程
        self.debug = False
        # 加载示例数据（如果存在 data/ 目录），但不和意图绑定
        # 数据加载为可选功能，供外部 handler 使用
        self.data = {}
        try:
            self._load_data_dir(os.path.join(os.path.dirname(__file__), 'data'))
        except Exception:
            self.data = {}

        # 外部可注册的 intent -> handler 映射（handler: func(agent, user_input, intent) -> Optional[response])
        self.handlers: Dict[str, Any] = {}
        # 挂起的跟进上下文：用于多轮槽位填充
        # 结构例如: {'intent': 'BALANCE_INQUIRY', 'slot': 'account_type', 'data': {}}
        self.pending: Optional[Dict[str, Any]] = None
        # 可选的文本规范化器（AI）。如果环境变量 ARK_API_KEY 存在，则尝试创建。
        # 仅在用户配置了 ARK_API_KEY 时才尝试创建 normalizer
        if os.environ.get('ARK_API_KEY'):
            try:
                from ai_normalizer import ArkNormalizer
                self.normalizer = ArkNormalizer()
            except Exception:
                self.normalizer = None
        else:
            self.normalizer = None

    def load_script(self, path: str):
        program = self.parser.parse_file(path)
        self._build_intents(program)

    def load_string(self, code: str):
        program = self.parser.parse_string(code)
        self._build_intents(program)

    def _build_intents(self, program):
        self.intents = {}
        for child in getattr(program, 'children', []):
            if getattr(child, 'node_type', None) == 'intent':
                name = child.get_attribute('name')
                raw_patterns = child.get_attribute('patterns') or []
                # 规范化 patterns：去掉外层引号、去除多余的逗号/空白
                patterns = []
                compiled = []
                for p in raw_patterns:
                    try:
                        if not isinstance(p, str):
                            s = str(p)
                        else:
                            s = p.strip()
                        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
                            s = s[1:-1]
                        if s.endswith(','):
                            s = s[:-1].strip()
                    except Exception:
                        s = str(p)

                    patterns.append(s)
                    # 预编译正则（支持以 /.../ 或 /.../i 格式）
                    if s.startswith('/') and s.rfind('/') > 0:
                        # 提取最后一个/之后的标志，如 /pattern/i
                        last_slash = s.rfind('/')
                        pattern_body = s[1:last_slash]
                        flags = 0
                        flag_str = s[last_slash+1:]
                        if 'i' in flag_str:
                            flags |= re.IGNORECASE
                        try:
                            regex_obj = re.compile(pattern_body, flags)
                            compiled.append({'type': 'regex', 'pattern': s, 're': regex_obj})
                        except re.error:
                            # 如果正则编译失败，则当作普通文本
                            tokens = self._extract_tokens(s)
                            compiled.append({'type': 'text', 'pattern': s, 'tokens': tokens})
                    else:
                        tokens = self._extract_tokens(s)
                        compiled.append({'type': 'text', 'pattern': s, 'tokens': tokens})
                response = child.get_attribute('response') or ''
                response_type = child.get_attribute('response_type') or 'text'
                next_state = child.get_attribute('next_state')
                priority = child.get_attribute('priority')
                self.intents[name] = {
                    'patterns': patterns,
                    'compiled': compiled,
                    'response': response,
                    'response_type': response_type,
                    'next_state': next_state,
                    'priority': priority,
                }
        if self.debug:
            print("Loaded intents:")
            for k, v in self.intents.items():
                print(k, 'patterns=', v.get('patterns'))

    def detect_intent(self, user_input: str) -> str:
        # 可选：先使用 external normalizer 将非结构化输入规范化为更易匹配的文本
        norm_input = user_input
        try:
            if getattr(self, 'normalizer', None):
                normalized = self.normalizer.normalize(user_input)
                if normalized and isinstance(normalized, str) and normalized.strip():
                    norm_input = normalized
                    if self.debug:
                        print(f"[normalizer] raw: {user_input!r} -> normalized: {norm_input!r}")
        except Exception:
            norm_input = user_input

        text_norm = self._normalize_text(norm_input)
        # 1) 规则匹配（优先）
        for name, info in self.intents.items():
            for entry in info.get('compiled', []):
                if entry['type'] == 'regex':
                    try:
                        if entry['re'].search(user_input):
                            if self.debug:
                                print(f"regex match: intent={name} pattern={entry['pattern']}")
                            return name
                    except re.error:
                        continue
                else:
                    # 使用预提取的 tokens 来匹配，避免 agent 中包含 DSL 特定词表
                    tokens = entry.get('tokens') or []
                    if tokens:
                        if self._match_tokens(text_norm, tokens):
                            if self.debug:
                                print(f"token match: intent={name} tokens={tokens} pattern={entry.get('pattern')}")
                            return name
                    else:
                        # 备用：直接使用原始模式字符串的子串匹配
                        pat = entry.get('pattern', '')
                        if pat and pat.strip() and pat.lower() in user_input.lower():
                            if self.debug:
                                print(f"substr match: intent={name} pattern={pat}")
                            return name

        # 2) LLM 回退
        intent = self.llm.detect_intent(user_input, {k: v['patterns'] for k, v in self.intents.items()})
        # 如果 LLM 回退且配置了 ARK API，则尝试使用 Ark 的意图识别作为补充
        if intent == 'FALLBACK':
            try:
                ark_key = os.environ.get('ARK_API_KEY')
                if ark_key:
                    from ai_normalizer import detect_intent_via_ark
                    ark_intent = detect_intent_via_ark(ark_key, user_input, {k: v['patterns'] for k, v in self.intents.items()})
                    if ark_intent and ark_intent in self.intents:
                        return ark_intent
            except Exception:
                pass
        return intent

    def _normalize_text(self, text: str) -> str:
        # 小写化，半角化，去除标点（保留中文汉字和数字字母）
        if not isinstance(text, str):
            text = str(text)
        s = text.strip()
        # 全角转半角
        def _dbc2sbc(u_text: str) -> str:
            res = []
            for ch in u_text:
                code = ord(ch)
                if code == 0x3000:
                    res.append(' ')
                elif 0xFF01 <= code <= 0xFF5E:
                    res.append(chr(code - 0xFEE0))
                else:
                    res.append(ch)
            return ''.join(res)
        s = _dbc2sbc(s)
        s = s.lower()
        # 去掉标点与符号：使用与平台兼容的正则，保留中文汉字、字母和数字
        # 说明：Python 的内置 re 不支持 \p{...} Unicode 属性类，因此用下面的替代表达式
        s = re.sub(r"[^0-9a-zA-Z_\u4e00-\u9fff]+", ' ', s)
        s = re.sub(r"\s+", ' ', s).strip()
        return s

    def _match_text_pattern(self, text_norm: str, pattern: str) -> bool:
        # 该方法已由基于 tokens 的匹配替代；保留兼容实现
        p_norm = self._normalize_text(pattern)
        parts = [t for t in p_norm.split(' ') if t]
        if not parts:
            return False
        if len(parts) == 1:
            return parts[0] in text_norm
        return all(tok in text_norm for tok in parts)

    def _extract_tokens(self, pattern: str) -> List[str]:
        """从模式文本中提取用于匹配的 token 列表（去除停用词/短词）。"""
        p = self._normalize_text(pattern)
        parts = [t for t in p.split(' ') if t and len(t) > 1]
        # 如果都是单字符，保留长度1的作为最后手段
        if not parts:
            parts = [t for t in p.split(' ') if t]
        return parts

    def _match_tokens(self, text_norm: str, tokens: List[str]) -> bool:
        """基于 tokens 的匹配策略：若 tokens 数量大于1，要求全部命中（AND）；否则任一命中即匹配（OR）。"""
        if not tokens:
            return False
        if len(tokens) == 1:
            return tokens[0] in text_norm
        return all(tok in text_norm for tok in tokens)

    def fuzzy_match(self, a: str, b: str, threshold: float = 0.72) -> bool:
        """基于归一化后的两段文本计算相似度，超过阈值则认为匹配。

        使用 stdlib `difflib.SequenceMatcher` 以避免额外依赖。
        """
        try:
            from difflib import SequenceMatcher
            if not a or not b:
                return False
            a_norm = self._normalize_text(a)
            b_norm = self._normalize_text(b)
            if not a_norm or not b_norm:
                return False
            r = SequenceMatcher(None, a_norm, b_norm).ratio()
            return r >= float(threshold)
        except Exception:
            return False

    def _heuristic_route(self, user_input: str) -> Optional[str]:
        """简单启发式：如果输入看起来像账户 ID 或与已有账户高度相似，则路由到 BALANCE_INQUIRY。

        返回 intent 名称或 None。
        """
        try:
            # 检查 data.accounts 中是否有 account_id 出现在用户输入中
            accounts = self.data.get('accounts') or []
            low = user_input.lower()
            # 直接按 account_id 精确或包含匹配
            for a in accounts:
                aid = str(a.get('account_id', '')).lower()
                if not aid:
                    continue
                if aid in low or low in aid:
                    return 'BALANCE_INQUIRY'

            # 按数字 id 模式（如 010 或 1001 等）尝试匹配
            import re
            m = re.search(r"\b[aA]?\d{2,4}\b", user_input)
            if m:
                token = m.group(0).lower()
                for a in accounts:
                    if token in str(a.get('account_id', '')).lower() or token in str(a.get('user_id', '')).lower():
                        return 'BALANCE_INQUIRY'

            # 模糊匹配账户名/类型
            for a in accounts:
                for f in (str(a.get('account_id', '')), str(a.get('user_id', '')), str(a.get('type', '')), str(a.get('name', ''))):
                    if f and self.fuzzy_match(f, user_input, threshold=0.65):
                        return 'BALANCE_INQUIRY'
        except Exception:
            return None
        return None

    def handle(self, user_input: str) -> Dict[str, Any]:
        # 如果存在挂起的跟进上下文，则优先将当前输入作为跟进内容处理
        if self.pending:
            pending_intent = self.pending.get('intent')
            handler = self.handlers.get(pending_intent)
            if handler:
                try:
                    # 尝试以 4 参数调用 handler(agent, user_input, intent, context)
                    out = None
                    try:
                        out = handler(self, user_input, pending_intent, self.pending)
                    except TypeError:
                        # 向后兼容：尝试 3 参数签名
                        out = handler(self, user_input, pending_intent)

                    result = {'intent': pending_intent, 'response': None, 'next_state': None}
                    if isinstance(out, dict):
                        # 如果 handler 要求继续挂起
                        if out.get('ask') and out.get('pending'):
                            # 更新 pending，上层继续等待用户输入
                            self.pending = out.get('pending')
                            result['response'] = out.get('ask')
                            return result
                        # 如果 handler 返回完整结果替换
                        result.update(out)
                        # 默认清除 pending 除非 handler 指明保留
                        if not out.get('keep_pending'):
                            self.pending = None
                        return result
                    elif isinstance(out, str):
                        # 单纯字符串返回，清除 pending
                        self.pending = None
                        return {'intent': pending_intent, 'response': out, 'next_state': None}
                except Exception:
                    # 出错则清除 pending 并继续正常解析流程
                    if self.debug:
                        import traceback
                        traceback.print_exc()
                    self.pending = None

        intent = self.detect_intent(user_input)
        # 启发式路由：如果未识别意图（FALLBACK），尝试根据内容直接路由到可能的 handler（例如账户 ID）
        if intent == 'FALLBACK' or intent not in self.intents:
            try:
                heuristic = self._heuristic_route(user_input)
                if heuristic and heuristic in self.handlers:
                    intent = heuristic
            except Exception:
                pass
        result = {'intent': intent, 'response': None, 'next_state': None}

        if intent == 'FALLBACK' or intent not in self.intents:
            # 默认fallback
            result['response'] = "抱歉，我没能理解您的意图。您可以换一种说法或联系客服。"
            return result

        info = self.intents.get(intent, {})
        # 基础响应来自 DSL 定义
        if info:
            if info.get('response_type') == 'text':
                result['response'] = info.get('response')
            else:
                result['response'] = f"[CODE RESPONSE]\n{info.get('response')}"
            if info.get('next_state'):
                self.state = info.get('next_state')
                result['next_state'] = self.state

        # 如果外部注册了 handler，则调用之；handler 可返回字符串或 dict 替换 response
        handler = self.handlers.get(intent)
        if handler:
            try:
                out = None
                try:
                    out = handler(self, user_input, intent)
                except TypeError:
                    # 如果 handler 支持 context 参数，会在 pending 分支中以 4 个参数被调用
                    out = handler(self, user_input, intent, None)

                if isinstance(out, dict):
                    # 支持 handler 返回 {'ask': '...', 'pending': {...}} 来发起槽位跟进
                    if out.get('ask') and out.get('pending'):
                        self.pending = out.get('pending')
                        result['response'] = out.get('ask')
                        return result
                    result.update(out)
                elif isinstance(out, str):
                    result['response'] = out
            except Exception:
                if self.debug:
                    import traceback
                    traceback.print_exc()

        return result

    def _load_data_dir(self, data_dir: str):
        """加载 data 目录下的所有 json 文件为示例数据。"""
        if not os.path.isdir(data_dir):
            return
        for name in os.listdir(data_dir):
            if name.endswith('.json'):
                key = name[:-5]
                path = os.path.join(data_dir, name)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        self.data[key] = json.load(f)
                except Exception:
                    self.data[key] = None



def _interactive_loop(agent: DSLAgent):
    print("进入交互模式，输入 'exit' 退出。")
    while True:
        try:
            text = input('> ')
        except KeyboardInterrupt:
            print('\n退出')
            break
        if not text:
            continue
        if text.strip().lower() in ('exit', 'quit'):
            break
        out = agent.handle(text)
        print(f"Intent: {out['intent']}")
        print(f"Response: {out['response']}")
        if out.get('next_state'):
            print(f"(转到状态: {out['next_state']})")


if __name__ == '__main__':
    import sys
    agent = DSLAgent()
    if len(sys.argv) > 1:
        script = sys.argv[1]
        agent.load_script(script)
        # 尝试自动加载示例 handlers（如果存在 handlers_example.register）
        try:
            import handlers_example
            if hasattr(handlers_example, 'register'):
                handlers_example.register(agent)
        except Exception:
            pass
    else:
        # 默认加载示例脚本
        here = os.path.dirname(__file__)
        example = os.path.join(here, 'examples', 'food.dsl')
        if os.path.exists(example):
            agent.load_script(example)
            # 尝试自动加载示例 handlers（如果存在 handlers_example.register）
            try:
                import handlers_example
                if hasattr(handlers_example, 'register'):
                    handlers_example.register(agent)
            except Exception:
                pass
        else:
            print('未提供脚本且未找到默认示例，退出')
            sys.exit(1)

    _interactive_loop(agent)
