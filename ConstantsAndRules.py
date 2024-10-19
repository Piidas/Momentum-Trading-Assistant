# Constants and rule are defined here
PORT = 7497   # for paper trading
# PORT = 7496
MAX_STOCK_SPREAD = 0.0125
SELL_HALF_REVERSAL_RULE = 0.06
SELL_FULL_REVERSAL_RULE = 0.1
BAD_CLOSE_RULE = 0.15
MAX_ALLOWED_DAILY_PNL_LOSS = -0.05
MIN_POSITION_SIZE = 0.001
PORTFOLIO_UPDATE_PRINTS = 0.1

# TASK: Use only IB TIMEZONE
market_constants = {
    "JP": {
        "MARKET_HAS_PAUSE": True,
        "TIMEZONE": "Japan",
        "EXR_RATE": 150,  # YEN per USD
        "NAME_OF_DAILYTRADINGPLAN": "DailyTradingPlan_JP.xlsx",
        "NAME_OF_DAILYTRADINGPLAN_SAVE": "_trading_plan_JP.xlsx",
        "NAME_OF_FETCHDATA_NEW_SAVE": "_fetch_new_positions_JP.xlsx",
        "NAME_OF_FETCHDATA_OPEN_SAVE": "_fetch_open_positions_JP.xlsx",
        "CLIENT_ID": 11
    },
    "NY": {
        "MARKET_HAS_PAUSE": False,
        "TIMEZONE": "America/New_York",
        "EXR_RATE": 1,  # USD per USD
        "NAME_OF_DAILYTRADINGPLAN": "DailyTradingPlan.xlsx",
        "NAME_OF_DAILYTRADINGPLAN_SAVE": "_trading_plan.xlsx",
        "NAME_OF_FETCHDATA_NEW_SAVE": "_fetch_new_positions.xlsx",
        "NAME_OF_FETCHDATA_OPEN_SAVE": "_fetch_open_positions.xlsx",
        "CLIENT_ID": 22
    },
    "DE": {
        "MARKET_HAS_PAUSE": False,
        "TIMEZONE": "Europe/Berlin",
        "EXR_RATE": 0.91,  # EUR per USD
        "NAME_OF_DAILYTRADINGPLAN": "DailyTradingPlan_DE.xlsx",
        "NAME_OF_DAILYTRADINGPLAN_SAVE": "_trading_plan_DE.xlsx",
        "NAME_OF_FETCHDATA_NEW_SAVE": "_fetch_new_positions_DE.xlsx",
        "NAME_OF_FETCHDATA_OPEN_SAVE": "_fetch_open_positions_DE.xlsx",
        "CLIENT_ID": 33
    }
}
