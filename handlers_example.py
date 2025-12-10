# Example of registering external handlers for the DSL agent
# This file should not be required by the agent; it's a usage example.

from agent import DSLAgent


def order_status_handler(agent: DSLAgent, user_input: str, intent: str, context: dict = None):
    """Example handler for ORDER_STATUS.

    Two modes:
    - Called normally: try to extract order id from user_input; if none, ask for it and set pending.
    - Called with context (pending): treat user_input as the slot value (order id) and respond.
    """
    import re
    # If called as follow-up (context provided), try to extract order id from the reply as well
    if context and context.get('slot') == 'order_id':
        m = re.search(r"(\d{2,6})", user_input)
        if m:
            order_id = m.group(1)
        else:
            # If no digits found, ask again for a clearer order id
            return {
                'ask': '没能识别到订单号，请只回复订单号数字（例如：1001）：',
                'pending': {'intent': 'ORDER_STATUS', 'slot': 'order_id', 'data': {}}
            }
    else:
        m = re.search(r"(\d{2,6})", user_input)
        if not m:
            # ask for order id and set pending
            return {
                'ask': '请提供订单号（例如 1001）：',
                'pending': {'intent': 'ORDER_STATUS', 'slot': 'order_id', 'data': {}}
            }
        order_id = m.group(1)

    orders = agent.data.get('orders') or []
    for o in orders:
        if str(o.get('order_id')) == str(order_id):
            eta = o.get('eta_minutes')
            status = o.get('status', '未知')
            if eta and int(eta) > 0:
                return f"订单 {order_id} 的当前状态：{status}，预计 {eta} 分钟送达。"
            return f"订单 {order_id} 的当前状态：{status}。"
    return f"未找到订单号 {order_id}。"


def cancel_order_handler(agent: DSLAgent, user_input: str, intent: str, context: dict = None):
    import re, json, os
    # Follow-up mode
    # If in follow-up, attempt to extract numeric order id from user's reply
    if context and context.get('slot') == 'order_id':
        m = re.search(r"(\d{2,6})", user_input)
        if m:
            order_id = m.group(1)
        else:
            return {
                'ask': '没能识别到订单号，请只回复订单号数字（例如：1001）：',
                'pending': {'intent': 'CANCEL_ORDER', 'slot': 'order_id', 'data': {}}
            }
    else:
        m = re.search(r"(\d{2,6})", user_input)
        if not m:
            return {
                'ask': '请提供要取消的订单号：',
                'pending': {'intent': 'CANCEL_ORDER', 'slot': 'order_id', 'data': {}}
            }
        order_id = m.group(1)

    orders = agent.data.get('orders') or []
    for o in orders:
        if str(o.get('order_id')) == str(order_id):
            o['status'] = '已取消'
            # attempt to persist (best-effort)
            try:
                data_dir = os.path.join(os.path.dirname(__file__), 'data')
                with open(os.path.join(data_dir, 'orders.json'), 'w', encoding='utf-8') as f:
                    json.dump(orders, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            return f"订单 {order_id} 已为您取消。"
    return f"未找到订单号 {order_id}，无法取消。"


def balance_inquiry_handler(agent: DSLAgent, user_input: str, intent: str, context: dict = None):
    """Example handler for BALANCE_INQUIRY.

    If account type not provided, ask follow-up and set pending slot 'account_type'.
    If called with context {'slot': 'account_type'}, treat user_input as slot value and return balance.
    """
    accounts = agent.data.get('accounts') or []
    if not accounts:
        return None

    # If this is a follow-up answering the slot
    if context and context.get('slot') == 'account_type':
        wanted = user_input.strip()
        # 支持用户输入账户ID（例如 a001）或账户类型（比如 储蓄/信用卡/储蓄账户）
        # 先尝试按 account_id 精确匹配
        # 1) 精确或包含匹配 account_id / user_id / name
        try:
            wanted_norm = agent._normalize_text(wanted)
        except Exception:
            wanted_norm = wanted.lower()

        for a in accounts:
            # 1) 精确 account_id 匹配（不区分大小写）
            if str(a.get('account_id', '')).lower() == wanted.lower():
                return f"账户 {a.get('account_id')}（{a.get('type')}）当前余额：{a.get('balance')} 元。"

            # 2) 精确或包含匹配（account_id / user_id / name / type），然后回退到模糊相似度匹配
            fields = [str(a.get('account_id', '')), str(a.get('user_id', '')), str(a.get('type', ''))]
            if a.get('name'):
                fields.append(str(a.get('name')))

            matched = False
            for f in fields:
                try:
                    f_norm = agent._normalize_text(f)
                except Exception:
                    f_norm = f.lower()
                # 先尝试子串匹配
                if wanted_norm in f_norm or f_norm in wanted_norm:
                    matched = True
                    break
                # 回退到模糊匹配（使用 agent 提供的 fuzzy_match）
                try:
                    if agent.fuzzy_match(wanted, f, threshold=0.68):
                        matched = True
                        break
                except Exception:
                    pass

            if matched:
                return f"账户 {a.get('account_id')}（{a.get('type')}）当前余额：{a.get('balance')} 元。"

        # 2) 如果没有匹配到，作为兜底返回未找到
        return f"未找到匹配 '{wanted}' 的账户。"

    # Try to detect account type in the initial query
    if '信用' in user_input or '信用卡' in user_input:
        for a in accounts:
            if '信用' in str(a.get('type', '')):
                return f"账户 {a.get('account_id')}（{a.get('type')}）当前余额：{a.get('balance')} 元。"

    # Ask which account type
    return {
        'ask': '请问您要查询哪个账户的余额？（例如：储蓄/信用卡）',
        'pending': {'intent': 'BALANCE_INQUIRY', 'slot': 'account_type', 'data': {}}
    }


def register(agent: DSLAgent):
    """Register example handlers onto a DSLAgent instance.

    Call this from your application to attach the example handlers.
    """
    agent.handlers['ORDER_STATUS'] = order_status_handler
    agent.handlers['CANCEL_ORDER'] = cancel_order_handler
    agent.handlers['BALANCE_INQUIRY'] = balance_inquiry_handler


if __name__ == '__main__':
    agent = DSLAgent()
    register(agent)
    # Start interactive loop
    print('Registered example handlers for ORDER_STATUS, CANCEL_ORDER and BALANCE_INQUIRY')
    print('Run agent by importing this file or registering handlers from your application code.')
