import csv
import gspread
from gspread_formatting import *
from request_handler import RequestHandler
import os


class Mapper:
    """

    """

    def __init__(self):
        self.__csv_identifier: str = ".CSV"
        self.__main_url_folder: str = "https://drive.google.com/drive/folders/"
        self.__folder_id_year: str = None
        self.__request_handler = RequestHandler()
        self.latest_bank_csv_path: str = None
        self.latest_paypal_csv_path: str = None
        self.csvs_path: str = os.path.join(os.getcwd(), "bank_csvs")
        self.read_paypal_csv: bool = True
        self.read_bank_csv: bool = True
        self.__paypal_surplus: float
        self.recurrent_expense_identifiers = ["IGNORE", "IGNORAR", "MIETE", "Spotify", "Scribd", "AUDIBLE GMBH",
                                              "ANLAGE",
                                              "WACHSTUMS-SPAREN",
                                              "Virtus Jiu-Jitsu", "Allgemeine WÃ¤hrungsumrechnung"]
        self.transaction_value_column: int = 3
        self.transaction_description_column: int = 4
        self.transaction_category_column: int = 5
        self.fmt: CellFormat = CellFormat(backgroundColor=Color(1, 1, 0))  # set it to yellow -> red: (1,0,0), white: (1,1,1)
        self.transferred_expenses = []
        self.expenses2add = {}

    def __read_csvs(self):
        """
        creates list of expenses that haven't been added to worksheet
        Paypal expenses are added independently of entries in bank csv because the entry for the expense in the bank csv and in the PayPal csv might not be the same becasue of paypal income money. The income gains are thus also considered separately and added to income in gsheet
        :return:
        """
        self.__read_paypal_csv()
        self.__read_bank_csv()

    def __read_paypal_csv(self):
        """
        Read expenses to add to google sheet and saves them in 'expenses2add'.
        At the same time it calculates the total gains (equivalent to taking from bank account) and losses (equivalent to paying to a provider).
        :return:
        """
        # do not read if not wanted by user
        if self.read_paypal_csv is False:
            return
        # get expenses
        with open(self.latest_paypal_csv_path, mode='r') as csv_file_paypal:
            csv_reader_paypal = csv.reader(csv_file_paypal, delimiter=',')
            for row in csv_reader_paypal:
                if csv_reader_paypal.line_num == 1: continue
                # fetch description to track recurrent or already written expenses
                description = row[11]
                # fetch additional info
                additional_info = row[3]
                transaction = row[5]
                # verify if transaction is expense or gain
                if "-" in transaction:
                    # verify if expense is recurrent or if it has already been transferred to gsheet
                    if self.__expense_is_recurrent(description, additional_info) or (
                            "PayPal: " + description) in self.transferred_expenses:  # TODO make verification in transferred expenses based on value AND description
                        continue
                    # transaction is expense
                    expense_sum_as_float = float(transaction.replace("-", "").replace(",", "."))
                    column_index_expense_splitwise = "n"  # not for splitwise as default
                    description = "PayPal: " + description
                    self.expenses2add.update({description: [expense_sum_as_float, "Otros",
                                                            column_index_expense_splitwise]})
        total_paypal_gains = 0.0
        total_paypal_losses = 0.0
        with open(self.latest_paypal_csv_path, mode='r') as csv_file_paypal:
            csv_reader_paypal = csv.reader(csv_file_paypal, delimiter=',')
            # get total gains and losses
            for row in csv_reader_paypal:
                if csv_reader_paypal.line_num == 1: continue
                # fetch description to track recurrent or already written expenses
                transaction = row[5]
                # verify if transaction is expense or gain
                if "-" not in transaction:
                    # transaction is gain
                    gain = float(transaction.replace(",", "."))
                    total_paypal_gains += gain
                else:
                    # transaction is loss
                    loss = float(transaction.replace("-", "").replace(",", "."))
                    total_paypal_losses += loss

        self.__paypal_surplus = total_paypal_gains - total_paypal_losses

    def __read_bank_csv(self):
        # do not read if not wanted by user
        if self.read_bank_csv is False:
            return
        with open(self.latest_bank_csv_path, mode='r') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=';')
            row_count = 0
            paypal_expense_index = 0
            column_index_description = 3
            column_index_expense_sum = 4
            column_index_expense_cat = 9
            column_index_expense_splitwise = 10
            for row in csv_reader:
                row_count += 1
                description = row[column_index_description]
                expense_sum = row[column_index_expense_sum]
                expense_category = row[column_index_expense_cat]
                column_index_expense = row[column_index_expense_splitwise]
                # only add if it is a negative sum (expense)
                # verify if expense has already been transferred to gsheet
                if "-" in expense_sum and description not in self.transferred_expenses:  # TODO make verification in transferred expenses based on value AND description
                    if "PayPal" in description:
                        # PayPal's expenses have already been added in previous csv reading
                        continue
                    # verify if expense is recurrent
                    if self.__expense_is_recurrent(description): continue
                    expense_sum_as_float = float(expense_sum.replace("-", "").replace(",", "."))
                    self.expenses2add.update(
                        {description: [expense_sum_as_float, expense_category, column_index_expense]})

    def __read_transferred_expenses(self, transactions_sheet):
        """
        creates list of expenses that have already been added to gsheet
        :param transactions_sheet:
        :return:
        """
        print("Reading expenses to exclude from Google Sheets.")
        transaction_description_empty_rows = 0
        for row_index in range(5, transactions_sheet.row_count + 1):
            if transaction_description_empty_rows > 2:
                break
            transaction_description = self.__request_handler.get_request(row_index, self.transaction_description_column,
                                                                         transactions_sheet)
            if transaction_description is None or transaction_description == "":
                # increase 'transaction_description_empty_rows' count and continue
                transaction_description_empty_rows += 1
                continue
            else:
                # reset 'transaction_description_empty_rows' count
                transaction_description_empty_rows = 0
            self.transferred_expenses.append(transaction_description)

    def __expense_is_recurrent(self, *descriptions):
        for description in descriptions:
            for identifier in self.recurrent_expense_identifiers:
                if identifier in description:
                    return True
        return False

    def write2gsheet(self):
        """
        Folder in Google Drive has to be shared with email found in json file
        :return:
        """
        drive_url_folder = input("Enter drive url of folder")
        self.__folder_id_year = drive_url_folder.replace(self.__main_url_folder,
                                                         "")  # 2022 Folder  https://drive.google.com/drive/folders/1gfvN1cVxjTIWJAYlXjI46MB-oqYkKkyo
        month_spanish = input("Enter month in spanish:")
        bank_csv_file = input("Enter name of bank file or press ENTER:")
        paypal_csv_file = input("Enter name of paypal file or press ENTER:")
        if paypal_csv_file == "":
            self.read_paypal_csv = False
        if bank_csv_file == "":
            self.read_bank_csv = False
        if self.read_bank_csv is False and self.read_paypal_csv is False:
            print("No data to be mapped to Google Sheet")
            return
        self.latest_bank_csv_path = self.csvs_path + bank_csv_file + self.__csv_identifier
        self.latest_paypal_csv_path = self.csvs_path + paypal_csv_file + self.__csv_identifier
        # json file with account mail in C:\Users\bruno\AppData\Roaming\gspread s. https://console.cloud.google.com/iam-admin/serviceaccounts/details/102353359672448200928;edit=true/metrics?project=personal-projects-360115
        client = gspread.service_account()
        workbook = client.open(month_spanish, folder_id=self.__folder_id_year)
        transactions_sheet = workbook.get_worksheet(1)
        self.__read_transferred_expenses(transactions_sheet)
        print("Reading CSVs")
        self.__read_csvs()
        print("Writing to Google Sheet")
        for row_index in range(5, transactions_sheet.row_count + 1):
            if len(self.expenses2add) == 0:
                break
            transaction_value = self.__request_handler.get_request(row_index, self.transaction_value_column,
                                                                   transactions_sheet)
            if transaction_value is not None:
                continue  # if value is found in cell go to next free cell
            # get expense information
            description2add = list(self.expenses2add)[0]
            value2add = self.expenses2add.get(description2add)[0]
            category2add = self.expenses2add.get(description2add)[1]
            splitwise_expense = self.expenses2add.get(description2add)[2]
            # if is splitwise expense change cell colour
            if splitwise_expense == "y":
                # TODO create method for request handler to request address
                cell_address = transactions_sheet.cell(str(row_index), str(self.transaction_value_column)).address
                format_cell_range(transactions_sheet, cell_address, self.fmt)
            # update cells
            self.__request_handler.update_request(row_index, self.transaction_description_column, transactions_sheet,
                                                  description2add)
            self.__request_handler.update_request(row_index, self.transaction_value_column, transactions_sheet,
                                                  value2add)
            self.__request_handler.update_request(row_index, self.transaction_category_column, transactions_sheet,
                                                  category2add)
            # remove added item
            self.expenses2add.pop(description2add)

        # add gains from paypal
        gains_first_row = 5
        self.__request_handler.update_request(row_idx=gains_first_row, col_idx=8, ws=transactions_sheet,
                                              new_value=self.__paypal_surplus)
        self.__request_handler.update_request(row_idx=gains_first_row, col_idx=9, ws=transactions_sheet,
                                              new_value="PayPal gains")
        self.__request_handler.update_request(row_idx=gains_first_row, col_idx=10, ws=transactions_sheet,
                                              new_value="Otros")


if __name__ == "__main__":
    mapper = Mapper()
    mapper.write2gsheet()
