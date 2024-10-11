# Add imports if needed
from ibapi.order import Order

import datetime
import pytz


class MyOrders:

    @staticmethod
    def bracket_order(parent_order_id, req_id, timezone, ib_timezone_str, market_close, io_list):

        # Create Parent Order / Initial Entry
        parent = Order()
        parent.orderId = parent_order_id
        parent.orderType = "LMT"
        parent.action = "BUY"
        parent.tif = "GTD"
        # Order cancelled in two minute from now if it does not get filled
        # I want to avoid that price runs away and fills when it comes back in - this would not be directional
        parent.goodTillDate = \
            (datetime.datetime.now().astimezone(pytz.timezone(timezone)) + datetime.timedelta(minutes=2)) \
                .strftime("%Y%m%d %H:%M:%S " + ib_timezone_str)
        parent.lmtPrice = round(io_list['Buy limit price [$]'][req_id], 2)
        parent.totalQuantity = round(io_list['Quantity [#]'][req_id], 0)
        parent.transmit = False

        # Profit Target
        profit_target_order = Order()
        profit_target_order.orderId = parent_order_id + 1
        profit_target_order.orderType = "LMT"
        profit_target_order.action = "SELL"
        profit_target_order.tif = "GTC"
        profit_target_order.totalQuantity = round(io_list['Quantity [#]'][req_id], 0)
        profit_target_order.lmtPrice = round(io_list['Profit taker price [$]'][req_id], 2)
        profit_target_order.parentId = parent_order_id
        profit_target_order.transmit = False

        # Stop Loss
        stop_loss_order = Order()
        stop_loss_order.orderId = parent_order_id + 2
        stop_loss_order.orderType = "STP"
        stop_loss_order.action = "SELL"
        stop_loss_order.tif = "GTC"
        stop_loss_order.totalQuantity = round(io_list['Quantity [#]'][req_id], 0)
        stop_loss_order.auxPrice = round(io_list['Stop price [$]'][req_id], 2)
        stop_loss_order.parentId = parent_order_id
        stop_loss_order.transmit = True

        if io_list['Sell on close'][req_id]:
            # Market on close order if "sell on close" (faked MOC order since it did not execute in OCA)
            market_on_close_order = Order()
            market_on_close_order.orderId = parent_order_id + 3
            market_on_close_order.orderType = "MKT"
            market_on_close_order.action = "SELL"
            market_on_close_order.tif = "DAY"
            market_on_close_order.goodAfterTime = \
                (market_close - datetime.timedelta(minutes=5)).strftime("%Y%m%d %H:%M:%S " + ib_timezone_str)
            market_on_close_order.totalQuantity = round(io_list['Quantity [#]'][req_id], 0)
            market_on_close_order.parentId = parent_order_id
            market_on_close_order.transmit = True
            # Only the very last child of the array is allowed to be .transmit = True
            stop_loss_order.transmit = False

            bracket_orders = [parent, profit_target_order, stop_loss_order, market_on_close_order]

            print("\nStock ID:", req_id, io_list['Symbol'][req_id],
                  "- Sell on close OCA bracket defined. (",
                  datetime.datetime.now().astimezone(pytz.timezone(timezone)).strftime("%H:%M:%S"), ")")

            # Reporting
            io_list.loc[req_id, 'sellOnCloseOrderId'] = parent_order_id + 3

        else:
            bracket_orders = [parent, profit_target_order, stop_loss_order]

        # Reporting
        io_list.loc[req_id, 'parent_order_id'] = parent_order_id
        io_list.loc[req_id, 'profitOrderId'] = parent_order_id + 1
        io_list.loc[req_id, 'stopOrderId'] = parent_order_id + 2

        return bracket_orders, io_list

    # This is technically not a bracket order, it is an OCA order
    @staticmethod
    def one_cancels_all(order_id, total_quantity, lmt_price, aux_price, req_id, timezone, ib_timezone_str, market_close,
                        io_list):

        # Profit Target
        profit_target_order = Order()
        profit_target_order.orderId = order_id
        profit_target_order.orderType = "LMT"
        profit_target_order.action = "SELL"
        profit_target_order.tif = "GTC"
        profit_target_order.totalQuantity = total_quantity
        profit_target_order.lmtPrice = lmt_price
        profit_target_order.ocaGroup = "OCA_" + str(order_id)
        profit_target_order.ocaType = 2

        # Stop Loss
        stop_loss_order = Order()
        stop_loss_order.orderId = order_id + 1
        stop_loss_order.orderType = "STP"
        stop_loss_order.action = "SELL"
        stop_loss_order.tif = "GTC"
        stop_loss_order.totalQuantity = total_quantity
        stop_loss_order.auxPrice = aux_price
        stop_loss_order.ocaGroup = "OCA_" + str(order_id)
        stop_loss_order.ocaType = 2

        if io_list['Sell on close'][req_id]:
            # Market on close order if "sell on close" - fake MOC (see above)
            market_on_close_order = Order()
            market_on_close_order.orderId = order_id + 2
            market_on_close_order.orderType = "MKT"
            market_on_close_order.action = "SELL"
            market_on_close_order.tif = "DAY"
            market_on_close_order.ocaGroup = "OCA_" + str(order_id)
            market_on_close_order.goodAfterTime = \
                (market_close - datetime.timedelta(minutes=5)).strftime("%Y%m%d %H:%M:%S " + ib_timezone_str)
            market_on_close_order.totalQuantity = total_quantity
            market_on_close_order.ocaType = 2

            oca = [profit_target_order, stop_loss_order, market_on_close_order]

            print("\nStock ID:", req_id, io_list['Symbol'][req_id],
                  "- Sell on close OCA bracket defined. (",
                  datetime.datetime.now().astimezone(pytz.timezone(timezone)).strftime("%H:%M:%S"), ")")

            # Reporting & deletion of previous status
            io_list.loc[req_id, 'sellOnCloseOrderId'] = order_id + 2
            io_list.loc[req_id, 'SOC order filled'] = False

        else:
            oca = [profit_target_order, stop_loss_order]

        # Reporting & deletion of previous status
        io_list.loc[req_id, 'profitOrderId'] = order_id
        io_list.loc[req_id, 'Profit order filled'] = False
        io_list.loc[req_id, 'stopOrderId'] = order_id + 1
        io_list.loc[req_id, 'Stop order filled'] = False

        return oca, io_list

    @staticmethod
    def sell_market_order(order_id, total_quantity):
        # Create Parent Order / Initial Entry
        order = Order()
        order.orderId = order_id
        order.orderType = "MKT"
        order.action = "SELL"
        order.totalQuantity = total_quantity

        return order
