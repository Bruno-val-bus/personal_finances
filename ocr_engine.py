import requests
import json
import os
from typing import List, Dict

from splitwise.user import ExpenseUser
from splitwise import Splitwise, Group, Expense

from ocr.enumerations import ReceiptItems, ExceptionsItemIDs, PayloadResults, FileExtensions
from ocr.db import db_transactions
from ocr.config_loader import config


class ReceiptParser:

    def __init__(self):
        self.splitwise_description: str = None
        self.splitwise_amount: float = None
        self._json_response_path: str = None
        self.receipt_total_expense: float = 0.0
        self.amount_unshared_items: float = 0.0

    def set_json_response_path(self, json_response_path: str):
        self._json_response_path = json_response_path

    def _calculate_expenses(self, bought_items: List[Dict]):
        for item in bought_items:
            description = item.get(ReceiptItems.DESCRIPTION)
            amount = float(item.get(ReceiptItems.AMOUNT))
            if ExceptionsItemIDs.YFOOD in description or \
                    ExceptionsItemIDs.CRAZY_COCONUT in description \
                    or ExceptionsItemIDs.COLD_BREW in description:
                # add amount of item not to be shared to amount to subtract
                self.amount_unshared_items = self.amount_unshared_items + amount
            # add to total expense amount
        start_idx = len(bought_items) - 1
        stop_idx = -1
        step = -1
        for idx in range(start_idx, stop_idx, step):
            description = bought_items[idx].get(ReceiptItems.DESCRIPTION)
            amount = bought_items[idx].get(ReceiptItems.AMOUNT)
            if ExceptionsItemIDs.SUMME in description or ExceptionsItemIDs.EUR in description:
                # if total expense identifier is in description, override current sum and return
                self.receipt_total_expense = amount
                return

    def parse_receipt(self):
        with open(self._json_response_path, "r") as f:
            data = json.load(f)
            receipt_content: Dict = data[PayloadResults.RECEIPTS][0]
            items: List[Dict] = receipt_content.get('items')
            date: str = receipt_content.get('date')
            super_market: str = receipt_content.get('merchant_name')
            self.splitwise_description = f"{date}: {super_market}"
            self._calculate_expenses(items)
            self.splitwise_amount = self.receipt_total_expense - self.amount_unshared_items
            print(f"TOTAL: {str(self.receipt_total_expense)}")
            print(f"SPLITWISE: {str(self.splitwise_amount)}")


class OCRRequestSender:

    def __init__(self):
        self._res: requests.Response = None
        receipts_folder = PayloadResults.RECEIPTS
        self._receipts_folder_path = os.path.join(os.getcwd(), receipts_folder)
        self.url = "https://ocr.asprise.com/api/v1/receipt"  # Probably accepting only 5 requests per day. S. alternative (Mindee): https://stackoverflow.com/questions/72509413/how-do-i-use-mindee-api-with-python3
        self._splitwiseAPI: SplitwiseAPI = SplitwiseAPI()

    def _send_request(self, image_path: str):
        self._res = requests.post(self.url,
                                  data={
                                      "api_key": "TEST",
                                      "recognizer": "auto",
                                      "ref_no": "oct_python_123"
                                  },
                                  files={
                                      "file": open(image_path, "rb"),
                                  }
                                  )

    def _save_response(self, json_response_path: str):
        with open(json_response_path, "w") as f:
            response_loaded = json.loads(self._res.text)
            json.dump(response_loaded, f)

    def scan_directory(self):
        directory = os.fsencode(self._receipts_folder_path)
        for file in os.listdir(directory):
            filename = os.fsdecode(file)
            if filename in db_transactions.get_receipts_added2splitwise(col_name=db_transactions.FILE_NAME):
                continue
            if not filename.endswith(FileExtensions.JSON):
                # file is image
                json_response_path = os.path.join(self._receipts_folder_path, filename + FileExtensions.JSON)
                receipt_parser = ReceiptParser()
                receipt_parser.set_json_response_path(json_response_path)
                if not os.path.exists(json_response_path):
                    # if corresponding json file does not exist send request to ocr engine and save it
                    self._send_request(
                        image_path=os.path.join(self._receipts_folder_path, filename)
                    )
                    self._save_response(
                        json_response_path=json_response_path
                    )
                # TODO verify self._res.text to see if the return content is actually the parsed receipt or if the day limit has been reached
                ocr_parsed = True
                # when response is saved or if it already exists, parse receipt
                receipt_parser.parse_receipt()
                # TODO: maybe more robust if you check if the receipt_parser.splitwise_description has already been added to splitwise to account for adding a new image that has already been parsed:
                #   add column to existing table and retrieve the splitwise_description's using db_transactions.get_receipts_added2splitwise(col_name=db_transactions.ADDED2SPLITWISE)
                errors = self._splitwiseAPI.add_expense(amount_shared=receipt_parser.splitwise_amount,
                                                        expense_description=receipt_parser.splitwise_description)
                if errors is None:
                    # if no error with expense creation, tag receipt image or track via sql database
                    db_transactions.insert_receipt(file_name=filename, added2splitwise=True, ocr_parsed=ocr_parsed)
                else:
                    # TODO log error in sql
                    db_transactions.insert_receipt(file_name=filename, added2splitwise=False, ocr_parsed=ocr_parsed)


class SplitwiseAPI:

    def __init__(self):
        self._splitwiseObj = Splitwise(
            consumer_key=config.get("SPLITWISE", 'SPLITWISE_API_KEY'),
            consumer_secret=config.get("SPLITWISE", 'SPLITWISE_API_SECRET'),
            api_key=config.get("SPLITWISE", 'SPLITWISE_API_KEY_OAUTH20')
        )
        self._groupID = 18955015
        group: Group = self._splitwiseObj.getGroup(id=self._groupID)
        self._alex_user_id = group.getMembers()[1].id
        self._bruno_user_id = group.getMembers()[0].id
        self._alex = ExpenseUser()
        self._alex.setId(self._alex_user_id)
        self._bruno = ExpenseUser()
        self._bruno.setId(self._bruno_user_id)

    def add_expense(self, amount_shared: float, expense_description: str):
        expense: Expense = Expense()
        owed_shared = round(amount_shared / 2, 2)
        amount_shared = owed_shared * 2
        expense.setCost(str(amount_shared))
        expense.setDescription(expense_description)
        expense.setGroupId(self._groupID)
        self._bruno.setPaidShare(str(amount_shared))
        self._bruno.setOwedShare(str(owed_shared))
        self._alex.setPaidShare('0.00')
        self._alex.setOwedShare(str(owed_shared))
        expense.addUser(self._bruno)
        expense.addUser(self._alex)
        expense.setSplitEqually(True)
        expense, errors = self._splitwiseObj.createExpense(expense)
        return errors


OCRRequestSender().scan_directory()
# TODO download drive images to folder (https://stackoverflow.com/questions/38511444/python-download-files-from-google-drive-using-url && https://iq.opengenus.org/google-drive-file-download-upload/)
# host in replit https://www.youtube.com/watch?v=D7OWuslFYCw
