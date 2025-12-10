import pytest


def test_balance_followup_by_id(agent_banking):
    out1 = agent_banking.handle('余额')
    assert out1['intent'] == 'BALANCE_INQUIRY'
    assert '请问' in out1['response']

    out2 = agent_banking.handle('a001')
    assert out2['intent'] == 'BALANCE_INQUIRY'
    assert 'a001' in out2['response'] or '余额' in out2['response']


def test_balance_followup_by_type(agent_banking):
    out1 = agent_banking.handle('余额')
    assert out1['intent'] == 'BALANCE_INQUIRY'

    out2 = agent_banking.handle('储蓄')
    assert out2['intent'] == 'BALANCE_INQUIRY'
    assert '储蓄' in out2['response']


def test_order_status_followup(agent_food):
    out1 = agent_food.handle('订单的状态')
    assert out1['intent'] == 'ORDER_STATUS'
    assert '请提供订单号' in out1['response']

    out2 = agent_food.handle('我要1001的订单')
    # handler should extract 1001
    assert out2['intent'] == 'ORDER_STATUS'
    assert ('1001' in out2['response']) or ('未找到订单号' in out2['response'])


def test_priorities_loaded(agent_banking):
    # Ensure priority field parsed from DSL
    pi = agent_banking.intents.get('BALANCE_INQUIRY')
    assert pi is not None
    assert 'priority' in pi
    assert isinstance(pi['priority'], (int, type(None)))
