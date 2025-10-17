# Add imports if needed
from ibapi.contract import *
from pathlib import Path
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
    def feed_size_io_lists(io_list, io_list_copy_for_tick_data, tick_type, req_id, size):

        if tick_type == "ASK_SIZE":
            io_list.loc[req_id, 'ASK size'] = float(size)
            io_list_copy_for_tick_data.loc[req_id, 'ASK size'] = float(size)

        if tick_type == "BID_SIZE":
            io_list.loc[req_id, 'BID size'] = float(size)
            io_list_copy_for_tick_data.loc[req_id, 'BID size'] = float(size)

        if tick_type == "VOLUME":
            io_list.loc[req_id, 'Volume'] = float(size)
            io_list_copy_for_tick_data.loc[req_id, 'Volume'] = float(size)

        return io_list, io_list_copy_for_tick_data

    @staticmethod
    def feed_price_io_lists(io_list, io_list_copy_for_tick_data, tick_type, req_id, price):

        if tick_type == "CLOSE":
            io_list.loc[req_id, 'CLOSE price [$]'] = round(price, 2)
            io_list_copy_for_tick_data.loc[req_id, 'CLOSE price [$]'] = round(price, 2)

        if tick_type == "BID":
            io_list.loc[req_id, 'BID price [$]'] = round(price, 2)
            io_list_copy_for_tick_data.loc[req_id, 'BID price [$]'] = round(price, 2)

        if tick_type == "ASK":
            io_list.loc[req_id, 'ASK price [$]'] = round(price, 2)
            io_list_copy_for_tick_data.loc[req_id, 'ASK price [$]'] = round(price, 2)

        if tick_type == "LAST":
            io_list.loc[req_id, 'LAST price [$]'] = round(price, 2)
            io_list_copy_for_tick_data.loc[req_id, 'LAST price [$]'] = round(price, 2)

        if tick_type == "HIGH":
            if pd.isnull(io_list['HIGH price [$]'][req_id]) or price > io_list['HIGH price [$]'][req_id]:
                io_list.loc[req_id, 'HIGH price [$]'] = round(price, 2)

        if tick_type == "LOW":
            if pd.isnull(io_list['LOW price [$]'][req_id]) or price < io_list['LOW price [$]'][req_id]:
                io_list.loc[req_id, 'LOW price [$]'] = round(price, 2)

        return io_list, io_list_copy_for_tick_data

    @staticmethod
    def get_contract_details(io_list, req_id: int):

        # Create contract details
        contract = Contract()
        contract.symbol = io_list['Symbol'][req_id]
        contract.secType = io_list['Security Type'][req_id]
        contract.currency = io_list['Currency'][req_id]
        contract.exchange = io_list['Exchange'][req_id]
        contract.primaryExchange = io_list['Primary Exchange'][req_id]

        return contract

    # This function gives all columns the proper dtype
    # Can return one or two dataframes through return_both_dataframes
    @staticmethod
    def clean_up_data_frame(io_list_clean, tick_data_clean, return_both_dataframes=False):

        # Define a list of column names to apply the lambda operation to
        bool_columns_to_convert = ['Open position', 'Add and reduce', 'Sell on close', 'Stop low of day',
                                   'Sell negative on day 1', 'Stop undercut', 'Crossed buy price',
                                   'Order executed', 'Order filled', 'Profit order filled', 'Stop order filled',
                                   'Market order filled', 'SOC order filled', '2% above buy point', 'New OCA bracket',
                                   '5% above buy point', 'Bad close rule', 'x-R profits', 'Stock sold',
                                   'Spread above limit', 'Price above limit', 'Stock looped',
                                   'Open position bracket submitted', 'Add and reduce executed',
                                   'Open position updated', 'New position updated', 'New position added',
                                   'Invest limit reached', 'Position below limit', 'Max. daily loss reached',
                                   'Bad close checked', 'Negative close checked']

        # Define a list of column names to apply the conversion to str
        str_columns_to_convert = ['Symbol', 'Company name', 'Stop undercut [time]', 'Crossed buy price [time]',
                                  'Order executed [time]', 'New OCA bracket [time]', '5% above buy point [time]',
                                  'Bad close rule [time]', 'x-R profits [time]', 'Stock sold [time]',
                                  'Open position updated [time]',
                                  'New position updated [time]', 'New position added [time]', 'Stop timestamp',
                                  'Invest limit reached [time]', 'Max. daily loss reached [time]', 'liquidHours',
                                  'timeZoneId', 'local opening time', 'local closing time']

        # Define a list of column names to apply the conversion to float
        float_columns_to_convert = ['Entry price [$]', 'Stop price [$]', 'Buy limit price [$]',
                                    'Profit taker price [$]', 'Sell bellow SMA [$]', 'Spread at execution [%]',
                                    'Profit at x-R',
                                    'Last stop price', 'LAST price [$]', 'BID price [$]', 'ASK price [$]',
                                    'HIGH price [$]', 'LOW price [$]', 'CLOSE price [$]', 'Market sell price [$]']

        # Apply the bool lambda operation to each specified column
        for col in bool_columns_to_convert:
            io_list_clean[col] = io_list_clean[col].apply(lambda x: True if not pd.isnull(x) and x == 1.0 else False)

        # Apply the conversion to str type and clear contents for all but the first column
        for col in str_columns_to_convert:
            io_list_clean[col] = io_list_clean[col].astype(str)
            if col != 'Symbol':
                io_list_clean[col] = ""

        # Apply the conversion to float type
        io_list_clean[float_columns_to_convert] = io_list_clean[float_columns_to_convert].astype('float64')

        # Define a list of column names to apply the conversion to str
        tick_str_columns = ['timeStamp', 'Symbol']

        # Apply to conversion to str type and return both if needed
        if return_both_dataframes:
            for col in tick_str_columns:
                tick_data_clean[col] = tick_data_clean[col].astype(str)

            return io_list_clean, tick_data_clean

        else:
            return io_list_clean

    @staticmethod
    def document_trading_parameters(trading_plan, max_stock_spread, sell_half_reversal_rule, sell_full_reversal_rule,
                                    bad_close_rule, max_allowed_daily_pnl_loss, min_position_size):

        trading_plan.loc[0, 'MAX_STOCK_SPREAD'] = max_stock_spread
        trading_plan.loc[0, 'SELL_HALF_REVERSAL_RULE'] = sell_half_reversal_rule
        trading_plan.loc[0, 'SELL_FULL_REVERSAL_RULE'] = sell_full_reversal_rule
        trading_plan.loc[0, 'BAD_CLOSE_RULE'] = bad_close_rule
        trading_plan.loc[0, 'MAX_ALLOWED_DAILY_PNL_LOSS'] = max_allowed_daily_pnl_loss
        trading_plan.loc[0, 'MIN_POSITION_SIZE'] = min_position_size

        return trading_plan

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
    def compare_positions_currency_specific(open_positions, io_list):
        """
        Compares the sum of 'Quantity [#]' for each 'Symbol' in both open_positions and io_list DataFrames,
        specifically for the currency present in io_list (ignoring the first line). Checks if the quantities
        per Symbol in io_list cover the relevant quantities in open_positions for the given currency.

        Parameters:
        - open_positions (pd.DataFrame): DataFrame containing current open positions across various currencies.
        - io_list (pd.DataFrame): DataFrame containing positions in a single currency, excluding the first row.
        """
        # Exclude the first row from io_list
        io_list_filtered = io_list.iloc[1:]

        # Assuming all entries in io_list are in the same currency, determine that currency
        currency = io_list_filtered['Currency'].iloc[0]

        # Filter both DataFrames for the relevant currency
        open_positions_filtered = open_positions[open_positions['Currency'] == currency]
        io_list_filtered = io_list_filtered[io_list_filtered['Currency'] == currency]
        io_list_filtered = io_list_filtered[io_list_filtered['Open position'] == True]

        # Group by 'Symbol' and calculate the sum of 'Quantity [#]'
        open_positions_sum = open_positions_filtered.groupby('Symbol')['Quantity [#]'].sum()
        io_list_sum = io_list_filtered.groupby('Symbol')['Quantity [#]'].sum()

        # Compare the aggregated quantities
        if open_positions_sum.equals(io_list_sum):
            print("\nDailyTradingPlan matches current open portfolio positions for currency: " + currency)
        else:
            print("\n### ATTENTION ### DailyTradingPlan does not match current open portfolio positions for "
                  "currency: " + currency)
            print("\nOpen positions are:")
            print(open_positions_sum)
            print("\nOpen positions as per DailyTradingPlan are:")
            print(io_list_sum)

    @staticmethod
    def update_io_list_order_execution_status(status, order_id, last_fill_price, filled, remaining, io_list, timezone):

        # "Tries" need to find the relevant order_id to confirm the "Filled" status
        if status == "Filled" or ((status == "PreSubmitted" or status == "Submitted" or
                                   status == "PendingCancel" or status == "Cancelled") and filled > 0):

            try:
                index = io_list[io_list['parentOrderId'] == order_id].index.item()
                io_list.loc[index, 'Order filled'] = True
                io_list.loc[index, 'Entry price [$]'] = last_fill_price
                print("\nStock ID:", index, io_list['Symbol'][index], "buy order filled. (",
                      datetime.datetime.now().astimezone(pytz.timezone(timezone)).strftime("%H:%M:%S"), ")")
                if filled > 0:
                    io_list.loc[index, 'Quantity [#]'] = int(filled)

            except:
                pass

            try:
                index = io_list[io_list['profitOrderId'] == order_id].index.item()
                io_list.loc[index, 'Profit order filled'] = True
                io_list.loc[index, 'Profit taker price [$]'] = last_fill_price
                print("\nStock ID:", index, io_list['Symbol'][index], "profit order filled. (",
                      datetime.datetime.now().astimezone(pytz.timezone(timezone)).strftime("%H:%M:%S"), ")")
                if filled > 0:
                    # Uses "remaining" since I want to know the position remaining in my portfolio
                    io_list.loc[index, 'Quantity [#]'] = int(remaining)
                if remaining == 0:
                    io_list.loc[index, 'Stock sold'] = True
                    io_list.loc[index, 'Stock sold [time]'] = \
                        datetime.datetime.now().astimezone(pytz.timezone(timezone)).strftime("%H:%M:%S")
                    print("\nStock ID:", index, io_list['Symbol'][index], "completely sold. (",
                          datetime.datetime.now().astimezone(pytz.timezone(timezone)).strftime("%H:%M:%S"), ")")

            except:
                pass

            try:
                index = io_list[io_list['stopOrderId'] == order_id].index.item()
                io_list.loc[index, 'Stop order filled'] = True
                io_list.loc[index, 'Stop price [$]'] = last_fill_price
                print("\nStock ID:", index, io_list['Symbol'][index], "stop loss order filled. (",
                      datetime.datetime.now().astimezone(pytz.timezone(timezone)).strftime("%H:%M:%S"), ")")
                if filled > 0:
                    # Uses "remaining" since I want to know the position remaining in my portfolio
                    io_list.loc[index, 'Quantity [#]'] = int(remaining)
                if remaining == 0:
                    io_list.loc[index, 'Stock sold'] = True
                    io_list.loc[index, 'Stock sold [time]'] = \
                        datetime.datetime.now().astimezone(pytz.timezone(timezone)).strftime("%H:%M:%S")
                    print("\nStock ID:", index, io_list['Symbol'][index], "completely sold. (",
                          datetime.datetime.now().astimezone(pytz.timezone(timezone)).strftime("%H:%M:%S"), ")")

            except:
                pass

            try:
                index = io_list[io_list['sellOnCloseOrderId'] == order_id].index.item()
                io_list.loc[index, 'SOC order filled'] = True
                io_list.loc[index, 'Sell bellow SMA [$]'] = last_fill_price
                print("\nStock ID:", index, io_list['Symbol'][index], "SOC order filled. (",
                      datetime.datetime.now().astimezone(pytz.timezone(timezone)).strftime("%H:%M:%S"), ")")
                if filled > 0:
                    # Uses "remaining" since I want to know the position remaining in my portfolio
                    io_list.loc[index, 'Quantity [#]'] = int(remaining)
                if remaining == 0:
                    io_list.loc[index, 'Stock sold'] = True
                    io_list.loc[index, 'Stock sold [time]'] = \
                        datetime.datetime.now().astimezone(pytz.timezone(timezone)).strftime("%H:%M:%S")
                    print("\nStock ID:", index, io_list['Symbol'][index], "completely sold. (",
                          datetime.datetime.now().astimezone(pytz.timezone(timezone)).strftime("%H:%M:%S"), ")")

            except:
                pass

            try:
                index = io_list[io_list['marketOrderId'] == order_id].index.item()
                io_list.loc[index, 'Market order filled'] = True
                io_list.loc[index, 'Market sell price [$]'] = last_fill_price
                print("\nStock ID:", index, io_list['Symbol'][index], "Market order filled. (",
                      datetime.datetime.now().astimezone(pytz.timezone(timezone)).strftime("%H:%M:%S"), ")")

            except:
                pass

        return io_list

    @staticmethod
    def update_daily_pnl(portfolio_size, exr_rate, realized_pnl, realized_pnl_percent_last, unrealized_pnl,
                         unrealized_pnl_percent_last, max_allowed_daily_pnl_loss, max_daily_loss_reached, timezone,
                         portfolio_update_prints):

        # Starts the DailyPnL calculation
        if portfolio_size is not None:
            daily_pnl = (realized_pnl + unrealized_pnl) / exr_rate  # Only PnL figures come in local currency e.g. YEN
            daily_pnl_percent = daily_pnl / portfolio_size

            realized_pnl_percent = realized_pnl / portfolio_size * 100
            unrealized_pnl_percent = unrealized_pnl / portfolio_size * 100

            # Only updates if something has changed (beware the units)
            # Since default is 0 at program start, when I am 0% invested, nothing is printed
            if abs(realized_pnl_percent - realized_pnl_percent_last) > portfolio_update_prints or \
                    abs(unrealized_pnl_percent - unrealized_pnl_percent_last) > portfolio_update_prints:
                print("\nYour daily PnL (realized + unrealized) is now", round(daily_pnl_percent * 100, 2), "%. (",
                      datetime.datetime.now().astimezone(pytz.timezone(timezone)).strftime("%H:%M:%S"), ")")

                print("Realized:", round(realized_pnl_percent, 2), "%.   ")
                print("Unrealized:", round(unrealized_pnl_percent, 2), "%.")

                realized_pnl_percent_last = realized_pnl_percent
                unrealized_pnl_percent_last = unrealized_pnl_percent

            # Sets max_daily_loss_reached to True if more than 3% are lost which will stopp all new buying of stocks
            if max_daily_loss_reached == False and daily_pnl_percent <= max_allowed_daily_pnl_loss:
                max_daily_loss_reached = True
                print(f"\nDaily max. loss of {round(max_allowed_daily_pnl_loss * 100, 1)}% is reached. (",
                      datetime.datetime.now().astimezone(pytz.timezone(timezone)).strftime("%H:%M:%S"), ")")

        return max_daily_loss_reached, realized_pnl_percent_last, unrealized_pnl_percent_last

    @staticmethod
    def get_directory_path(directory_name):
        """
        Returns the absolute path to the specified directory relative to the script's parent directory.

        Parameters:
        - directory_name (str): Name of the directory ('Inputs' or 'Outputs').

        Returns:
        - Path object representing the directory path.

        Raises:
        - FileNotFoundError: If the specified directory does not exist.
        """
        try:
            # Get the absolute path to the current script (MyUtilities.py)
            script_path = Path(__file__).resolve()

            # Define the target directory relative to the script's parent directory
            target_dir = script_path.parent.parent / directory_name

            # Check if the target directory exists
            if not target_dir.exists():
                raise FileNotFoundError(f"{directory_name} directory does not exist: {target_dir}")

            return target_dir

        except Exception as e:
            print(f"Error in get_directory_path: {e}")
            raise

    @staticmethod
    def read_excel_inputs(filename, index_col=None):
        """
        Reads an Excel file from the Inputs directory into a pandas DataFrame.

        Parameters:
        - filename (str): Name of the Excel file to read.
        - index_col (int or str, optional): Column to set as the index of the DataFrame.

        Returns:
        - pandas.DataFrame: DataFrame containing the Excel data.
        - None: If reading the file fails.
        """
        try:
            # Get the Inputs directory path
            inputs_dir = MyUtilities.get_directory_path('Inputs')

            # Define the full path for the Excel file
            file_path = inputs_dir / filename

            # Check if the file exists
            if not file_path.exists():
                raise FileNotFoundError(f"Excel file not found: {file_path}")

            # Read the Excel file into a DataFrame
            df = pd.read_excel(file_path, index_col=index_col)

            return df

        except Exception as e:
            print(f"Failed to read Excel file '{filename}': {e}")
            return None

        except Exception as e:
            print(f"Failed to read Excel file: {e}")
            return None


    @staticmethod
    def save_excel_outputs(filename, pd_dataframe):
        """
        Saves a pandas DataFrame to an Excel file in the Outputs directory.

        Parameters:
        - filename (str): Name of the Excel file to save.
        - pd_dataframe (pandas.DataFrame): DataFrame to save to Excel.

        Returns:
        - None
        """
        try:
            # Get the Outputs directory path
            outputs_dir = MyUtilities.get_directory_path('Outputs')

            # Define the full path for the Excel file
            file_path = outputs_dir / filename

            # Save the DataFrame to the Excel file
            with pd.ExcelWriter(file_path) as writer:
                pd_dataframe.to_excel(writer, sheet_name="Sheet1", index=False)

            print(f"\nExcel output saved to {file_path}\n")

        except Exception as e:
            print(f"Failed to save Excel output '{filename}': {e}")

    @staticmethod
    def dailytradingplan_update(i, stop_loss_price, stock_quantity, name_of_dailytradingplan):
        """
        Updates the stop loss price in the DailyTradingPlan Excel file.

        Parameters:
        - i (int): The row index (0-based) to update.
        - stop_loss_price (float): The new stop loss price to set.
        - name_of_dailytradingplan (str): The filename of the DailyTradingPlan Excel file.

        Returns:
        - None
        """
        max_attempts = 3
        attempt = 0
        success_writing_xls = False

        while attempt < max_attempts and not success_writing_xls:
            try:
                # Get the Inputs directory path
                inputs_dir = MyUtilities.get_directory_path('Inputs')

                # Define the full path for the Excel file
                file_path = inputs_dir / name_of_dailytradingplan

                # Load the workbook
                workbook = load_workbook(filename=file_path)
                sheet = workbook.active

                # Determine the cell to update stop (e.g., "I3" if i=1)
                cell_name = f"I{i + 2}"  # Adjusting index for Excel row (assuming headers are in row 1)
                sheet[cell_name] = stop_loss_price

                # Determine the cell to update quantity (e.g., "I3" if i=1)
                cell_name = f"J{i + 2}"  # Adjusting index for Excel row (assuming headers are in row 1)
                sheet[cell_name] = stock_quantity

                # Save the workbook
                workbook.save(filename=file_path)
                success_writing_xls = True  # Update was successful, exit the loop
                print("DailyTradingPlan updated successfully.")

            except PermissionError as e:
                attempt += 1  # Increase the attempt counter
                time_now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"Attempt {attempt}: Did not get permission to write to {file_path}. "
                      f"Will try again in 20 secs. ({time_now_str})")
                print(f"Error details: {e}")
                if attempt < max_attempts:
                    time.sleep(20)  # Wait for 20 seconds before the next attempt

            except FileNotFoundError as e:
                # If the Inputs directory or Excel file is not found, log the error and exit
                print(f"FileNotFoundError: {e}")
                break

            except Exception as e:
                # Handle other exceptions
                print(f"An unexpected error occurred while updating '{name_of_dailytradingplan}': {e}")
                break

        if not success_writing_xls:
            # Final message if all attempts fail
            print("Failed to update DailyTradingPlan after 3 attempts - stop loss will change back to original value.")

    @staticmethod
    def find_earnings_dates(io_list, market_opening):

        set_of_stocks = set(io_list['Symbol'][1:])

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

            # Make the earnings_date aware by localizing it to the same TIMEZONE as reference_date
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
    def should_start_market_opening_function(io_list, time_delta_to_initialized_market):
        # Calculate the number of populated entries
        populated_entries = io_list['Company name'].apply(lambda x: x != "").sum()
        total_entries = len(io_list)

        # Check if the list is fully populated
        if time_delta_to_initialized_market.days > 10:
            if populated_entries == total_entries:
                return True

            # Check if the list is one entry away from being fully populated
            elif populated_entries == total_entries - 1:
                # Find the index of the remaining unpopulated entry
                unpopulated_index = io_list['Company name'].apply(lambda x: x == "").idxmax()

                # If the remaining entry is the one with req_id = 0
                if unpopulated_index == 0:
                    return True

        return False

    @staticmethod
    def append_fetch_data(tick_data, tick_data_open_position, tick_data_new_row, io_list_copy_for_tick_data, timezone):

        time_now_fetch = datetime.datetime.now().astimezone(pytz.timezone(timezone))
        time_now_fetch_str = time_now_fetch.strftime("%y%m%d %H:%M:%S")

        for i in range(len(io_list_copy_for_tick_data)):

            # Stocks meeting these criteria are skipped and shall only prevent the code from "falling asleep"
            if io_list_copy_for_tick_data['Entry price [$]'][i] == 9 and \
                    io_list_copy_for_tick_data['Stop price [$]'][i] == 11:
                continue

            # Only seeks to append data once per symbol for open position and once for new position in case
            if i > 0 and io_list_copy_for_tick_data['Symbol'][i] == io_list_copy_for_tick_data['Symbol'][i - 1] and \
                    (io_list_copy_for_tick_data['Open position'][i] == io_list_copy_for_tick_data['Open position'][i - 1] or
                     (
                             not io_list_copy_for_tick_data['Open position'][i] and
                             not io_list_copy_for_tick_data['Open position'][i - 1]
                     )
                    ):
                pass
            else:
                # Fills row to append in pd dataframe
                tick_data_new_row.loc[0, 'timeStamp'] = time_now_fetch_str
                tick_data_new_row.loc[0, 'Symbol'] = io_list_copy_for_tick_data['Symbol'][i]
                tick_data_new_row.loc[0, 'CLOSE price [$]'] = io_list_copy_for_tick_data['CLOSE price [$]'][i]
                tick_data_new_row.loc[0, 'BID price [$]'] = io_list_copy_for_tick_data['BID price [$]'][i]
                tick_data_new_row.loc[0, 'ASK price [$]'] = io_list_copy_for_tick_data['ASK price [$]'][i]
                tick_data_new_row.loc[0, 'LAST price [$]'] = io_list_copy_for_tick_data['LAST price [$]'][i]
                tick_data_new_row.loc[0, 'ASK size'] = io_list_copy_for_tick_data['ASK size'][i]
                tick_data_new_row.loc[0, 'BID size'] = io_list_copy_for_tick_data['BID size'][i]
                tick_data_new_row.loc[0, 'Volume'] = io_list_copy_for_tick_data['Volume'][i]

                if not io_list_copy_for_tick_data['Open position'][i]:
                    # Appends row to tick_data
                    tick_data = pd.concat([tick_data, tick_data_new_row], ignore_index=True)

                else:
                    # Appends row to tick_data_open_position
                    tick_data_open_position = pd.concat([tick_data_open_position, tick_data_new_row],
                                                        ignore_index=True)

        return tick_data, tick_data_open_position
