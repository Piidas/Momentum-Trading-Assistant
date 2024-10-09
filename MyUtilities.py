# Add imports if needed
from ibapi.contract import *
import pandas as pd
import datetime
import pytz
from openpyxl import load_workbook
import time
from bs4 import BeautifulSoup
import requests
import re

class MyUtilities:

    @staticmethod
    def get_contract_details(iOList, reqId: int):

        # Create contract details
        contract = Contract()
        contract.symbol = iOList['Symbol'][reqId]
        contract.secType = iOList['Security Type'][reqId]
        contract.currency = iOList['Currency'][reqId]
        contract.exchange = iOList['Exchange'][reqId]
        contract.primaryExchange = iOList['Primary Exchange'][reqId]

        return contract

    # This function gives all columns the proper dtype
    # Can return one or two dataframes through return_both_dataframes
    @staticmethod
    def dataFrameCleanUp(iOListClean, tickDataClean, return_both_dataframes=False):

        # Define a list of column names to apply the lambda operation to
        bool_columns_to_convert = ['Open position', 'Add and reduce', 'Sell on close', 'Stop low of day',
                                   'Stop undercut', 'Crossed buy price',
                                   'Order executed', 'Order filled', 'Profit order filled', 'Stop order filled',
                                   'SOC order filled', '2% above buy point', 'New OCA bracket', '5% above buy point',
                                   'Bad close rule', 'Stock sold', 'Spread above limit', 'Price above limit',
                                   'Stock looped', 'Open position bracket submitted', 'Add and reduce executed',
                                   'Open position updated', 'New position updated', 'New position added',
                                   'Invest limit reached', 'Position below limit', 'Max. daily loss reached',
                                   'Bad close checked']

        # Define a list of column names to apply the conversion to str
        str_columns_to_convert = ['Symbol', 'Company name', 'Stop undercut [time]', 'Crossed buy price [time]',
                                  'Order executed [time]', 'New OCA bracket [time]', '5% above buy point [time]',
                                  'Bad close rule [time]', 'Stock sold [time]', 'Open position updated [time]',
                                  'New position updated [time]', 'New position added [time]', 'Stop timestamp',
                                  'Invest limit reached [time]', 'Max. daily loss reached [time]', 'liquidHours',
                                  'timeZoneId', 'local opening time', 'local closing time']

        # Define a list of column names to apply the conversion to float
        float_columns_to_convert = ['Entry price [$]', 'Stop price [$]', 'Buy limit price [$]',
                                    'Profit taker price [$]', 'Sell bellow SMA [$]', 'Spread at execution [%]',
                                    'Last stop price', 'LAST price [$]', 'BID price [$]', 'ASK price [$]',
                                    'HIGH price [$]', 'LOW price [$]', 'CLOSE price [$]']

        # Apply the bool lambda operation to each specified column
        for col in bool_columns_to_convert:
            iOListClean[col] = iOListClean[col].apply(lambda x: True if not pd.isnull(x) and x == 1.0 else False)

        # Apply the conversion to str type and clear contents for all but the first column
        for col in str_columns_to_convert:
            iOListClean[col] = iOListClean[col].astype(str)
            if col != 'Symbol':
                iOListClean[col] = ""

        # Apply the conversion to float type
        iOListClean[float_columns_to_convert] = iOListClean[float_columns_to_convert].astype('float64')

        # Define a list of column names to apply the conversion to str
        tick_str_columns = ['timeStamp', 'Symbol']

        # Apply to conversion to str type and return both if needed
        if return_both_dataframes == True:
            for col in tick_str_columns:
                tickDataClean[col] = tickDataClean[col].astype(str)

            return iOListClean, tickDataClean

        else:
            return iOListClean

    @staticmethod
    def document_trading_parameters(tradingPlan, MAX_STOCK_SPREAD, SELL_HALF_REVERSAL_RULE, SELL_FULL_REVERSAL_RULE,
                                    BAD_CLOSE_RULE, MAX_ALLOWED_DAILY_PNL_LOSS, MIN_POSITION_SIZE):

        tradingPlan.loc[0, 'MAX_STOCK_SPREAD'] = MAX_STOCK_SPREAD
        tradingPlan.loc[0, 'SELL_HALF_REVERSAL_RULE'] = SELL_HALF_REVERSAL_RULE
        tradingPlan.loc[0, 'SELL_FULL_REVERSAL_RULE'] = SELL_FULL_REVERSAL_RULE
        tradingPlan.loc[0, 'BAD_CLOSE_RULE'] = BAD_CLOSE_RULE
        tradingPlan.loc[0, 'MAX_ALLOWED_DAILY_PNL_LOSS'] = MAX_ALLOWED_DAILY_PNL_LOSS
        tradingPlan.loc[0, 'MIN_POSITION_SIZE'] = MIN_POSITION_SIZE

        return tradingPlan

    @staticmethod
    def check_open_orders(open_positions, symbol, currency, position):
        """
        Updates the open_positions DataFrame with the given symbol, currency, and position

        Parameters:
        - open_positions (pd.DataFrame): DataFrame to update.
        - symbol (str): The symbol of the asset.
        - currency (str): The currency of the position.
        - position (str): The position size as a decimal string.

        Returns:
        - pd.DataFrame: Updated open_positions DataFrame.
        """
        position = pd.to_numeric(position)

        # Check if there's an existing row with the same symbol and currency
        mask = (open_positions['Symbol'] == symbol) & (open_positions['Currency'] == currency)
        if open_positions.loc[mask].empty:
            # If no existing row, create a new DataFrame for the row and use pd.concat to add it
            new_row_df = pd.DataFrame([{
                'Symbol': symbol,
                'Currency': currency,
                'Quantity [#]': position
                # Add other columns as necessary
            }])
            open_positions = pd.concat([open_positions, new_row_df], ignore_index=True)
        else:
            # If existing row, update the position
            open_positions.loc[mask, 'Quantity [#]'] = position

        return open_positions

    @staticmethod
    def compare_positions_currency_specific(open_positions, iOList):
        """
        Compares the sum of 'Quantity [#]' for each 'Symbol' in both open_positions and iOList DataFrames,
        specifically for the currency present in iOList (ignoring the first line). Checks if the quantities
        per Symbol in iOList cover the relevant quantities in open_positions for the given currency.

        Parameters:
        - open_positions (pd.DataFrame): DataFrame containing current open positions across various currencies.
        - iOList (pd.DataFrame): DataFrame containing positions in a single currency, excluding the first row.
        """
        # Exclude the first row from iOList
        iOList_filtered = iOList.iloc[1:]

        # Assuming all entries in iOList are in the same currency, determine that currency
        currency = iOList_filtered['Currency'].iloc[0]

        # Filter both DataFrames for the relevant currency
        open_positions_filtered = open_positions[open_positions['Currency'] == currency]
        iOList_filtered = iOList_filtered[iOList_filtered['Currency'] == currency]
        iOList_filtered = iOList_filtered[iOList_filtered['Open position'] == True]

        # Group by 'Symbol' and calculate the sum of 'Quantity [#]'
        open_positions_sum = open_positions_filtered.groupby('Symbol')['Quantity [#]'].sum()
        iOList_sum = iOList_filtered.groupby('Symbol')['Quantity [#]'].sum()

        # Compare the aggregated quantities
        if open_positions_sum.equals(iOList_sum):
            print("\nDailyTradingPlan matches current open portfolio positions for currency: " + currency)
        else:
            print("\n### ATTENTION ### DailyTradingPlan does not match current open portfolio positions for "
                  "currency: " + currency)
            print("\nOpen positions are:")
            print(open_positions_sum)
            print("\nOpen positions as per DailyTradingPlan are:")
            print(iOList_sum)

    @staticmethod
    def update_iOList_order_execution_status(status, orderId, lastFillPrice, filled, remaining, iOList, TIMEZONE):

        # "Tries" need to find the relevant orderId to confirm the "Filled" status
        if status == "Filled" or ((status == "PreSubmitted" or status == "Submitted" or
                                   status == "PendingCancel" or status == "Cancelled") and filled > 0):

            try:
                index = iOList[iOList['parentOrderId'] == orderId].index.item()
                iOList.loc[index, 'Order filled'] = True
                iOList.loc[index, 'Entry price [$]'] = lastFillPrice
                print("\nStock ID:", index, iOList['Symbol'][index], "buy order filled. (",
                      datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)).strftime("%H:%M:%S"), ")")
                if filled > 0:
                    iOList.loc[index, 'Quantity [#]'] = int(filled)

            except:
                pass

            try:
                index = iOList[iOList['profitOrderId'] == orderId].index.item()
                iOList.loc[index, 'Profit order filled'] = True
                iOList.loc[index, 'Profit taker price [$]'] = lastFillPrice
                print("\nStock ID:", index, iOList['Symbol'][index], "profit order filled. (",
                      datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)).strftime("%H:%M:%S"), ")")
                if filled > 0:
                    # Uses "remaining" since I want to know the position remaining in my portfolio
                    iOList.loc[index, 'Quantity [#]'] = int(remaining)

            except:
                pass

            try:
                index = iOList[iOList['stopOrderId'] == orderId].index.item()
                iOList.loc[index, 'Stop order filled'] = True
                iOList.loc[index, 'Stop price [$]'] = lastFillPrice
                print("\nStock ID:", index, iOList['Symbol'][index], "stop loss order filled. (",
                      datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)).strftime("%H:%M:%S"), ")")
                if filled > 0:
                    # Uses "remaining" since I want to know the position remaining in my portfolio
                    iOList.loc[index, 'Quantity [#]'] = int(remaining)

            except:
                pass

            try:
                index = iOList[iOList['sellOnCloseOrderId'] == orderId].index.item()
                iOList.loc[index, 'SOC order filled'] = True
                iOList.loc[index, 'Sell bellow SMA [$]'] = lastFillPrice
                print("\nStock ID:", index, iOList['Symbol'][index], "SOC order filled. (",
                      datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)).strftime("%H:%M:%S"), ")")
                if filled > 0:
                    # Uses "remaining" since I want to know the position remaining in my portfolio
                    iOList.loc[index, 'Quantity [#]'] = int(remaining)

            except:
                pass

        return iOList

    @staticmethod
    def update_daily_PnL(portfolio_size, EXR_RATE, realized_PnL, realized_PnL_percent_last, unrealized_PnL,
                         unrealized_PnL_percent_last, MAX_ALLOWED_DAILY_PNL_LOSS, max_daily_loss_reached, TIMEZONE,
                         PORTFOLIO_UPDATE_PRINTS):

        # Starts the DailyPnL calculation
        if not pd.isnull(portfolio_size):
            daily_PnL = (realized_PnL + unrealized_PnL) / EXR_RATE  # Only PnL figures come in local currency e.g. YEN
            daily_PnL_percent = daily_PnL / portfolio_size

            realized_PnL_percent = realized_PnL / portfolio_size * 100
            unrealized_PnL_percent = unrealized_PnL / portfolio_size * 100

            # Only updates if something has changed (beware the units)
            # Since default is 0 at program start, when I am 0% invested, nothing is printed
            if abs(realized_PnL_percent - realized_PnL_percent_last) > PORTFOLIO_UPDATE_PRINTS or \
                    abs(unrealized_PnL_percent - unrealized_PnL_percent_last) > PORTFOLIO_UPDATE_PRINTS:
                print("\nYour daily PnL (realized + unrealized) is now", round(daily_PnL_percent * 100, 2), "%. (",
                      datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)).strftime("%H:%M:%S"), ")")

                print("Realized:", round(realized_PnL_percent, 2), "%.   ")
                print("Unrealized:", round(unrealized_PnL_percent, 2), "%.")

                realized_PnL_percent_last = realized_PnL_percent
                unrealized_PnL_percent_last = unrealized_PnL_percent

            # Sets max_daily_loss_reached to True if more than 3% are lost which will stopp all new buying of stocks
            if max_daily_loss_reached == False and daily_PnL_percent <= MAX_ALLOWED_DAILY_PNL_LOSS:
                max_daily_loss_reached = True
                print(f"\nDaily max. loss of {round(MAX_ALLOWED_DAILY_PNL_LOSS * 100, 1)}% is reached. (",
                      datetime.datetime.now().astimezone(pytz.timezone(TIMEZONE)).strftime("%H:%M:%S"), ")")

        return max_daily_loss_reached, realized_PnL_percent_last, unrealized_PnL_percent_last

    @staticmethod
    def save_excel_outputs(filename, pd_dataframe):

        with pd.ExcelWriter(filename) as writer:
            pd_dataframe.to_excel(writer, sheet_name="Sheet1")

        print("\nExcel output saved.\n")

    @staticmethod
    def dailytradingplan_stop_update(i, stop_loss_price, NAME_OF_DAILYTRADINGPLAN):

        # Attempt to update the DailyTradingPlan up to 3 times with a 20-second delay between tries
        # if a PermissionError is encountered (e.g., file is open).

        max_attempts = 3
        attempt = 0
        success_writing_xls = False

        while attempt < max_attempts and not success_writing_xls:
            try:
                workbook = load_workbook(filename=NAME_OF_DAILYTRADINGPLAN)
                sheet = workbook.active
                cellName = "I" + str(i + 2)  # Adjusting index for Excel row.
                sheet[cellName] = stop_loss_price
                workbook.save(filename=NAME_OF_DAILYTRADINGPLAN)
                success_writing_xls = True  # Update was successful, exit the loop
                print("DailyTradingPlan updated successfully.")
            except PermissionError as e:
                attempt += 1  # Increase the attempt counter
                time_now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"Attempt {attempt}: Did not get permission to write to DailyTradingPlan."
                      f"Will try again in 20 secs. ({time_now_str})")
                print(f"Error details: {e}")
                if attempt < max_attempts:
                    time.sleep(20)  # Wait for 20 seconds before the next attempt

        if not success_writing_xls:
            # Final message if all attempts fail
            print("Failed to update DailyTradingPlan after 3 attempts - stopp loss will change back to original value.")

    @staticmethod
    def find_earnings_dates(iOList, market_opening):

        set_of_stocks = set(iOList['Symbol'][1:])

        data_table = pd.DataFrame(columns=['Symbol', 'Earnings Date', 'Days to Earnings'])
        data_table['Symbol'] = list(set_of_stocks)

        try:
            for stock in set_of_stocks:
                earnings_date = MyUtilities.scrape_earnings_date(stock)
                data_table.loc[data_table['Symbol'] == stock, 'Earnings Date'] = earnings_date
                data_table.loc[data_table['Symbol'] == stock, 'Days to Earnings'] = \
                    MyUtilities.calculate_days_to_earnings(earnings_date, market_opening)
                time.sleep(0.5)

            data_table = data_table.sort_values(by='Days to Earnings')
            print('The earnings dates for your focus stocks are:')
            print(data_table)
            for index, row in data_table.iterrows():
                if row['Days to Earnings'] < 4:
                    print(f'### ATTENTION ### {row["Symbol"]} has its earnings in {row["Days to Earnings"]} days.')

        except Exception as e:
            print(f'It was not possible to get the earnings data. Error code: {e}')

        return

    @staticmethod
    def scrape_earnings_date(stock):

        url = f'https://www.earningswhispers.com/stocks/{stock}'

        try:
            # Request the page
            res = requests.get(url)
            soup = BeautifulSoup(res.text, 'html.parser')

            # Find the meta tag with the 'og:description' property
            meta_tag = soup.find('meta', property='og:description')

            # Check if the meta tag was found
            if meta_tag and 'content' in meta_tag.attrs:
                # Extract the content attribute
                content = meta_tag['content']

                # Use regex to find the date in the format Month Day, Year (e.g., August 21, 2024)
                date_match = re.search(r'\b\w+ \d{1,2}, \d{4}\b', content)
                if date_match:
                    earnings_date = date_match.group(0)
                    return earnings_date

            return None
        except Exception as e:
            print(f'It was not possible to scrape the earnings data. Error code: {e}')

    @staticmethod
    def calculate_days_to_earnings(earnings_date_str, reference_date):
        try:
            # Convert the earnings_date_str to a datetime object (naive)
            earnings_date_naive = datetime.datetime.strptime(earnings_date_str, '%B %d, %Y')

            # Make the earnings_date aware by localizing it to the same timezone as reference_date
            reference_tz = reference_date.tzinfo
            earnings_date_aware = reference_tz.localize(earnings_date_naive)

            # Normalize both dates to midnight
            earnings_date_midnight = earnings_date_aware.replace(hour=0, minute=0, second=0, microsecond=0)
            reference_date_midnight = reference_date.replace(hour=0, minute=0, second=0, microsecond=0)

            # Calculate the difference in days
            delta = (earnings_date_midnight - reference_date_midnight).days
            return delta
        except Exception as e:
            print(f'It was not possible to calculate the delta to the earnings dates. Error code: {e}')

    @staticmethod
    def should_start_market_opening_function(iOList, time_delta_to_initialized_market):
        # Calculate the number of populated entries
        populated_entries = iOList['Company name'].apply(lambda x: x != "").sum()
        total_entries = len(iOList)

        # Check if the list is fully populated
        if time_delta_to_initialized_market.days > 10:
            if populated_entries == total_entries:
                return True

            # Check if the list is one entry away from being fully populated
            elif populated_entries == total_entries - 1:
                # Find the index of the remaining unpopulated entry
                unpopulated_index = iOList['Company name'].apply(lambda x: x == "").idxmax()

                # If the remaining entry is the one with reqId = 0
                if unpopulated_index == 0:
                    return True

        return False
