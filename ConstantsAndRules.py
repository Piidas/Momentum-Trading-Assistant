# Constants and rule are defined here
port = 7497   # for paper trading
# port = 7496
max_stock_spread = 0.0125
sell_half_reversal_rule = 0.06
sell_full_reversal_rule = 0.1
bad_close_rule = 0.15
max_allowed_daily_pnl_loss = -0.05
min_position_size = 0.001
portfolio_update_prints = 0.1

# TASK: Use only IB timezone
market_constants = {
    "JP": {
        "market_has_pause": True,
        "timezone": "Japan",
        "exr_rate": 150,  # YEN per USD
        "name_of_dailytradingplan": "DailyTradingPlan_JP.xlsx",
        "name_of_dailytradingplan_save": "_trading_plan_JP.xlsx",
        "name_of_fetchdata_new_save": "_fetch_new_positions_JP.xlsx",
        "name_of_fetchdata_open_save": "_fetch_open_positions_JP.xlsx",
        "client_id": 11
    },
    "NY": {
        "market_has_pause": False,
        "timezone": "America/New_York",
        "exr_rate": 1,  # USD per USD
        "name_of_dailytradingplan": "DailyTradingPlan.xlsx",
        "name_of_dailytradingplan_save": "_trading_plan.xlsx",
        "name_of_fetchdata_new_save": "_fetch_new_positions.xlsx",
        "name_of_fetchdata_open_save": "_fetch_open_positions.xlsx",
        "client_id": 22
    },
    "DE": {
        "market_has_pause": False,
        "timezone": "Europe/Berlin",
        "exr_rate": 0.91,  # EUR per USD
        "name_of_dailytradingplan": "DailyTradingPlan_DE.xlsx",
        "name_of_dailytradingplan_save": "_trading_plan_DE.xlsx",
        "name_of_fetchdata_new_save": "_fetch_new_positions_DE.xlsx",
        "name_of_fetchdata_open_save": "_fetch_open_positions_DE.xlsx",
        "client_id": 33
    }
}
