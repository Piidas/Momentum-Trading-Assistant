# Imports
import argparse
import datetime
import collections
import inspect
from decimal import Decimal
from typing import Optional

import threading
import pandas as pd
import numpy as np
import pytz
import math
import re

import logging
import time
import os.path

from ibapi import wrapper
from ibapi.client import EClient
from ibapi.utils import longMaxString
from ibapi.utils import iswrapper

# types
from ibapi.common import *
from ibapi.order_condition import *
from ibapi.contract import *
from ibapi.order import *
from ibapi.order_state import *
from ibapi.execution import Execution
from ibapi.commission_report import CommissionReport
from ibapi.ticktype import *
from ibapi.tag_value import TagValue

from MyUtilities import MyUtilities
from MyOrders import MyOrders

# Constants and rule are defined here
# PORT = 7497   # PAPERTRADING
PORT = 7496
MAX_STOCK_SPREAD = 0.0125
SELL_HALF_REVERSAL_RULE = 0.06
SELL_FULL_REVERSAL_RULE = 0.1
BAD_CLOSE_RULE = 0.15
MAX_ALLOWED_DAILY_PNL_LOSS = -0.05
MIN_POSITION_SIZE = 0.001
PORTFOLIO_UPDATE_PRINTS = 0.1

# TASK: Use only IB timezone
which_markets_to_trade = input("\nDo you want to trade New York [NY], Japan [JP] or Germany [DE]?\n")
if which_markets_to_trade == "JP":
    market_has_pause = True
    TIMEZONE = "Japan"
    EXR_RATE = 150  # YEN per USD
    NAME_OF_DAILYTRADINGPLAN = "DailyTradingPlan_JP.xlsx"
    NAME_OF_DAILYTRADINGPLAN_SAVE = "_trading_plan_JP.xlsx"
    NAME_OF_FETCHDATA_NEW_SAVE = "_fetch_new_positions_JP.xlsx"
    NAME_OF_FETCHDATA_OPEN_SAVE = "_fetch_open_positions_JP.xlsx"
    CLIENT_ID = 11
elif which_markets_to_trade == "NY":
    market_has_pause = False
    TIMEZONE = "America/New_York"
    EXR_RATE = 1  # USD per USD
    NAME_OF_DAILYTRADINGPLAN = "DailyTradingPlan.xlsx"
    NAME_OF_DAILYTRADINGPLAN_SAVE = "_trading_plan.xlsx"
    NAME_OF_FETCHDATA_NEW_SAVE = "_fetch_new_positions.xlsx"
    NAME_OF_FETCHDATA_OPEN_SAVE = "_fetch_open_positions.xlsx"
    CLIENT_ID = 22
elif which_markets_to_trade == "DE":
    market_has_pause = False
    TIMEZONE = "Europe/Berlin"
    EXR_RATE = 0.91  # EUR per USD
    NAME_OF_DAILYTRADINGPLAN = "DailyTradingPlan_DE.xlsx"
    NAME_OF_DAILYTRADINGPLAN_SAVE = "_trading_plan_DE.xlsx"
    NAME_OF_FETCHDATA_NEW_SAVE = "_fetch_new_positions_DE.xlsx"
    NAME_OF_FETCHDATA_OPEN_SAVE = "_fetch_open_positions_DE.xlsx"
    CLIENT_ID = 33
else:
    print("Please restart the program and provide a valid entry.")
    exit()

# Variables are defined here
market_opening = datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)) - datetime.timedelta(days=31)
market_close = datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)) - datetime.timedelta(days=30)
market_pause_start = datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)) - datetime.timedelta(days=31)
market_pause_end = datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)) - datetime.timedelta(days=31)
ib_timezone_str = ""
markets_are_open = False
previous_markets_are_open = False
all_opening_hours = []
market_open_print_timestamp = datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE))
update_DailyTradingPlan_timestamp = datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE))
time_algo_starts = datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE))
market_opening_hours_defined = False
fetch_data_triggered = False
daily_brackets_submitted = False
all_orders_cancelled = False
percent_invested_last = -1
portfolio_size: Optional[float] = None  # Required to avoid type warnings
percent_invested: Optional[float] = None  # Required to avoid type warnings
PnL_percent = 0
max_daily_loss_reached = False
gross_position_value = None
unrealized_PnL = 0
realized_PnL = 0
realized_PnL_percent_last = 0
unrealized_PnL_percent_last = 0
old_orderids = []
sum_of_open_positions = []
fetch_stock_data_thread = None
open_positions_check_done = False
last_orderStatus_message = {}

iOList = pd.read_excel(NAME_OF_DAILYTRADINGPLAN, index_col=0)
tickData = pd.read_excel('tickDataTemplate.xlsx', index_col=0)

iOList, tickData = MyUtilities.data_frame_clean_up(iOList, tickData, return_both_dataframes=True)

iOList = MyUtilities.document_trading_parameters(iOList, MAX_STOCK_SPREAD, SELL_HALF_REVERSAL_RULE,
                                                 SELL_FULL_REVERSAL_RULE, BAD_CLOSE_RULE, MAX_ALLOWED_DAILY_PNL_LOSS,
                                                 MIN_POSITION_SIZE)

tickData_open_position = tickData.copy()
tickData_new_row = tickData.copy()

# Ensures that indices are the same for both files
iOListCopyForTickData = iOList
open_positions_iOList = iOList.copy()
open_positions_iOList = open_positions_iOList.iloc[0:0]

# Prints current time in NY to confirm that there are no bugs conc. timezones considered
print("\n", datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)))

# Prints io_list for reference and double-check
print("\n", iOList.iloc[:, [0, 6, 7, 8, 10, 11]])

# Ends the program when it is not confirmed that the DailyTradingPlan has been updated
dailyPlanUpdated = input("\nHave you updated the DailyTradingPlan on the server? [y/n]\n")
if dailyPlanUpdated != "y":
    exit()

# Defines daily investment limits
invested_max = int(input("\nWhat is your maximum you want to go in the market today [%]?\n"))
percent_invested_max = invested_max / 100


def SetupLogger():
    if not os.path.exists("log"):
        os.makedirs("log")

    time.strftime("pyibapi.%Y%m%d_%H%M%S.log")

    recfmt = '(%(threadName)s) %(asctime)s.%(msecs)03d %(levelname)s %(filename)s:%(lineno)d %(message)s'

    timefmt = '%y%m%d_%H:%M:%S'

    # logging.basicConfig( level=logging.DEBUG,
    #                    format=recfmt, datefmt=timefmt)
    logging.basicConfig(filename=time.strftime("log/pyibapi.%y%m%d_%H%M%S.log"),
                        filemode="w",
                        level=logging.INFO,
                        format=recfmt, datefmt=timefmt)
    logger = logging.getLogger()
    console = logging.StreamHandler()
    console.setLevel(logging.ERROR)
    logger.addHandler(console)


def printWhenExecuting(fn):
    def fn2(self):
        print("   doing", fn.__name__)
        fn(self)
        print("   done w/", fn.__name__)

    return fn2


def printinstance(inst: Object):
    attrs = vars(inst)
    print(', '.join(
        '{}:{}'.format(
            key,
            decimalMaxString(value) if type(value) is Decimal else
            floatMaxString(value) if type(value) is float else
            intMaxString(value) if type(value) is int else
            value
        )
        for key, value in attrs.items()
    ))


class Activity(Object):
    def __init__(self, reqMsgId, ansMsgId, ansEndMsgId, reqId):
        self.reqMsdId = reqMsgId
        self.ansMsgId = ansMsgId
        self.ansEndMsgId = ansEndMsgId
        self.reqId = reqId


class RequestMgr(Object):
    def __init__(self):
        # I will keep this simple even if slower for now: only one list of
        # requests finding will be done by linear search
        self.requests = []

    def addReq(self, req):
        self.requests.append(req)

    def receivedMsg(self, msg):
        pass


# ! [socket_declare]
class TestClient(EClient):
    def __init__(self, wrapper):
        EClient.__init__(self, wrapper)
        # ! [socket_declare]

        # how many times a method is called to see test coverage
        self.clntMeth2callCount = collections.defaultdict(int)
        self.clntMeth2reqIdIdx = collections.defaultdict(lambda: -1)
        self.reqId2nReq = collections.defaultdict(int)
        self.setupDetectReqId()

    def countReqId(self, methName, fn):
        def countReqId_(*args, **kwargs):
            self.clntMeth2callCount[methName] += 1
            idx = self.clntMeth2reqIdIdx[methName]
            if idx >= 0:
                sign = -1 if 'cancel' in methName else 1
                self.reqId2nReq[sign * args[idx]] += 1
            return fn(*args, **kwargs)

        return countReqId_

    def setupDetectReqId(self):

        methods = inspect.getmembers(EClient, inspect.isfunction)
        for (methName, meth) in methods:
            if methName != "send_msg":
                # don't screw up the nice automated logging in the send_msg()
                self.clntMeth2callCount[methName] = 0
                # logging.debug("meth %s", name)
                sig = inspect.signature(meth)
                for (idx, pnameNparam) in enumerate(sig.parameters.items()):
                    (paramName, param) = pnameNparam  # @UnusedVariable
                    if paramName == "req_id":
                        self.clntMeth2reqIdIdx[methName] = idx

                setattr(TestClient, methName, self.countReqId(methName, meth))

                # print("TestClient.clntMeth2reqIdIdx", self.clntMeth2reqIdIdx)


# ! [ewrapperimpl]
class TestWrapper(wrapper.EWrapper):
    # ! [ewrapperimpl]
    def __init__(self):
        wrapper.EWrapper.__init__(self)

        self.wrapMeth2callCount = collections.defaultdict(int)
        self.wrapMeth2reqIdIdx = collections.defaultdict(lambda: -1)
        self.reqId2nAns = collections.defaultdict(int)
        self.setupDetectWrapperReqId()

    # TODO: see how to factor this out !!

    def countWrapReqId(self, methName, fn):
        def countWrapReqId_(*args, **kwargs):
            self.wrapMeth2callCount[methName] += 1
            idx = self.wrapMeth2reqIdIdx[methName]
            if idx >= 0:
                self.reqId2nAns[args[idx]] += 1
            return fn(*args, **kwargs)

        return countWrapReqId_

    def setupDetectWrapperReqId(self):

        methods = inspect.getmembers(wrapper.EWrapper, inspect.isfunction)
        for (methName, meth) in methods:
            self.wrapMeth2callCount[methName] = 0
            # logging.debug("meth %s", name)
            sig = inspect.signature(meth)
            for (idx, pnameNparam) in enumerate(sig.parameters.items()):
                (paramName, param) = pnameNparam  # @UnusedVariable
                # we want to count the errors as 'error' not 'answer'
                if 'error' not in methName and paramName == "req_id":
                    self.wrapMeth2reqIdIdx[methName] = idx

            setattr(TestWrapper, methName, self.countWrapReqId(methName, meth))

            # print("TestClient.wrapMeth2reqIdIdx", self.wrapMeth2reqIdIdx)


# ! [socket_init]
class TestApp(TestWrapper, TestClient):
    def __init__(self):
        TestWrapper.__init__(self)
        TestClient.__init__(self, wrapper=self)
        # ! [socket_init]
        self.nKeybInt = 0
        self.started = False
        self.nextValidOrderId = None
        self.permId2ord = {}
        self.reqId2nErr = collections.defaultdict(int)
        self.globalCancelOnly = False
        self.simplePlaceOid = None

    def dumpTestCoverageSituation(self):
        for clntMeth in sorted(self.clntMeth2callCount.keys()):
            logging.debug("ClntMeth: %-30s %6d" % (clntMeth,
                                                   self.clntMeth2callCount[clntMeth]))

        for wrapMeth in sorted(self.wrapMeth2callCount.keys()):
            logging.debug("WrapMeth: %-30s %6d" % (wrapMeth,
                                                   self.wrapMeth2callCount[wrapMeth]))

    def dumpReqAnsErrSituation(self):
        logging.debug("%s\t%s\t%s\t%s" % ("ReqId", "#Req", "#Ans", "#Err"))
        for reqId in sorted(self.reqId2nReq.keys()):
            nReq = self.reqId2nReq.get(reqId, 0)
            nAns = self.reqId2nAns.get(reqId, 0)
            nErr = self.reqId2nErr.get(reqId, 0)
            logging.debug("%d\t%d\t%s\t%d" % (reqId, nReq, nAns, nErr))

    @iswrapper
    # ! [connectack]
    def connectAck(self):
        if self.asynchronous:
            self.startApi()

    # ! [connectack]

    @iswrapper
    # ! [nextvalidid]
    def nextValidId(self, orderId: int):

        super().nextValidId(orderId)

        logging.debug("setting nextValidOrderId: %d", orderId)
        self.nextValidOrderId = orderId
        print("NextValidId:", orderId)
        # ! [nextvalidid]

        # we can start now
        if hasattr(self, 'account'):
            self.start()

    def start(self):
        if self.started:
            return

        self.started = True

        if self.globalCancelOnly:
            print("Executing GlobalCancel only")
            self.reqGlobalCancel()
        else:
            print("Executing requests")
            # self.reqGlobalCancel()
            self.marketDataTypeOperations()
            self.accountOperations_req()
            self.tickDataOperations_req()
            self.contractOperations()

            print("Executing requests ... finished")

    def keyboardInterrupt(self):
        self.nKeybInt += 1
        if self.nKeybInt == 1:
            self.stop()
        else:
            print("Finishing test")
            self.done = True

    def stop(self):
        print("Executing cancels")
        self.accountOperations_cancel()
        self.tickDataOperations_cancel()
        print("Executing cancels ... finished")

    def nextOrderId(self):
        oid = self.nextValidOrderId
        self.nextValidOrderId += 1
        return oid

    @iswrapper
    # ! [error]
    def error(self, reqId: TickerId, errorCode: int, errorString: str, advancedOrderRejectJson=""):
        super().error(reqId, errorCode, errorString, advancedOrderRejectJson)
        if advancedOrderRejectJson:
            print("Error. Id:", reqId, "Code:", errorCode, "Msg:", errorString, "AdvancedOrderRejectJson:",
                  advancedOrderRejectJson)
        else:
            print("Error. Id:", reqId, "Code:", errorCode, "Msg:", errorString)

    # ! [error] self.reqId2nErr[req_id] += 1

    @iswrapper
    def winError(self, text: str, lastError: int):
        super().winError(text, lastError)

    @iswrapper
    # ! [orderstatus]
    def orderStatus(self, orderId: OrderId, status: str, filled: Decimal,
                    remaining: Decimal, avgFillPrice: float, permId: int,
                    parentId: int, lastFillPrice: float, clientId: int,
                    whyHeld: str, mktCapPrice: float):

        global iOList
        global old_orderids
        global last_orderStatus_message

        super().orderStatus(orderId, status, filled, remaining,
                            avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice)

        # Used to later delete orders from last session
        old_orderids.append(orderId)

        current_message = {
            "Order Status - Order ID": orderId,
            "Status": status,
            "Filled": decimalMaxString(filled),
            "Remaining": decimalMaxString(remaining),
            "AvgFillPrice": floatMaxString(avgFillPrice),
            "ParentId": parentId,
        }

        if markets_are_open and current_message != last_orderStatus_message:
            print("Order Status - Order ID:", orderId, "Status:", status, "Filled:", decimalMaxString(filled),
                  "Remaining:", decimalMaxString(remaining), "AvgFillPrice:", floatMaxString(avgFillPrice),
                  "Parent ID:", parentId,
                  "(", datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)).strftime("%H:%M:%S"), ")")

            last_orderStatus_message = current_message.copy()

        iOList = MyUtilities.update_io_list_order_execution_status(status, orderId, lastFillPrice, filled, remaining,
                                                                   iOList, TIMEZONE)

    # ! [orderstatus]

    @printWhenExecuting
    def accountOperations_req(self):

        # Subscribing to an account's information. Only one at a time!
        # ! [reqaaccountupdates]
        self.reqAccountUpdates(True, self.account)
        # ! [reqaaccountupdates]

        # Requesting all accounts' positions.
        # ! [reqpositions]
        self.reqPositions()
        # ! [reqpositions]

    @printWhenExecuting
    def accountOperations_cancel(self):

        # ! [cancelaaccountupdates]
        self.reqAccountUpdates(False, self.account)
        # ! [cancelaaccountupdates]

        # ! [cancelpositions]
        self.cancelPositions()
        # ! [cancelpositions]

    @iswrapper
    # ! [managedaccounts]
    def managedAccounts(self, accountsList: str):
        super().managedAccounts(accountsList)
        print("Account list:", accountsList)
        # ! [managedaccounts]

        self.account = accountsList.split(",")[0]

        if self.nextValidOrderId is not None:
            self.start()

    @iswrapper
    # ! [accountsummary]
    def accountSummary(self, reqId: int, account: str, tag: str, value: str,
                       currency: str):
        super().accountSummary(reqId, account, tag, value, currency)
        print("AccountSummary. ReqId:", reqId, "Account:", account,
              "Tag: ", tag, "Value:", value, "Currency:", currency)

    # ! [accountsummary]

    @iswrapper
    # ! [accountsummaryend]
    def accountSummaryEnd(self, reqId: int):
        super().accountSummaryEnd(reqId)
        print("AccountSummaryEnd. ReqId:", reqId)

    # ! [accountsummaryend]

    @iswrapper
    # ! [updateaccountvalue]
    def updateAccountValue(self, key: str, val: str, currency: str,
                           accountName: str):

        global gross_position_value
        global portfolio_size
        global percent_invested
        global percent_invested_last
        global realized_PnL
        global unrealized_PnL
        global max_daily_loss_reached
        global max_daily_loss_reached
        global realized_PnL_percent_last
        global unrealized_PnL_percent_last

        super().updateAccountValue(key, val, currency, accountName)

        if key == "GrossPositionValue":
            gross_position_value = float(val)

        if key == "NetLiquidation":
            portfolio_size = float(val)

            if not pd.isnull(gross_position_value):

                percent_invested = gross_position_value / portfolio_size

                # Only updates if something has changed (beware the units)
                if abs(percent_invested - percent_invested_last) * 100 > PORTFOLIO_UPDATE_PRINTS:
                    print("\nYour portfolio size is", round(portfolio_size, 0), "$. (",
                          datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)).strftime("%H:%M:%S"), ")")

                    print("You are now", round(percent_invested * 100, 2), "% invested. (",
                          datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)).strftime("%H:%M:%S"), ")")

                    percent_invested_last = percent_invested

        if key == "RealizedPnL" and currency == "BASE":
            realized_PnL = float(val)

        if key == "UnrealizedPnL" and currency == "BASE":
            unrealized_PnL = float(val)

        if (key == "RealizedPnL" and currency == "BASE") or (key == "UnrealizedPnL" and currency == "BASE"):
            max_daily_loss_reached, realized_PnL_percent_last, unrealized_PnL_percent_last = (
                MyUtilities.update_daily_pnl(portfolio_size, EXR_RATE, realized_PnL, realized_PnL_percent_last,
                                             unrealized_PnL, unrealized_PnL_percent_last, MAX_ALLOWED_DAILY_PNL_LOSS,
                                             max_daily_loss_reached, TIMEZONE, PORTFOLIO_UPDATE_PRINTS))

    # ! [updateaccountvalue]

    @iswrapper
    # ! [accountdownloadend]
    def accountDownloadEnd(self, accountName: str):
        super().accountDownloadEnd(accountName)
        print("AccountDownloadEnd. Account:", accountName)

    # ! [accountdownloadend]

    @iswrapper
    # ! [position]
    def position(self, account: str, contract: Contract, position: Decimal,
                 avgCost: float):

        global open_positions_iOList

        super().position(account, contract, position, avgCost)

        if open_positions_check_done == False:
            print("Position.", "Account:", account, "Symbol:", contract.symbol, "SecType:",
                  contract.secType, "Currency:", contract.currency,
                  "Position:", decimalMaxString(position), "Avg cost:", floatMaxString(avgCost))

            open_positions_iOList = MyUtilities.check_open_orders(open_positions_iOList, contract.symbol,
                                                                  contract.currency, decimalMaxString(position))

    # ! [position]

    @iswrapper
    # ! [positionend]
    def positionEnd(self):
        super().positionEnd()
        print("PositionEnd")

    @iswrapper
    # ! [pnl]
    def pnl(self, reqId: int, dailyPnL: float,
            unrealizedPnL: float, realizedPnL: float):
        super().pnl(reqId, dailyPnL, unrealizedPnL, realizedPnL)
        print("Daily PnL. ReqId:", reqId, "DailyPnL:", floatMaxString(dailyPnL),
              "UnrealizedPnL:", floatMaxString(unrealizedPnL), "RealizedPnL:", floatMaxString(realizedPnL))

    # ! [pnl]

    @iswrapper
    # ! [pnlsingle]
    def pnlSingle(self, reqId: int, pos: Decimal, dailyPnL: float,
                  unrealizedPnL: float, realizedPnL: float, value: float):
        super().pnlSingle(reqId, pos, dailyPnL, unrealizedPnL, realizedPnL, value)
        print("Daily PnL Single. ReqId:", reqId, "Position:", decimalMaxString(pos),
              "DailyPnL:", floatMaxString(dailyPnL), "UnrealizedPnL:", floatMaxString(unrealizedPnL),
              "RealizedPnL:", floatMaxString(realizedPnL), "Value:", floatMaxString(value))

    # ! [pnlsingle]

    def marketDataTypeOperations(self):
        # ! [reqmarketdatatype]
        # Switch to live (1) frozen (2) delayed (3) delayed frozen (4).
        self.reqMarketDataType(MarketDataTypeEnum.REALTIME)
        # ! [reqmarketdatatype]

    @printWhenExecuting
    def tickDataOperations_req(self):
        self.reqMarketDataType(MarketDataTypeEnum.REALTIME)

        # Requesting real time market data
        for i in range(len(iOList)):
            contract = MyUtilities.get_contract_details(iOList, i)
            self.reqMktData(i, contract, "", False, False, [])

    @printWhenExecuting
    def tickDataOperations_cancel(self):
        # Canceling the market data subscription
        # ! [cancelmktdata]
        for i in range(len(iOList)):
            self.cancelMktData(i)

    @iswrapper
    # ! [tickprice]
    def tickPrice(self, reqId: TickerId, tickType: TickType, price: float,
                  attrib: TickAttrib):
        super().tickPrice(reqId, tickType, price, attrib)

        global iOList
        global fetch_data_triggered
        global iOListCopyForTickData
        global all_orders_cancelled
        global daily_brackets_submitted
        global markets_are_open
        global previous_markets_are_open
        global market_opening_hours_defined
        global market_open_print_timestamp
        global update_DailyTradingPlan_timestamp
        global fetch_stock_data_thread
        global open_positions_check_done

        time_now = datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE))
        time_now_str = time_now.strftime("%H:%M:%S")

        if time_now > time_algo_starts + datetime.timedelta(minutes=1) and open_positions_check_done == False:
            MyUtilities.compare_positions_currency_specific(open_positions_iOList, iOList)

            open_positions_check_done = True

        # Sets marker True if market opening hours are defined
        if market_opening_hours_defined == False:
            time_delta_to_initialized_market = time_now - market_opening
            if time_delta_to_initialized_market.days < 10:
                market_opening_hours_defined = True
                print("\nMarket opening hours are defined.\n")

        if market_opening_hours_defined and \
                (
                        (market_close > time_now > market_opening and market_has_pause == False)
                        or
                        (
                                (market_pause_start > time_now > market_opening or
                                 market_close > time_now > market_pause_end)
                                and market_has_pause
                        )
                ):

            markets_are_open = True
        else:
            markets_are_open = False

        # Triggers only once when markets just opened
        if market_opening_hours_defined and markets_are_open and previous_markets_are_open == False:
            update_DailyTradingPlan_timestamp = time_now
            print("\n##################################################################")
            print("\nDingDingDing - Markets are open!\n")
            print("##################################################################\n")
            columns_to_clear = ['LAST price [$]', 'BID price [$]', 'ASK price [$]', 'BID size', 'ASK size',
                                'CLOSE price [$]']
            iOList[columns_to_clear] = np.nan

        # Triggers only once when markets just closed
        if previous_markets_are_open and markets_are_open == False:
            print("\n##################################################################")
            print("\nMarkets are closed.\n")
            print("##################################################################\n")

        # Update the previous state for the next check
        previous_markets_are_open = markets_are_open

        # Allocates all relevant tickTypes to their respective field
        if TickTypeEnum.toStr(tickType) == "CLOSE":
            iOList.loc[reqId, 'CLOSE price [$]'] = price
            iOListCopyForTickData.loc[reqId, 'CLOSE price [$]'] = price

        if TickTypeEnum.toStr(tickType) == "BID":
            iOList.loc[reqId, 'BID price [$]'] = price
            iOListCopyForTickData.loc[reqId, 'BID price [$]'] = price

        if TickTypeEnum.toStr(tickType) == "ASK":
            iOList.loc[reqId, 'ASK price [$]'] = price
            iOListCopyForTickData.loc[reqId, 'ASK price [$]'] = price

        if TickTypeEnum.toStr(tickType) == "LAST":
            iOList.loc[reqId, 'LAST price [$]'] = price
            iOListCopyForTickData.loc[reqId, 'LAST price [$]'] = price

        if TickTypeEnum.toStr(tickType) == "HIGH":
            if pd.isnull(iOList['HIGH price [$]'][reqId]) or price > iOList['HIGH price [$]'][reqId]:
                iOList.loc[reqId, 'HIGH price [$]'] = price

        if TickTypeEnum.toStr(tickType) == "LOW":
            if pd.isnull(iOList['LOW price [$]'][reqId]) or price < iOList['LOW price [$]'][reqId]:
                iOList.loc[reqId, 'LOW price [$]'] = price

        # Start function fetch_stock_data() only once
        if fetch_data_triggered == False and markets_are_open:
            fetch_stock_data_thread = threading.Thread(target=self.fetch_stock_data, daemon=False)
            fetch_stock_data_thread.start()
            fetch_data_triggered = True

        # Continues only when US_market_hours are defined
        if market_opening_hours_defined == False:
            return

        if market_has_pause and time_now > market_opening:
            minutes_to_market_open = (market_pause_end - time_now).total_seconds() / 60
        else:
            minutes_to_market_open = (market_opening - time_now).total_seconds() / 60

        # Place brackets around open positions
        if daily_brackets_submitted == False and market_opening_hours_defined and \
                iOList['Open position'][reqId] and iOList['Open position bracket submitted'][reqId] == False:

            # Cancels all open orders every time the algo is started if the market opening is only some minutes away
            # Note that this only happens if there are open positions in io_list
            if all_orders_cancelled == False and minutes_to_market_open < 15:

                for old_id in old_orderids:
                    self.cancelOrder(int(old_id), "")

                all_orders_cancelled = True

            # Only continues in logic if all relevant data points are already received
            if pd.isnull(iOList['LAST price [$]'][reqId]):
                return

            # Bracket shall immediately be placed when last price is within -1% or above of defined stop
            if markets_are_open and iOList['LAST price [$]'][reqId] > iOList['Stop price [$]'][reqId] * 0.99:
                # Place new OCA profit taker and stop loss
                contract = MyUtilities.get_contract_details(iOList, reqId)
                total_quantity = round(iOList['Quantity [#]'][reqId], 0)
                lmt_price = round(iOList['Profit taker price [$]'][reqId], 2)
                aux_price = round(iOList['Stop price [$]'][reqId], 2)
                oca, iOList = MyOrders.one_cancels_all(self.nextOrderId(), total_quantity, lmt_price, aux_price, reqId,
                                                       TIMEZONE, ib_timezone_str, market_close, iOList)
                for o in oca:
                    self.placeOrder(o.orderId, contract, o)
                    self.nextOrderId()

                iOList.loc[reqId, 'Open position bracket submitted'] = True
                iOList.loc[reqId, 'Order executed [time]'] = time_now.strftime("%y%m%d %H:%M:%S")
                print(f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} within -1% from buy price - bracket defined."
                      f"( {time_now_str} )")

            # If price gaps below -1% from buy price and stock iterates the first time:
            elif markets_are_open and iOList["Stop timestamp"][reqId] == "":
                iOList.loc[reqId, "Stop timestamp"] = datetime.datetime.now(tz=None)
                iOList.loc[reqId, "Last stop price"] = iOList["LAST price [$]"][reqId]
                iOList.loc[reqId, 'Stock looped'] = True
                print(f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} gapped below -1% from buy price - we wait 4 secs."
                      f"( {time_now_str} )")

            # If price gaps below -1% from buy price and stock iterates further:
            elif markets_are_open and iOList["Stop timestamp"][reqId] <= \
                    datetime.datetime.now(tz=None) - datetime.timedelta(seconds=4):

                # If stock continues to sink within last 4 seconds, sell order is placed
                if iOList["Last stop price"][reqId] > iOList["LAST price [$]"][reqId]:

                    # Shoot market sell order
                    contract = MyUtilities.get_contract_details(iOList, reqId)
                    total_quantity = round(iOList['Quantity [#]'][reqId], 0)
                    orderId = self.nextOrderId()
                    order = MyOrders.sell_market_order(orderId, total_quantity)
                    self.placeOrder(order.orderId, contract, order)

                    iOList.loc[reqId, 'Open position bracket submitted'] = True
                    iOList.loc[reqId, 'Order executed [time]'] = time_now.strftime("%y%m%d %H:%M:%S")
                    iOList.loc[reqId, 'stopOrderId'] = orderId

                    print(f"\n Stock with ID: {reqId} {iOList['Symbol'][reqId]} fell further in price - stock sold."
                          f"( {time_now_str} )")

                # If the price increased, I will wait 4 more seconds
                else:
                    iOList.loc[reqId, "Stop timestamp"] = datetime.datetime.now(tz=None)
                    iOList.loc[reqId, "Last stop price"] = iOList["LAST price [$]"][reqId]
                    print(f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} improved in price - wait 4 more secs.\n")

            if iOList['Open position'].equals(iOList['Open position bracket submitted']):
                daily_brackets_submitted = True

                print(f"\nAll brackets for open positions transmitted. ( {time_now_str} )\n")

        # Only continues if market_hours are defined and markets are open (reports every minute)
        if markets_are_open == False and time_now < market_close + datetime.timedelta(minutes=3):

            # Prints message more often the closer it gets to market opening
            if (
                    minutes_to_market_open > 15 and market_open_print_timestamp + datetime.timedelta(minutes=15)
                    < time_now
            ) or \
                    (
                            15 >= minutes_to_market_open > 2 and
                            market_open_print_timestamp + datetime.timedelta(minutes=3) < time_now
                    ) or \
                    (
                            2 >= minutes_to_market_open and market_open_print_timestamp + datetime.timedelta(seconds=30)
                            < time_now
                    ):
                print(f"\nMarkets not open. ( {time_now_str} )")

                market_open_print_timestamp = time_now

            return

        elif time_now > market_close + datetime.timedelta(minutes=3):

            print("Code attempting to shut down. ( ", time_now_str, " )")

            if fetch_stock_data_thread.is_alive():
                fetch_stock_data_thread.join()

                print("Threads joined. ( ", time_now_str, " )")

            print("Finally exit. ( ", time_now_str, " )")
            exit()

        # Only continues in logic if all relevant data points are already received and market_hours are defined
        if pd.isnull(iOList['LAST price [$]'][reqId]) or pd.isnull(iOList['ASK price [$]'][reqId]) or \
                pd.isnull(iOList['BID price [$]'][reqId]):
            return

        # Updating DailyTradingPlan
        # Function reads DailyTradingPlan every few seconds and checks for updates (open and new positions)
        if update_DailyTradingPlan_timestamp + datetime.timedelta(seconds=15) < time_now:

            success_reading_xls = True
            io_list_update = None
            update_DailyTradingPlan_timestamp = time_now

            try:
                io_list_update = pd.read_excel(NAME_OF_DAILYTRADINGPLAN, index_col=0)

            except PermissionError:
                print(
                    f"Did not get permission to read DailyTradingPlan. Will try again in some secs. ( {time_now_str} )")
                success_reading_xls = False

            except FileNotFoundError:
                print("File not found.")
                success_reading_xls = False

            except Exception as e:
                print(f"An error occurred: {e}")
                success_reading_xls = False

            if success_reading_xls:
                # Applies the necessary datatypes again
                io_list_update = MyUtilities.data_frame_clean_up(io_list_update, tickData, return_both_dataframes=False)

                for j in range(len(io_list_update)):

                    # Adding new positions
                    # Must come first to avoid errors due to index j exceeding len(io_list)
                    if j >= len(iOList):

                        # Adds the new row to io_list and iOListCopyForTickData for fetching function
                        iOList = pd.concat([iOList, io_list_update.iloc[[j]]], ignore_index=True)
                        iOListCopyForTickData = pd.concat([iOListCopyForTickData, io_list_update.iloc[[j]]],
                                                          ignore_index=True)

                        # Requests contract details and market data
                        contract = MyUtilities.get_contract_details(iOList, j)
                        self.reqContractDetails(j, contract)
                        self.reqMktData(j, contract, "", False, False, [])

                        print(f"\nStock ID: {j} {iOList['Symbol'][j]} - New position data is added acc. to new plan."
                              f"( {time_now_str} )")

                        iOList.loc[j, 'New position added'] = True
                        iOList.loc[j, 'New position added [time]'] = time_now_str

                    # Updating open positions or filled new positions
                    elif (
                            (iOList['Open position'][j] == False and iOList['Order filled'][j] and
                             iOList['Stock sold'][j] == False)
                            or (
                                    iOList['Open position'][j] and
                                    iOList['Open position bracket submitted'][j] and iOList['Stock sold'][j] == False
                            )) and (
                            io_list_update['Stop price [$]'][j] != iOList['Stop price [$]'][j] or
                            io_list_update['Profit taker price [$]'][j] != iOList['Profit taker price [$]'][j] or
                            io_list_update['Quantity [#]'][j] < iOList['Quantity [#]'][j]
                    ):

                        if iOList['Open position'][j] == False and iOList['Stop low of day'][j] and \
                                io_list_update['Stop price [$]'][j] != iOList['Stop price [$]'][j]:
                            print(
                                f"\n### ATTENTION #### Stock ID: {j} {iOList['Symbol'][j]} - You are overwriting stop "
                                f"at the low of the day of {iOList['Stop price [$]'][j]} with a new stop price of "
                                f"{io_list_update['Stop price [$]'][j]}. ( {time_now_str} )")

                        iOList.loc[j, 'Stop price [$]'] = io_list_update['Stop price [$]'][j]
                        iOList.loc[j, 'Profit taker price [$]'] = io_list_update['Profit taker price [$]'][j]

                        # Cancel current bracket oder
                        self.cancelOrder(int(iOList['profitOrderId'][j]), "")

                        # Only required if the quantity is trimmed
                        if io_list_update['Quantity [#]'][j] < iOList['Quantity [#]'][j]:
                            # Shoot market sell order
                            contract = MyUtilities.get_contract_details(iOList, j)
                            total_quantity = round(iOList['Quantity [#]'][j] - io_list_update['Quantity [#]'][j], 0)
                            order = MyOrders.sell_market_order(self.nextOrderId(), total_quantity)
                            self.placeOrder(order.orderId, contract, order)
                            iOList.loc[j, 'Quantity [#]'] = io_list_update['Quantity [#]'][j]

                        # Place new OCA profit taker with adjusted stop loss
                        contract = MyUtilities.get_contract_details(iOList, j)
                        total_quantity = round(iOList['Quantity [#]'][j], 0)
                        lmt_price = round(iOList['Profit taker price [$]'][j], 2)
                        aux_price = round(iOList['Stop price [$]'][j], 2)
                        oca, iOList = MyOrders.one_cancels_all(self.nextOrderId(), total_quantity, lmt_price, aux_price,
                                                               j, TIMEZONE, ib_timezone_str, market_close, iOList)
                        for o in oca:
                            self.placeOrder(o.orderId, contract, o)
                            self.nextOrderId()

                        print(f"\nStock ID: {j} {iOList['Symbol'][j]} - Open position bracket updated acc. to new plan."
                              f"( {time_now_str} )")

                        iOList.loc[j, 'Open position updated'] = True
                        iOList.loc[j, 'Open position updated [time]'] = time_now_str

                    # Updating new positions that did not execute
                    elif iOList['Open position'][j] == False and iOList['Crossed buy price'][j] == False and \
                            (
                                    io_list_update['Entry price [$]'][j] != iOList['Entry price [$]'][j] or
                                    io_list_update['Stop price [$]'][j] != iOList['Stop price [$]'][j] or
                                    io_list_update['Quantity [#]'][j] != iOList['Quantity [#]'][j] or
                                    io_list_update['Buy limit price [$]'][j] != iOList['Buy limit price [$]'][j] or
                                    io_list_update['Profit taker price [$]'][j] != iOList['Profit taker price [$]'][j]
                            ):

                        iOList.loc[j, 'Entry price [$]'] = io_list_update['Entry price [$]'][j]
                        iOList.loc[j, 'Stop price [$]'] = io_list_update['Stop price [$]'][j]
                        iOList.loc[j, 'Quantity [#]'] = io_list_update['Quantity [#]'][j]
                        iOList.loc[j, 'Buy limit price [$]'] = io_list_update['Buy limit price [$]'][j]
                        iOList.loc[j, 'Profit taker price [$]'] = io_list_update['Profit taker price [$]'][j]

                        print(f"\nStock ID: {j} {iOList['Symbol'][j]} - New position data is updated acc. to new plan."
                              f"( {time_now_str} )")

                        iOList.loc[j, 'New position updated'] = True
                        iOList.loc[j, 'New position updated [time]'] = time_now_str

        # Stocks meeting these criteria are skipped and shall only prevent the code from "falling asleep"
        # Recommended to use Crypto here due to 24/7 trading
        if iOList['Entry price [$]'][reqId] == 9 and iOList['Stop price [$]'][reqId] == 11:
            if iOList['Stop undercut'][reqId] == False:
                iOList.loc[reqId, 'Stop undercut'] = True
            return

        # Checks if price undercuts stop and sets value as True in case
        if iOList['LAST price [$]'][reqId] < iOList['Stop price [$]'][reqId] and \
                iOList['Stop undercut'][reqId] == False:
            iOList.loc[reqId, 'Stop undercut'] = True
            iOList.loc[reqId, 'Stop undercut [time]'] = time_now_str
            print(f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} has undercut the stop. ( {time_now_str} )")

        # Sets marker if stock is sold for open positions and new positions
        if (
                (
                        iOList['Open position'][reqId] or
                        (iOList['Open position'][reqId] == False and iOList['Order filled'][reqId])
                ) and
                iOList['Stock sold'][reqId] == False
        ) and \
                (
                        iOList['Profit order filled'][reqId] or iOList['Stop order filled'][reqId] or
                        iOList['SOC order filled'][reqId]
                ):
            iOList.loc[reqId, 'Stock sold'] = True
            iOList.loc[reqId, 'Stock sold [time]'] = time_now_str

        # Only continues if all relevant data points are defined and parameters given
        if pd.isnull(percent_invested) or portfolio_size in None or percent_invested is None or \
                iOList['Position below limit'][reqId] or iOList['Max. daily loss reached'][reqId]:
            return

        # When buy price is crossed and field is still empty means crosses the price the first time
        # Two-step entries are excluded, but OR grants access within first minute to check on lower spread/ price
        # to enter

        if (
                iOList['LAST price [$]'][reqId] > iOList['Entry price [$]'][reqId] and
                iOList['Open position'][reqId] == False and iOList['Crossed buy price'][reqId] == False and
                iOList['Order executed'][reqId] == False
        ) or \
                (
                        iOList['Crossed buy price'][reqId] and iOList['Order executed'][reqId] == False and
                        time_now < market_opening + datetime.timedelta(minutes=1)
                ):

            # Marks "crossed buy price" only once
            if iOList['Crossed buy price'][reqId] == False:
                iOList.loc[reqId, 'Crossed buy price'] = True
                iOList.loc[reqId, 'Crossed buy price [time]'] = time_now_str
                print(f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} crossed buy price. ( {time_now_str} )")
                iOList.loc[reqId, "Stop timestamp"] = datetime.datetime.now(tz=None)

            # Checks if I would reach my daily investment limit with this buy order
            if iOList['Entry price [$]'][reqId] / EXR_RATE * iOList['Quantity [#]'][reqId] \
                    / portfolio_size + percent_invested > percent_invested_max:

                # Reduces the size of the position to stay within the investment limit
                iOList.loc[reqId, 'Quantity [#]'] = math.floor(
                    (percent_invested_max - percent_invested) * portfolio_size
                    / (iOList['Entry price [$]'][reqId] / EXR_RATE))

                iOList.loc[reqId, 'Invest limit reached'] = True
                iOList.loc[reqId, 'Invest limit reached [time]'] = time_now_str

                # Very small resulting positions shall not be traded
                if iOList['Quantity [#]'][reqId] * iOList['Entry price [$]'][reqId] \
                        < MIN_POSITION_SIZE * portfolio_size:
                    iOList.loc[reqId, 'Position below limit'] = True
                    print(
                        f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} would exceed my daily investment limit - "
                        f"remainder is below the minimum position size of {round(MIN_POSITION_SIZE * 100, 1)}"
                        f"% - trade not executed. ( {time_now_str} )")
                    return

                print(f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} would exceed my daily investment limit. "
                      f"Position size has been reduced. ( {time_now_str} )")

            # Terminates all buying if daily loss limit is reached
            if max_daily_loss_reached:
                iOList.loc[reqId, 'Max. daily loss reached'] = True
                iOList.loc[reqId, 'Max. daily loss reached [time]'] = time_now_str
                print(f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} not executed - daily max. loss of "
                      f"{round(MAX_ALLOWED_DAILY_PNL_LOSS * 100, 1)}% is reached. ( {time_now_str} ")
                return

            stock_spread = abs((iOList['ASK price [$]'][reqId] - iOList['BID price [$]'][reqId])
                               / iOList['ASK price [$]'][reqId])
            iOList.loc[reqId, 'Spread at execution [%]'] = round(stock_spread * 100, 2)

            # Provides feedback to cmd prompt when stock is above price or spread limit
            # In the first minutes, a message is only printed every 10 seconds
            # Only prints this message if stock is already looping for 10 sec. (small inaccuracy to CMD prompt)
            if time_now < market_opening + datetime.timedelta(minutes=1) and iOList["Stop timestamp"][reqId] <= \
                    datetime.datetime.now(tz=None) - datetime.timedelta(seconds=10):

                iOList.loc[reqId, "Stop timestamp"] = datetime.datetime.now(tz=None)

                if iOList['LAST price [$]'][reqId] >= iOList['Buy limit price [$]'][reqId]:
                    print(f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} - LAST price is above buy limit -"
                          f"stock loops within first minutes. ( {time_now_str} )")
                    iOList.loc[reqId, 'Stock looped'] = True

                if stock_spread > MAX_STOCK_SPREAD:
                    print(f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} - Spread is above limit at:"
                          f"{round(stock_spread * 100, 2)}% - stock loops within first minutes. ( {time_now_str} )")
                    iOList.loc[reqId, 'Stock looped'] = True

            elif market_opening + datetime.timedelta(minutes=1) <= time_now < market_close:

                if iOList['LAST price [$]'][reqId] >= iOList['Buy limit price [$]'][reqId]:
                    print(f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} - LAST price is above buy limit."
                          f"( {time_now_str} )")

                if stock_spread > MAX_STOCK_SPREAD:
                    print(f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} - Spread is above limit at: "
                          f"{round(stock_spread * 100, 2)}%. ( {time_now_str} )")

            # Provides feedback to DailyTradingPlan if stock is above price or spread limit
            if iOList['LAST price [$]'][reqId] >= iOList['Buy limit price [$]'][reqId]:
                iOList.loc[reqId, 'Price above limit'] = True

            if stock_spread > MAX_STOCK_SPREAD:
                iOList.loc[reqId, 'Spread above limit'] = True

            # Checks 1) if stop has not already been undercut, 2) if stock price is still below the buy limit price,
            # 3) spread < MAX_STOCK_SPREAD
            if iOList['Stop undercut'][reqId] == False and \
                    iOList['LAST price [$]'][reqId] < iOList['Buy limit price [$]'][reqId] and \
                    stock_spread < MAX_STOCK_SPREAD:

                iOList.loc[reqId, 'Order executed'] = True
                iOList.loc[reqId, 'Order executed [time]'] = time_now.strftime("%y%m%d %H:%M:%S")

                # Blocks execution of buy order shortly before market close for "sell on close" stock
                # 15 minutes since at t-8min the brackets got replaced and t-5min the sells are done
                if time_now > market_close - (datetime.timedelta(minutes=15)) and iOList['Sell on close'][reqId]:
                    print(
                        f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} will be sold on close - buy not executed."
                        f"( {time_now_str} )")

                    return

                if iOList['Stop low of day'][reqId] and \
                        iOList['LOW price [$]'][reqId] > iOList['Stop price [$]'][reqId]:

                    # Ensures a min. -1% stop
                    if iOList['LAST price [$]'][reqId] * 0.99 > iOList['LOW price [$]'][reqId]:
                        iOList.loc[reqId, 'Stop price [$]'] = iOList['LOW price [$]'][reqId]
                        print(
                            f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} uses low of the day of "
                            f"{iOList['Stop price [$]'][reqId]} as stop loss price. ( {time_now_str} )")
                    else:
                        iOList.loc[reqId, 'Stop price [$]'] = iOList['LAST price [$]'][reqId] * 0.99
                        print(
                            f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} low of the day is too tight -"
                            f"-1% stop of {iOList['Stop price [$]'][reqId]} is used instead. ( {time_now_str} )")

                    MyUtilities.dailytradingplan_stop_update(reqId, iOList['Stop price [$]'][reqId],
                                                             NAME_OF_DAILYTRADINGPLAN)

                contract = MyUtilities.get_contract_details(iOList, reqId)
                bracket, iOList = MyOrders.bracket_order(self.nextOrderId(), reqId, TIMEZONE, ib_timezone_str,
                                                         market_close, iOList)
                for o in bracket:
                    self.placeOrder(o.orderId, contract, o)
                    self.nextOrderId()

                iOList.loc[reqId, 'Spread at execution [%]'] = round(stock_spread * 100, 2)
                print(f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} - Order placed. ( {time_now_str} )")

        # Add & reduce function
        # Increases the stop of all open positions when additional shares are added
        if daily_brackets_submitted and iOList['Add and reduce'][reqId] and \
                iOList['Add and reduce executed'][reqId] == False and iOList['Order filled'][reqId]:

            for i in range(len(iOList)):
                if (
                        (
                                iOList['Open position'][i] == False and iOList['Order filled'][i] and
                                iOList['Stock sold'][i] == False
                        ) or
                        (
                                iOList['Open position'][i] and iOList['Stock sold'][i] == False
                        )
                ) and iOList['Symbol'][i] == iOList['Symbol'][reqId]:

                    # Cancel current bracket oder
                    self.cancelOrder(int(iOList['profitOrderId'][i]), "")

                    # Place new OCA profit taker with adjusted stop loss
                    contract = MyUtilities.get_contract_details(iOList, i)
                    total_quantity = round(iOList['Quantity [#]'][i], 0)
                    lmt_price = round(iOList['Profit taker price [$]'][i], 2)
                    aux_price = round(iOList['Stop price [$]'][reqId], 2)
                    oca, iOList = MyOrders.one_cancels_all(self.nextOrderId(), total_quantity, lmt_price, aux_price, i,
                                                           TIMEZONE, ib_timezone_str, market_close, iOList)
                    for o in oca:
                        self.placeOrder(o.orderId, contract, o)
                        self.nextOrderId()

                    # Changes stop price in io_list
                    iOList.loc[i, 'Stop price [$]'] = aux_price

                    # Changes stop price in DailyTradingPlan
                    MyUtilities.dailytradingplan_stop_update(i, aux_price, NAME_OF_DAILYTRADINGPLAN)

                    print(f"\nStock ID: {i} {iOList['Symbol'][i]} - Add and reduce executed. ( {time_now_str} )")

            iOList.loc[reqId, 'Add and reduce executed'] = True

        # Sells half of positions if stock is increasing X% over buy point and coming back in to b/e
        # First, marker to be set if buy price increases X% after buy (see SELL_HALF_REVERSAL_RULE)
        if iOList['Open position'][reqId] == False and iOList['Order filled'][reqId] and \
                iOList['2% above buy point'][reqId] == False and \
                iOList['LAST price [$]'][reqId] > iOList['Entry price [$]'][reqId] * (
                1 + SELL_HALF_REVERSAL_RULE):

            execution_timestamp = datetime.datetime.strptime(iOList['Order executed [time]'][reqId], "%y%m%d %H:%M:%S")
            tz = pytz.timezone(TIMEZONE)
            execution_timestamp = tz.normalize(tz.localize(execution_timestamp))

            # Sets marker only if stock buy order was placed more than 2.5 minutes ago
            if (time_now - execution_timestamp).seconds > 150:
                iOList.loc[reqId, '2% above buy point'] = True

        # Second, if stock comes in again to b/o level, 50% must be sold, bracket cancelled
        # New OCA profit taker and stop loss to be set for 50% of quantity
        if iOList['Open position'][reqId] == False and iOList['Order filled'][reqId] and \
                iOList['2% above buy point'][reqId] and iOList['New OCA bracket'][reqId] == False and \
                iOList['Stock sold'][reqId] == False and iOList['5% above buy point'][reqId] == False and \
                iOList['LAST price [$]'][reqId] <= \
                iOList['Entry price [$]'][reqId] * (1 + iOList['Spread at execution [%]'][reqId] / 100) and \
                round(iOList['Quantity [#]'][reqId], 0) > 1:

            # Cancels current bracket oder
            self.cancelOrder(int(iOList['profitOrderId'][reqId]), "")

            # Shoot market sell order for 50%
            contract = MyUtilities.get_contract_details(iOList, reqId)
            total_quantity = math.ceil(round(iOList['Quantity [#]'][reqId], 0) / 2)
            order = MyOrders.sell_market_order(self.nextOrderId(), total_quantity)
            self.placeOrder(order.orderId, contract, order)

            print(
                f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} increased {round(SELL_HALF_REVERSAL_RULE * 100, 1)}% "
                f"above buy price and came in to B/O level - sold half. ( {time_now_str} )")

            # Place new OCA profit taker and stop loss for 50% quantity
            total_quantity = math.floor(round(iOList['Quantity [#]'][reqId], 0) / 2)
            lmt_price = round(iOList['Profit taker price [$]'][reqId], 2)
            aux_price = round(iOList['Stop price [$]'][reqId], 2)
            oca, iOList = MyOrders.one_cancels_all(self.nextOrderId(), total_quantity, lmt_price, aux_price, reqId,
                                                   TIMEZONE, ib_timezone_str, market_close, iOList)
            for o in oca:
                self.placeOrder(o.orderId, contract, o)
                self.nextOrderId()
            iOList.loc[reqId, 'New OCA bracket'] = True
            iOList.loc[reqId, 'New OCA bracket [time]'] = time_now_str
            iOList.loc[reqId, 'Quantity [#]'] = total_quantity

        # Function increases stop to b/e if stock gained Y% over buy point
        # Marker to be set if buy price increases Y% after buy (see SELL_FULL_REVERSAL_RULE)
        if iOList['Open position'][reqId] == False and iOList['Order filled'][reqId] and \
                iOList['Stock sold'][reqId] == False and iOList['5% above buy point'][reqId] == False and \
                iOList['LAST price [$]'][reqId] > iOList['Entry price [$]'][reqId] * (
                1 + SELL_FULL_REVERSAL_RULE):

            execution_timestamp = datetime.datetime.strptime(iOList['Order executed [time]'][reqId], "%y%m%d %H:%M:%S")
            tz = pytz.timezone(TIMEZONE)
            execution_timestamp = tz.normalize(tz.localize(execution_timestamp))

            # Exits if order was place less than 2.5 minutes ago
            if (time_now - execution_timestamp).seconds < 150:
                return

            iOList.loc[reqId, '5% above buy point'] = True
            iOList.loc[reqId, '5% above buy point [time]'] = time_now_str

            # Cancel current bracket oder
            self.cancelOrder(int(iOList['profitOrderId'][reqId]), "")

            # Place new OCA profit taker and stop loss with stop at B/E
            contract = MyUtilities.get_contract_details(iOList, reqId)
            total_quantity = round(iOList['Quantity [#]'][reqId], 0)
            lmt_price = round(iOList['Profit taker price [$]'][reqId], 2)
            aux_price = round(iOList['Entry price [$]'][reqId], 2)
            oca, iOList = MyOrders.one_cancels_all(self.nextOrderId(), total_quantity, lmt_price, aux_price, reqId,
                                                   TIMEZONE, ib_timezone_str, market_close, iOList)
            for o in oca:
                self.placeOrder(o.orderId, contract, o)
                self.nextOrderId()
            iOList.loc[reqId, 'Stop price [$]'] = iOList['Entry price [$]'][reqId]

            # Changes stop price in DailyTradingPlan
            MyUtilities.dailytradingplan_stop_update(reqId, aux_price, NAME_OF_DAILYTRADINGPLAN)

            print("\nStock ID:", reqId, iOList['Symbol'][reqId],
                  "increased", round(SELL_FULL_REVERSAL_RULE * 100, 1),
                  "% above buy price - stop is increased to B/E. (",
                  time_now_str, ")")

        # SOC SMA Function: Cancels open orders and places new bracket without sell on close order
        if time_now > market_close - (datetime.timedelta(minutes=8)) and \
                iOList['Stock sold'][reqId] == False and iOList['Sell on close'][reqId] and \
                pd.notna(iOList['Sell bellow SMA [$]'][reqId]) and \
                iOList['Profit taker price [$]'][reqId] > iOList['LAST price [$]'][reqId] > \
                iOList['Stop price [$]'][reqId] and \
                iOList['LAST price [$]'][reqId] > iOList['Sell bellow SMA [$]'][reqId] and \
                (
                        (
                                iOList['Open position'][reqId] == False and iOList['Order filled'][reqId]
                        ) or
                        iOList['Open position'][reqId]
                ):

            # Important so that he places a bracket without SOC order
            iOList.loc[reqId, 'Sell on close'] = False

            # Cancels current bracket oder
            self.cancelOrder(int(iOList['profitOrderId'][reqId]), "")

            # Place new bracket without GAT portion
            contract = MyUtilities.get_contract_details(iOList, reqId)
            total_quantity = round(iOList['Quantity [#]'][reqId], 0)
            lmt_price = round(iOList['Profit taker price [$]'][reqId], 2)
            aux_price = round(iOList['Stop price [$]'][reqId], 2)
            oca, iOList = MyOrders.one_cancels_all(self.nextOrderId(), total_quantity, lmt_price, aux_price, reqId,
                                                   TIMEZONE, ib_timezone_str, market_close, iOList)
            for o in oca:
                self.placeOrder(o.orderId, contract, o)
                self.nextOrderId()

            print(f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} - Sell on close order deleted since last price "
                  f"{round(iOList['LAST price [$]'][reqId], 2)} is above sell limit of "
                  f"{round(iOList['Sell bellow SMA [$]'][reqId], 2)}. ( {time_now_str} )")

        # Sells half of the position if stock does not close in the upper Z% of the daily range
        # This function is working only when sell-half and sell-full rules have not been triggered
        if time_now > market_close - (datetime.timedelta(minutes=2)) and \
                iOList['Bad close checked'][reqId] == False:

            iOList.loc[reqId, 'Bad close checked'] = True

            if iOList['Open position'][reqId] == False and \
                    iOList['Order filled'][reqId] and iOList['Stock sold'][reqId] == False and \
                    iOList['Sell on close'][reqId] == False and pd.isnull(
                iOList['Sell bellow SMA [$]'][reqId]) and \
                    iOList['5% above buy point'][reqId] == False and iOList['New OCA bracket'][
                reqId] == False and \
                    iOList['Bad close rule'][reqId] == False and round(iOList['Quantity [#]'][reqId], 0) > 1 and \
                    (
                            (iOList['LAST price [$]'][reqId] - iOList['LOW price [$]'][reqId]) /
                            (iOList['HIGH price [$]'][reqId] - iOList['LOW price [$]'][reqId]) < BAD_CLOSE_RULE
                    ):

                # Cancels current bracket oder
                self.cancelOrder(int(iOList['profitOrderId'][reqId]), "")

                # Shoot market sell order for 50%
                contract = MyUtilities.get_contract_details(iOList, reqId)
                total_quantity = math.ceil(round(iOList['Quantity [#]'][reqId], 0) / 2)
                order = MyOrders.sell_market_order(self.nextOrderId(), total_quantity)
                self.placeOrder(order.orderId, contract, order)

                print(f"\nStock ID: {reqId} {iOList['Symbol'][reqId]} attempts a bad close - sold half. "
                      f"( {time_now_str} )")

                total_quantity = math.floor(round(iOList['Quantity [#]'][reqId], 0) / 2)
                lmt_price = round(iOList['Profit taker price [$]'][reqId], 2)
                aux_price = round(iOList['Stop price [$]'][reqId], 2)
                oca, iOList = MyOrders.one_cancels_all(self.nextOrderId(), total_quantity, lmt_price, aux_price, reqId,
                                                       TIMEZONE, ib_timezone_str, market_close, iOList)
                for o in oca:
                    self.placeOrder(o.orderId, contract, o)
                    self.nextOrderId()
                iOList.loc[reqId, 'Bad close rule'] = True
                iOList.loc[reqId, 'Bad close rule [time]'] = time_now_str
                iOList.loc[reqId, 'Quantity [#]'] = total_quantity

    # ! [tickprice]

    @iswrapper
    # ! [ticksize]
    def tickSize(self, reqId: TickerId, tickType: TickType, size: Decimal):
        super().tickSize(reqId, tickType, size)
        # print("TickSize. TickerId:", req_id, "TickType:", tickType, "Size: ", decimalMaxString(size))
        global iOList
        global iOListCopyForTickData

        if TickTypeEnum.toStr(tickType) == "ASK_SIZE":
            iOList.loc[reqId, 'ASK size'] = float(size)
            iOListCopyForTickData.loc[reqId, 'ASK size'] = float(size)

        if TickTypeEnum.toStr(tickType) == "BID_SIZE":
            iOList.loc[reqId, 'BID size'] = float(size)
            iOListCopyForTickData.loc[reqId, 'BID size'] = float(size)

        if TickTypeEnum.toStr(tickType) == "VOLUME":
            iOList.loc[reqId, 'Volume'] = float(size)
            iOListCopyForTickData.loc[reqId, 'Volume'] = float(size)

    # ! [ticksize]

    @iswrapper
    # ! [tickgeneric]
    def tickGeneric(self, reqId: TickerId, tickType: TickType, value: float):
        super().tickGeneric(reqId, tickType, value)
        # print("TickGeneric. TickerId:", req_id, "TickType:", tickType, "Value:", floatMaxString(value))

    # ! [tickgeneric]

    @printWhenExecuting
    def contractOperations(self):
        # ! [reqcontractdetails]
        for i in range(len(iOList)):
            contract = MyUtilities.get_contract_details(iOList, i)
            self.reqContractDetails(i, contract)

    @iswrapper
    # ! [contractdetails]
    def contractDetails(self, reqId: int, contractDetails: ContractDetails):
        global market_opening
        global market_close
        global market_pause_start
        global market_pause_end
        global iOList
        global all_opening_hours
        global ib_timezone_str

        super().contractDetails(reqId, contractDetails)
        # printinstance(contractDetails)
        time_delta_to_initialized_market = datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)) - market_opening

        # saves longName in io_list and prints it for checking
        iOList.loc[reqId, 'Company name'] = contractDetails.longName
        print(f"\n {reqId} {iOList['Company name'][reqId]}")

        # First line item must be ignored since it is only used to keep the algo awake
        all_opening_hours.append(contractDetails.liquidHours[:28])

        if len(all_opening_hours) == len(iOList):
            if len(set(all_opening_hours)) > 2:
                for i in range(len(all_opening_hours)):
                    if i > 1 and all_opening_hours[i] != all_opening_hours[i - 1]:
                        input(f"{iOList['Company name'][i]} and {iOList['Company name'][i - 1]} have different "
                              f"market opening hours. You should end the program and adjust DailyTradingPlan.")
            else:
                print("### Market opening hours are all identical. ###")

        if MyUtilities.should_start_market_opening_function(iOList, time_delta_to_initialized_market):

            ib_timezone_str = contractDetails.timeZoneId
            print(f"\nIB's timezone is {ib_timezone_str}.")
            market_trading_hours = contractDetails.liquidHours
            tz = pytz.timezone(TIMEZONE)
            tradinghours_split_to_list = re.split(";|-", market_trading_hours)
            print("\n", tradinghours_split_to_list)
            index_open = int(input("\nEnter the index of the next market OPEN: "))
            index_close = int(input("\nEnter the index of the next market CLOSE: "))
            market_opening = datetime.datetime.strptime(tradinghours_split_to_list[index_open], "%Y%m%d:%H%M")
            market_opening = tz.normalize(tz.localize(market_opening))
            market_close = datetime.datetime.strptime(tradinghours_split_to_list[index_close], "%Y%m%d:%H%M")
            market_close = tz.normalize(tz.localize(market_close))

            if market_has_pause:
                market_pause_start = datetime.datetime.strptime(tradinghours_split_to_list[index_open + 1],
                                                                "%Y%m%d:%H%M")
                market_pause_start = tz.normalize(tz.localize(market_pause_start))
                market_pause_end = datetime.datetime.strptime(tradinghours_split_to_list[index_close - 1],
                                                              "%Y%m%d:%H%M")
                market_pause_end = tz.normalize(tz.localize(market_pause_end))

                print(f"\nOpening: {market_opening} - "
                      f"Pause: {market_pause_start} - {market_pause_end} - Closing: {market_close}")
            else:
                print(f"\nOpening: {market_opening} - Closing: {market_close}")

            # Only required for one main.py
            if which_markets_to_trade == "NY":
                earnings_thread = threading.Thread(target=MyUtilities.find_earnings_dates,
                                                   args=(iOList, market_opening), daemon=True)
                earnings_thread.start()
            else:
                print("Earnings dates can only be given for US-stocks.")

            if datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)) > market_close:
                input("\n ### Attention ### Market close is already in the past. Code will exit.")
                exit()

    # ! [contractdetails]

    @iswrapper
    # ! [contractdetailsend]
    def contractDetailsEnd(self, reqId: int):
        super().contractDetailsEnd(reqId)
        print("ContractDetailsEnd. ReqId:", reqId)

    # ! [contractdetailsend]

    @iswrapper
    # ! [execdetails]
    def execDetails(self, reqId: int, contract: Contract, execution: Execution):
        super().execDetails(reqId, contract, execution)
        print("\nExecDetails. Symbol:", contract.symbol, "SecType:", contract.secType, "Currency:",
              contract.currency, "Shares:", execution.shares, "Avrg. price:", round(execution.avgPrice, 2), "OrderId:",
              execution.orderId)

    # ! [execdetails]

    @iswrapper
    # ! [execdetailsend]
    def execDetailsEnd(self, reqId: int):
        super().execDetailsEnd(reqId)
        print("ExecDetailsEnd. ReqId:", reqId)

    # ! [execdetailsend]

    @iswrapper
    # ! [commissionreport]
    def commissionReport(self, commissionReport: CommissionReport):
        super().commissionReport(commissionReport)
        print("\nCommissionReport. Commission:", round(commissionReport.commission, 2), "Currency:",
              commissionReport.currency, "RealizedPnL:", round(commissionReport.realizedPNL, 2))

    # ! [commissionreport]

    @iswrapper
    # ! [currenttime]
    def currentTime(self, time: int):
        super().currentTime(time)
        print("CurrentTime:", datetime.datetime.fromtimestamp(time).strftime("%Y%m%d-%H:%M:%S"))

    # ! [currenttime]

    @iswrapper
    # ! [completedorder]
    def completedOrder(self, contract: Contract, order: Order,
                       orderState: OrderState):
        super().completedOrder(contract, order, orderState)
        print("CompletedOrder. PermId:", intMaxString(order.permId), "ParentPermId:", longMaxString(order.parentPermId),
              "Account:", order.account,
              "Symbol:", contract.symbol, "SecType:", contract.secType, "Exchange:", contract.exchange,
              "Action:", order.action, "OrderType:", order.orderType, "TotalQty:",
              decimalMaxString(order.totalQuantity),
              "CashQty:", floatMaxString(order.cashQty), "FilledQty:", decimalMaxString(order.filledQuantity),
              "LmtPrice:", floatMaxString(order.lmtPrice), "AuxPrice:", floatMaxString(order.auxPrice), "Status:",
              orderState.status,
              "Completed time:", orderState.completedTime, "Completed Status:" + orderState.completedStatus,
              "MinTradeQty:", intMaxString(order.minTradeQty), "MinCompeteSize:", intMaxString(order.minCompeteSize),
              "competeAgainstBestOffset:",
              "UpToMid" if order.competeAgainstBestOffset == COMPETE_AGAINST_BEST_OFFSET_UP_TO_MID else floatMaxString(
                  order.competeAgainstBestOffset),
              "MidOffsetAtWhole:", floatMaxString(order.midOffsetAtWhole), "MidOffsetAtHalf:",
              floatMaxString(order.midOffsetAtHalf))

    # ! [completedorder]

    @iswrapper
    # ! [completedordersend]
    def completedOrdersEnd(self):
        super().completedOrdersEnd()
        print("CompletedOrdersEnd")

    # ! [completedordersend]

    @iswrapper
    # ! [userinfo]
    def userInfo(self, reqId: int, whiteBrandingId: str):
        super().userInfo(reqId, whiteBrandingId)
        print("UserInfo.", "ReqId:", reqId, "WhiteBrandingId:", whiteBrandingId)

    # ! [userinfo]

    # Saves all tickData for every stock for every second
    def fetch_stock_data(self):
        global tickData
        global tickData_open_position
        global tickData_new_row

        time_now_fetch = datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE))
        time_now_fetch_str = time_now_fetch.strftime("%y%m%d %H:%M:%S")

        print("\nFetch stock data function is started.\n")
        # Writes the tickData for each ticker to pd dataframe every second for later analysis
        # When saving this dataframe as excel at the end, ~44 different stocks can be saved
        while market_close + datetime.timedelta(seconds=1) >= time_now_fetch >= market_opening:

            for i in range(len(iOListCopyForTickData)):

                # Stocks meeting these criteria are skipped and shall only prevent the code from "falling asleep"
                if iOListCopyForTickData['Entry price [$]'][i] == 9 and \
                        iOListCopyForTickData['Stop price [$]'][i] == 11:
                    continue

                # Only seeks to append data once per symbol for open position and once for new position in case
                if i > 0 and iOListCopyForTickData['Symbol'][i] == iOListCopyForTickData['Symbol'][i - 1] and \
                        (iOListCopyForTickData['Open position'][i] == iOListCopyForTickData['Open position'][i - 1] or
                         (
                                 iOListCopyForTickData['Open position'][i] == False and
                                 iOListCopyForTickData['Open position'][i - 1] == False
                         )
                        ):
                    pass
                else:
                    # Fills row to append in pd dataframe
                    tickData_new_row.loc[0, 'timeStamp'] = time_now_fetch_str
                    tickData_new_row.loc[0, 'Symbol'] = iOListCopyForTickData['Symbol'][i]
                    tickData_new_row.loc[0, 'CLOSE price [$]'] = iOListCopyForTickData['CLOSE price [$]'][i]
                    tickData_new_row.loc[0, 'BID price [$]'] = iOListCopyForTickData['BID price [$]'][i]
                    tickData_new_row.loc[0, 'ASK price [$]'] = iOListCopyForTickData['ASK price [$]'][i]
                    tickData_new_row.loc[0, 'LAST price [$]'] = iOListCopyForTickData['LAST price [$]'][i]
                    tickData_new_row.loc[0, 'ASK size'] = iOListCopyForTickData['ASK size'][i]
                    tickData_new_row.loc[0, 'BID size'] = iOListCopyForTickData['BID size'][i]
                    tickData_new_row.loc[0, 'Volume'] = iOListCopyForTickData['Volume'][i]

                    if iOListCopyForTickData['Open position'][i] == False:
                        # Appends row to tickData
                        tickData = pd.concat([tickData, tickData_new_row], ignore_index=True)

                    else:
                        # Appends row to tickData_open_position
                        tickData_open_position = pd.concat([tickData_open_position, tickData_new_row],
                                                           ignore_index=True)

            # Pauses while-loop for one second until the next round
            time.sleep(1)

            time_now_fetch = datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE))
            time_now_fetch_str = time_now_fetch.strftime("%y%m%d %H:%M:%S")

        filename = market_close.strftime("%y%m%d") + NAME_OF_DAILYTRADINGPLAN_SAVE
        MyUtilities.save_excel_outputs(filename, iOList)

        # Avoids saving an Excel file if no new positions are in DailyTradingPlan
        if len(tickData) > 100:
            filename = market_close.strftime("%y%m%d") + NAME_OF_FETCHDATA_NEW_SAVE
            MyUtilities.save_excel_outputs(filename, tickData)

        # Avoids saving an Excel file if no open positions are in DailyTradingPlan
        if len(tickData_open_position) > 100:
            filename = market_close.strftime("%y%m%d") + NAME_OF_FETCHDATA_OPEN_SAVE
            MyUtilities.save_excel_outputs(filename, tickData_open_position)

        # Return to close the thread, since daemon=False. "sys.exit()" is an alternative.
        return


def main():
    global CLIENT_ID
    global PORT

    SetupLogger()
    logging.debug("now is %s", datetime.datetime.now())
    logging.getLogger().setLevel(logging.ERROR)

    cmdLineParser = argparse.ArgumentParser("api tests")
    # cmdLineParser.add_option("-c", action="store_True", dest="use_cache", default = False, help = "use the cache")
    # cmdLineParser.add_option("-f", action="store", type="string", dest="file", default="", help="the input file")
    cmdLineParser.add_argument("-p", "--port", action="store", type=int,
                               dest="port", default=PORT, help="The TCP port to use")
    cmdLineParser.add_argument("-C", "--global-cancel", action="store_true",
                               dest="global_cancel", default=False,
                               help="whether to trigger a globalCancel req")
    args = cmdLineParser.parse_args()
    print("Using args", args)
    logging.debug("Using args %s", args)
    # print(args)

    # enable logging when member vars are assigned
    from ibapi import utils
    Order.__setattr__ = utils.setattr_log
    Contract.__setattr__ = utils.setattr_log
    DeltaNeutralContract.__setattr__ = utils.setattr_log
    TagValue.__setattr__ = utils.setattr_log
    TimeCondition.__setattr__ = utils.setattr_log
    ExecutionCondition.__setattr__ = utils.setattr_log
    MarginCondition.__setattr__ = utils.setattr_log
    PriceCondition.__setattr__ = utils.setattr_log
    PercentChangeCondition.__setattr__ = utils.setattr_log
    VolumeCondition.__setattr__ = utils.setattr_log

    try:
        app = TestApp()
        if args.global_cancel:
            app.globalCancelOnly = True
        # ! [connect]
        app.connect("127.0.0.1", args.port, clientId=CLIENT_ID)
        # ! [connect]
        print("serverVersion:%s connectionTime:%s" % (app.serverVersion(),
                                                      app.twsConnectionTime()))

        # ! [clientrun]
        app.run()
        # ! [clientrun]
    except:
        raise
    finally:
        app.dumpTestCoverageSituation()
        app.dumpReqAnsErrSituation()


if __name__ == "__main__":
    main()
