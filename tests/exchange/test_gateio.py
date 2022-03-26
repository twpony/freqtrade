from unittest.mock import MagicMock

import pytest

from freqtrade.enums import MarginMode, TradingMode
from freqtrade.exceptions import OperationalException
from freqtrade.exchange import Gateio
from freqtrade.resolvers.exchange_resolver import ExchangeResolver
from tests.conftest import get_patched_exchange


def test_validate_order_types_gateio(default_conf, mocker):
    default_conf['exchange']['name'] = 'gateio'
    mocker.patch('freqtrade.exchange.Exchange._init_ccxt')
    mocker.patch('freqtrade.exchange.Exchange._load_markets', return_value={})
    mocker.patch('freqtrade.exchange.Exchange.validate_pairs')
    mocker.patch('freqtrade.exchange.Exchange.validate_timeframes')
    mocker.patch('freqtrade.exchange.Exchange.validate_stakecurrency')
    mocker.patch('freqtrade.exchange.Exchange.validate_pricing')
    mocker.patch('freqtrade.exchange.Exchange.name', 'Bittrex')
    exch = ExchangeResolver.load_exchange('gateio', default_conf, True)
    assert isinstance(exch, Gateio)

    default_conf['order_types'] = {
        'entry': 'market',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    with pytest.raises(OperationalException,
                       match=r'Exchange .* does not support market orders.'):
        ExchangeResolver.load_exchange('gateio', default_conf, True)


def test_fetch_stoploss_order_gateio(default_conf, mocker):
    exchange = get_patched_exchange(mocker, default_conf, id='gateio')

    fetch_order_mock = MagicMock()
    exchange.fetch_order = fetch_order_mock

    exchange.fetch_stoploss_order('1234', 'ETH/BTC')
    assert fetch_order_mock.call_count == 1
    assert fetch_order_mock.call_args_list[0][1]['order_id'] == '1234'
    assert fetch_order_mock.call_args_list[0][1]['pair'] == 'ETH/BTC'
    assert fetch_order_mock.call_args_list[0][1]['params'] == {'stop': True}


def test_cancel_stoploss_order_gateio(default_conf, mocker):
    exchange = get_patched_exchange(mocker, default_conf, id='gateio')

    cancel_order_mock = MagicMock()
    exchange.cancel_order = cancel_order_mock

    exchange.cancel_stoploss_order('1234', 'ETH/BTC')
    assert cancel_order_mock.call_count == 1
    assert cancel_order_mock.call_args_list[0][1]['order_id'] == '1234'
    assert cancel_order_mock.call_args_list[0][1]['pair'] == 'ETH/BTC'
    assert cancel_order_mock.call_args_list[0][1]['params'] == {'stop': True}


@pytest.mark.parametrize('sl1,sl2,sl3,side', [
    (1501, 1499, 1501, "sell"),
    (1499, 1501, 1499, "buy")
])
def test_stoploss_adjust_gateio(mocker, default_conf, sl1, sl2, sl3, side):
    exchange = get_patched_exchange(mocker, default_conf, id='gateio')
    order = {
        'price': 1500,
        'stopPrice': 1500,
    }
    assert exchange.stoploss_adjust(sl1, order, side)
    assert not exchange.stoploss_adjust(sl2, order, side)


def test_fetch_order_gateio(mocker, default_conf):
    tick = {'ETH/USDT:USDT': {
        'info': {'user_id': '',
                 'taker_fee': '0.0018',
                 'maker_fee': '0.0018',
                 'gt_discount': False,
                 'gt_taker_fee': '0',
                 'gt_maker_fee': '0',
                 'loan_fee': '0.18',
                 'point_type': '1',
                 'futures_taker_fee': '0.0005',
                 'futures_maker_fee': '0'},
            'symbol': 'ETH/USDT:USDT',
            'maker': 0.0,
            'taker': 0.0005}
            }
    default_conf['dry_run'] = False
    default_conf['trading_mode'] = TradingMode.FUTURES
    default_conf['margin_mode'] = MarginMode.ISOLATED

    api_mock = MagicMock()
    api_mock.fetch_order = MagicMock(return_value={
        'fee': None,
        'price': 3108.65,
        'cost': 0.310865,
        'amount': 1,  # 1 contract
    })
    exchange = get_patched_exchange(mocker, default_conf, api_mock=api_mock, id='gateio')
    exchange._trading_fees = tick
    order = exchange.fetch_order('22255', 'ETH/USDT:USDT')

    assert order['fee']
    assert order['fee']['rate'] == 0.0005
    assert order['fee']['currency'] == 'USDT'
    assert order['fee']['cost'] == 0.0001554325
