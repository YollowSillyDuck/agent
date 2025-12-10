import pytest
import os

from agent import DSLAgent
import handlers_example


@pytest.fixture
def agent_banking(tmp_path):
    # Create an agent and inject small test data for banking
    agent = DSLAgent()
    # Avoid external normalizer in tests
    os.environ.pop('ARK_API_KEY', None)
    # sample accounts
    agent.data = {
        'accounts': [
            {"account_id": "a001", "user_id": "u001", "type": "储蓄", "balance": 5234.56},
            {"account_id": "a002", "user_id": "u002", "type": "信用卡", "balance": -1200.0},
        ]
    }
    # load banking DSL
    here = os.path.dirname(__file__)
    root = os.path.dirname(here)
    script = os.path.join(root, 'examples', 'banking.dsl')
    agent.load_script(script)
    handlers_example.register(agent)
    return agent


@pytest.fixture
def agent_food(tmp_path):
    agent = DSLAgent()
    os.environ.pop('ARK_API_KEY', None)
    # sample orders
    agent.data = {
        'orders': [
            {"order_id": 1001, "status": "配送中", "eta_minutes": 15},
            {"order_id": 1002, "status": "已送达", "eta_minutes": 0},
        ]
    }
    here = os.path.dirname(__file__)
    root = os.path.dirname(here)
    script = os.path.join(root, 'examples', 'food.dsl')
    agent.load_script(script)
    handlers_example.register(agent)
    return agent
