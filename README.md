# Introduction

Momentum-Trading-Assistant (MTA) is a python program designed to replace a Momentum Trader using the Interactive Brokers Trader Workstation (TWS) in front of the screen during market opening hours, respectively to assist him during trading hours through order executions and the application of further individualized trading rules. Herein, MTA makes use of the API as provided by Interactive Brokers. This program is especially designed for Momentum Traders following the trading style of Mark Minervini, William O’Neal, Mark Richie II, Oliver Kell, Quallamaggie and many more.

This code offers a way to hard-wire your trading rules, execute them consequently and adjust these rules periodically after your personal post analysis. Momentum trading is directional trading and means that the entry prices defined in your daily trading plan must be above the current price, see more on order execution in the [User Manual](/User-Manual_Momentum-Trading-Assistant.pdf). Your trading strategy needs to be defined daily in the DailyTradingPlan.xlsx file. The code is currently written for trading stocks long only and has not been tested on other assets.

MTA does not make any trading decisions which are not predefined by the user in advance. Therefore, the stock selection, definition of risk and profit potential, entry and exit scenarios fully rely on the Momentum Trader’s judgement and decisions. This trading plan can also be updated when MTA is running so that it can be used to assist you while live trading.

MTA is currently set up to trade the markets of the US, Germany and Japan. With minor tweaks, also other markets can easily be added. MTA can only cover one market with assets in one currency at a time. If e.g. German and US markets need to be traded with overlapping market opening times, MTA needs to be run as two separate processes in parallel, one for Germany and one for the US.

The program can be started e.g. through the cmd prompt after you have opened and logged into your TWS. Make sure TWS is set up properly so that the API connection is enabled, you have subscribed to the relevant market data feeds and MTA has sufficient writing rights.

MTA is meant not only for trading-enthusiasts among the IT community, but also momentum traders with only limited IT and esp. coding know-how. Please therefore excuse that some explanations in the README as well as the User Manual are somewhat nitty gritty.

The README.md provides only a very first view on how to use MTA, but does not cover any further details about its many trading rules and functionalities. Therefore, please refer also to the more detailed [User Manual](/User-Manual_Momentum-Trading-Assistant.pdf) as provided within this project.

# Liabilities

This code is tested through my personal use for the US markets during the last several years, but still, it remains your responsibility to supervise MTA sufficiently during its application to avoid any unintended activities in your portfolio. The creator cannot be held liable for any financial damage occurring while using MTA.

# Quick start guide

This section contains all necessary steps you need to get MTA up and running:

  1) Ensure your IB TWS is set up properly to use the API with port 7496 see IB documentation at https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#tws-config-api

  2) Make sure not to use IB API as it is available via `pip` as this package is outdated and no longer supported. It needs to be downloaded and installed manually, see https://interactivebrokers.github.io/#. Follow the instruction on the website for installation. Make sure to add ibapi to your PYTHONPATH in your environment variables (e.g. `C:\TWS API\source\pythonclient`)

  3) Subscribe to the relevant market data on you IB-account

  4) Save this project to a folder of your choice

  5) Go to the `Inputs` folder and fill columns A, B and D to M of `DailyTradingPlan.xlsx`

  6) Log into TWS

  7) Open your CMD prompt for windows and, navigate to the folder where you saved the files (e.g. through `cd documents\foldername`)

  8) Start MTA through `python main.py`



It is recommended but not necessary to start MTA before the market opens.

# MTA input and output files

As detailed further in the [User Manual](/User-Manual_Momentum-Trading-Assistant.pdf), MTA requires six files as inputs for startup, which are located in the same folder and will return three files as outputs to this same folder. Only `DailyTradingPlan.xlsx`  contains your daily trading plan and needs to be updated daily. The input files are:

  - [`main.py`](/main.py)
  - [`Functionalities`](/Functionalities)
    - [`MyFunctionalities.py`](/Functionalities/MyFunctionalities.py)
  - [`Utilities/`](/Utilities)
    - [`MyOrders.py`](/Utilities/MyOrders.py)
    - [`MyUtilities.py`](/Utilities/MyUtilities.py)
  - [`Rules/`](/Rules)
    - [`ConstantsAndRules.py`](/Rules/ConstantsAndRules.py)
  - [`Inputs/`](/Inputs)
    - [`tickDataTemplate.xlsx`](/Inputs/tickDataTemplate.xlsx)
    - [`DailyTradingPlan.xlsx`](/Inputs/DailyTradingPlan.xlsx) (resp. `DailyTradingPlan_DE.xlsx` or `DailyTradingPlan_JP.xlsx`)

The program will return the following three files to the `Outputs` folder:

  - `yymmdd_fetch_open_positions.xlsx`
  - `yymmdd_fetch_new_positions.xlsx`
  - `yymmdd_trading_plan.xlsx`



# Starting MTA

It is recommended but not required to start MTA at any time before the market opening. The first row BTC of `DailyTradingPlan.xlsx` is recommended not to be changed to assure program stability.

Open the cmd prompt or your favorite IDE and locate the folder where the program is saved e.g. through `cd documents\foldername` on windows.

Start the program through its file name e.g. `python main.py`.

Define which market you want to trade, see Figure below. Since MTA can only trade one market at a time, if you seek to trade e.g. the German and US market in parallel, you need to prepare two `DailyTradingPlan.xlsx` and run MTA twice in parallel.

![image](https://github.com/user-attachments/assets/21979062-77f8-4c37-aba3-d7f66b572dfd)

Afterwards, an extract of your `DailyTradingPlan.xlsx` will be printed and you will be asked to confirm that the `DailyTradingPlan.xlsx` is correct with “y” in case, see Figure below.

![image](https://github.com/user-attachments/assets/19f69046-0b10-4c92-8550-698aefe654b2) 

Then define what %-invested you would like to go as a maximum for the day, see Figure below. The entered value can be `0 < x < ∞` and therefore can also be used for a margin account. Please see further information on the significance of this value in the [User Manual](/User-Manual_Momentum-Trading-Assistant.pdf).

![image](https://github.com/user-attachments/assets/c4df87a1-9e76-447d-a6b2-5dda474f04d4)

Finally, chose the indices of the correct market opening and closing hours while considering that indices start counting at 0, see Figure below.

![image](https://github.com/user-attachments/assets/cbeb0642-a38d-4576-b9f1-1e70f4eb9f50)



The program then starts its work without any further inputs required.



To assure a flawless start, it is recommended to check also the following based on the given prints in the cmd (or similar):



Are the company names correct based on the entered stock data?

Is the printed Account Information e.g. in terms of current %-invested correct?

Are the market opening hours correctly defined for the day?

Are there any other noticeable deviations to normal operation?



As a further support of your trading in case of US-market stocks, the code provides an information about the days to the next Earnings Calls of the companies mentioned in your `DailyTradingPlan.xlsx`, see the Figure below as an example.

![image](https://github.com/user-attachments/assets/5ef1cd22-fc86-4c4f-9827-766c69a83853)

The code gives you a warning if one earnings call is only three days or less away. Further, MTA checks if the open positions as defined in your `DailyTradingPlan.xlsx` are matching the open positions in your portfolio for the given currency (and therefore market) of the assets. In case this matches, the confirming message is shown in the Figure below. If this is not the case, MTA gives you a warning. This shall assure that all positions will be covered by a bracket order.

![image](https://github.com/user-attachments/assets/0dea2da4-7c56-4b98-8372-3beb185b255b)

If there are any issues during this starting phase of MTA, consider interrupting the code e.g. through `STRG + C` and restarting it with updated information.



If you start MTA the first time on your account, you should delete all open orders related to your stock holdings for this market. MTA can only receive order IDs of open orders which were previously sent with the same client ID. If this is not the case, it will lead to the definition of unnecessary bracket orders and impair also others of MTA’s functionalities.

## Program stability

It must be assured that MTA is running and has a continuous internet connection throughout its time of application. Therefore, please ensure that your computer does not go to sleep mode or shut down as well as that your internet connection is stable. I was able to increase MTA’s stability to a maximum through shifting TWS and MTA to a cloud computer. Further, as previously described, it is recommended to leave the first row of `DailyTradingPlan.xlsx` (BTC data stream) unchanged to avoid the code “falling asleep”.

# Contribution to this project

Your feedback as well as contribution is most welcome. This project shall serve to support our trading and improve our trading results.
Proposed next improvements are:
  - Slim down `main.py` through outsourcing of logical tests to `MyFunctionalities.py`
  - Increase focus on OOP standards (to be pursued soon in separate fork)
  - etc.

Therefore, brains-on please :)

# Software support

If you encounter any errors or uncertainties resp. ambiguities towards MTA’s usage, please feel free to come back to me any time in case I did not cover this topic in the [User Manual](/User-Manual_Momentum-Trading-Assistant.pdf).

