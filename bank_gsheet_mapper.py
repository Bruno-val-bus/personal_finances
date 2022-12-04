import csv
import gspread
from gspread_formatting import *
from request_handler import RequestHandler

class Mapper:
    """

    """
    latest_csv_path = "C:\\Users\\bruno\\Documents\\Python Projects v2\\personal_finances\\bank_csvs\\" # Umsaetze_KtoNr175014000_EUR_04-09-2022_1557.CSV
    latest_paypal_csv_path = "C:\\Users\\bruno\\Documents\\Python Projects v2\\personal_finances\\bank_csvs\\" # D4ELEMZ9DJQR6-MSR-20220701000000-20220731235959.CSV
    read_paypal_csv = True
    read_bank_csv = True
    total_paypal_gains = 0.0
    total_paypal_losses = 0.0
    transferred_expenses = []
    recurrent_expense_identifiers = ["IGNORE", "MIETE", "Spotify", "Scribd", "AUDIBLE GMBH", "ANLAGE", "WACHSTUMS-SPAREN",
                                     "Virtus Jiu-Jitsu", "Allgemeine WÃ¤hrungsumrechnung"]
    transferred_files_paths = []
    expenses2add = {}
    transaction_value_column = 3
    transaction_description_column = 4
    transaction_category_column = 5

    fmt = CellFormat(backgroundColor=Color(1, 1, 0))  # set it to yellow
    # red: (1,0,0), white: (1,1,1)
    row = 3

    def __init__(self):
        self.__folder_id_year = "1gfvN1cVxjTIWJAYlXjI46MB-oqYkKkyo"
        self.__request_handler = RequestHandler()

    def __read_csvs(self):
        """
        creates list of expenses that haven't been added to worksheet
        Paypal expenses are added independently from entries in bank csv because the entry for the expense in the bank csv and in the PayPal csv might not be the same becasue of paypal income money. The income gains are thus also considered separately and added to income in gsheet
        :return:
        """
        self.__read_paypal_csv()
        self.__read_bank_csv()

    def __read_paypal_csv(self):
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
                # verify if expense is recurrent or if it has already been transfered to gsheet
                if self.__expense_is_recurrent(description, additional_info) or ("PayPal: " + description) in self.transferred_expenses:
                    continue
                transaction = row[5]
                # verify if transaction is expense or gain
                if "-" in transaction:
                    # transaction is expense
                    expense_sum_as_float = float(transaction.replace("-", "").replace(",", "."))
                    column_index_expense_splitwise = "n"  # not for splitwise as default
                    description = "PayPal: " + description
                    self.expenses2add.update({description: [expense_sum_as_float, "Otros",
                                                       column_index_expense_splitwise]})  # todo differentiate category

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
                    self.total_paypal_gains += gain
                else:
                    # transaction is loss
                    loss = float(transaction.replace("-", "").replace(",", "."))
                    self.total_paypal_losses += loss

    def __read_bank_csv(self):
        # do not read if not wanted by user
        if self.read_bank_csv is False:
            return
        with open(self.latest_csv_path, mode='r') as csv_file:
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
                if "-" in expense_sum and description not in self.transferred_expenses:
                    if "PayPal" in description:
                        # paypal expenses have already been added in previous csv reading
                        continue
                    # verify if expense is recurrent
                    if self.__expense_is_recurrent(description): continue
                    expense_sum_as_float = float(expense_sum.replace("-", "").replace(",", "."))
                    self.expenses2add.update(
                        {description: [expense_sum_as_float, expense_category, column_index_expense]})

    def __create_expenses2exclude(self, transactions_sheet):
        """
        creates list of expenses that have already been added to gsheet
        :param transactions_sheet:
        :return:
        """
        for row_index in range(5, transactions_sheet.row_count + 1):
            transaction_description = transactions_sheet.cell(str(row_index), str(self.transaction_description_column)).value
            if transaction_description is not None:
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

        month_spanish = input("Enter month:")#"Agosto"
        bank_csv_file = input("Enter name of bank file or press ENTER:")
        paypal_csv_file = input("Enter name of paypal file or press ENTER:")
        if paypal_csv_file == "":
            self.read_paypal_csv = False
        if bank_csv_file == "":
            self.read_bank_csv = False
        if self.read_bank_csv is False and self.read_paypal_csv is False:
            print("No data to be mapped to Google Sheet")
            return
        self.latest_csv_path = self.latest_csv_path + bank_csv_file + ".CSV"
        self.latest_paypal_csv_path = self.latest_paypal_csv_path + paypal_csv_file + ".CSV"
        # json file with account mail in C:\Users\bruno\AppData\Roaming\gspread s. https://console.cloud.google.com/iam-admin/serviceaccounts/details/102353359672448200928;edit=true/metrics?project=personal-projects-360115
        client = gspread.service_account()
        workbook = client.open(month_spanish, folder_id=self.__folder_id_year)
        transactions_sheet = workbook.get_worksheet(1)
        self.__create_expenses2exclude(transactions_sheet)
        self.__read_csvs()
        # last_cell.update_cell(row,column, numeric_value/string_value)
        for row_index in range(5, transactions_sheet.row_count + 1):
            if len(self.expenses2add) == 0:
                break
            transaction_value = transactions_sheet.cell(str(row_index), str(self.transaction_value_column)).value
            if transaction_value is not None:
                continue  # if value is found in cell go to next free cell
            # get expense information
            description2add = list(self.expenses2add)[0]
            value2add = self.expenses2add.get(description2add)[0]
            category2add = self.expenses2add.get(description2add)[1]
            splitwise_expense = self.expenses2add.get(description2add)[2]
            # if is splitwise expense change cell colour
            if splitwise_expense == "y":
                cell_address = transactions_sheet.cell(str(row_index), str(self.transaction_value_column)).address
                format_cell_range(transactions_sheet, cell_address, self.fmt)
            # update cells
            transactions_sheet.update_cell(row_index, self.transaction_description_column, description2add)
            transactions_sheet.update_cell(row_index, self.transaction_value_column, value2add)
            transactions_sheet.update_cell(row_index, self.transaction_category_column, category2add)
            # remove added item
            self.expenses2add.pop(description2add)

        # add gains from paypal
        transactions_sheet.update_cell(5, 8, self.total_paypal_gains - self.total_paypal_losses)
        transactions_sheet.update_cell(5, 9, "PayPal gains")
        transactions_sheet.update_cell(5, 10, "Otros")

if __name__ == "__main__":
    mapper = Mapper()
    mapper.write2gsheet()