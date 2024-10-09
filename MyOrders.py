# Add imports if needed
from ibapi.order import Order

import datetime
import pytz


class MyOrders:

    @staticmethod
    def bracketOrder(parentOrderId, reqId, TIMEZONE, ib_timezone_str, market_close, iOList):

        # Create Parent Order / Initial Entry
        parent = Order()
        parent.orderId = parentOrderId
        parent.orderType = "LMT"
        parent.action = "BUY"
        parent.tif = "GTD"
        # Order cancelled in two minute from now if it does not get filled
        # I want to avoid that price runs away and fills when it comes back in - this would not be directional
        parent.goodTillDate = \
            (datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)) + datetime.timedelta(minutes=2)) \
                .strftime("%Y%m%d %H:%M:%S " + ib_timezone_str)
        parent.lmtPrice = round(iOList['Buy limit price [$]'][reqId], 2)
        parent.totalQuantity = round(iOList['Quantity [#]'][reqId], 0)
        parent.transmit = False

        # Profit Target
        profitTargetOrder = Order()
        profitTargetOrder.orderId = parentOrderId + 1
        profitTargetOrder.orderType = "LMT"
        profitTargetOrder.action = "SELL"
        profitTargetOrder.tif = "GTC"
        profitTargetOrder.totalQuantity = round(iOList['Quantity [#]'][reqId], 0)
        profitTargetOrder.lmtPrice = round(iOList['Profit taker price [$]'][reqId], 2)
        profitTargetOrder.parentId = parentOrderId
        profitTargetOrder.transmit = False

        # Stop Loss
        stopLossOrder = Order()
        stopLossOrder.orderId = parentOrderId + 2
        stopLossOrder.orderType = "STP"
        stopLossOrder.action = "SELL"
        stopLossOrder.tif = "GTC"
        stopLossOrder.totalQuantity = round(iOList['Quantity [#]'][reqId], 0)
        stopLossOrder.auxPrice = round(iOList['Stop price [$]'][reqId], 2)
        stopLossOrder.parentId = parentOrderId
        stopLossOrder.transmit = True

        if iOList['Sell on close'][reqId] == True:
            # Market on close order if "sell on close" (faked MOC order since it did not execute in OCA)
            marketOnCloseOrder = Order()
            marketOnCloseOrder.orderId = parentOrderId + 3
            marketOnCloseOrder.orderType = "MKT"
            marketOnCloseOrder.action = "SELL"
            marketOnCloseOrder.tif = "DAY"
            marketOnCloseOrder.goodAfterTime = \
                (market_close - datetime.timedelta(minutes=5)).strftime("%Y%m%d %H:%M:%S " + ib_timezone_str)
            marketOnCloseOrder.totalQuantity = round(iOList['Quantity [#]'][reqId], 0)
            marketOnCloseOrder.parentId = parentOrderId
            marketOnCloseOrder.transmit = True
            # Only the very last child of the array is allowed to be .transmit = True
            stopLossOrder.transmit = False

            bracketOrders = [parent, profitTargetOrder, stopLossOrder, marketOnCloseOrder]

            print("\nStock ID:", reqId, iOList['Symbol'][reqId],
                  "- Sell on close OCA bracket defined. (",
                  datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)).strftime("%H:%M:%S"), ")")

            # Reporting
            iOList.loc[reqId, 'sellOnCloseOrderId'] = parentOrderId + 3

        else:
            bracketOrders = [parent, profitTargetOrder, stopLossOrder]

        # Reporting
        iOList.loc[reqId, 'parentOrderId'] = parentOrderId
        iOList.loc[reqId, 'profitOrderId'] = parentOrderId + 1
        iOList.loc[reqId, 'stopOrderId'] = parentOrderId + 2

        return bracketOrders, iOList


    # This is technically not a bracket order, it is an OCA order
    @staticmethod
    def OneCancelsAll(orderId, totalQuantity, lmtPrice, auxPrice, reqId, TIMEZONE, ib_timezone_str, market_close,
                      iOList):

        # Profit Target
        profitTargetOrder = Order()
        profitTargetOrder.orderId = orderId
        profitTargetOrder.orderType = "LMT"
        profitTargetOrder.action = "SELL"
        profitTargetOrder.tif = "GTC"
        profitTargetOrder.totalQuantity = totalQuantity
        profitTargetOrder.lmtPrice = lmtPrice
        profitTargetOrder.ocaGroup = "OCA_" + str(orderId)
        profitTargetOrder.ocaType = 2


        # Stop Loss
        stopLossOrder = Order()
        stopLossOrder.orderId = orderId + 1
        stopLossOrder.orderType = "STP"
        stopLossOrder.action = "SELL"
        stopLossOrder.tif = "GTC"
        stopLossOrder.totalQuantity = totalQuantity
        stopLossOrder.auxPrice = auxPrice
        stopLossOrder.ocaGroup = "OCA_" + str(orderId)
        stopLossOrder.ocaType = 2

        if iOList['Sell on close'][reqId] == True:
            # Market on close order if "sell on close" - fake MOC (see above)
            marketOnCloseOrder = Order()
            marketOnCloseOrder.orderId = orderId + 2
            marketOnCloseOrder.orderType = "MKT"
            marketOnCloseOrder.action = "SELL"
            marketOnCloseOrder.tif = "DAY"
            marketOnCloseOrder.ocaGroup = "OCA_" + str(orderId)
            marketOnCloseOrder.goodAfterTime = \
                (market_close - datetime.timedelta(minutes=5)).strftime("%Y%m%d %H:%M:%S " + ib_timezone_str)
            marketOnCloseOrder.totalQuantity = totalQuantity
            marketOnCloseOrder.ocaType = 2

            OCA = [profitTargetOrder, stopLossOrder, marketOnCloseOrder]

            print("\nStock ID:", reqId, iOList['Symbol'][reqId],
                  "- Sell on close OCA bracket defined. (",
                  datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)).strftime("%H:%M:%S"), ")")

            # Reporting & deletion of previous status
            iOList.loc[reqId, 'sellOnCloseOrderId'] = orderId + 2
            iOList.loc[reqId, 'SOC order filled'] = False

        else:
            OCA = [profitTargetOrder, stopLossOrder]

        # Reporting & deletion of previous status
        iOList.loc[reqId, 'profitOrderId'] = orderId
        iOList.loc[reqId, 'Profit order filled'] = False
        iOList.loc[reqId, 'stopOrderId'] = orderId + 1
        iOList.loc[reqId, 'Stop order filled'] = False

        return OCA, iOList


    @staticmethod
    def sellMarketOrder(orderId, totalQuantity):
        # Create Parent Order / Initial Entry
        order = Order()
        order.orderId = orderId
        order.orderType = "MKT"
        order.action = "SELL"
        order.totalQuantity = totalQuantity

        return order
