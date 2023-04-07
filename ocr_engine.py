from mindee import Client, documents
from mindee.client import DocumentClient
from mindee.response import PredictResponse
import requests
import json
import os
from typing import List, Dict
import datetime
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


class ReceiptParserMindee(ReceiptParser):
    def __init__(self):
        super(ReceiptParserMindee, self).__init__()

    def extract_expenses_data(self, api_response: PredictResponse) -> None:
        date = api_response.document.date.value
        time = api_response.document.time.value
        amount = api_response.document.total_incl.value
        merchant = api_response.document.merchant_name
        self.splitwise_description = f"{date} at {time}:{merchant}"
        self.splitwise_amount = float(amount)


class OCRRequestSender:

    def __init__(self):
        self._res: requests.Response = None
        receipts_folder = PayloadResults.RECEIPTS
        self.receipts_folder_path = os.path.join(os.getcwd(), receipts_folder)
        self._url = "https://ocr.asprise.com/api/v1/receipt"  # Probably accepting only 5 requests per day. S. alternative (Mindee): https://stackoverflow.com/questions/72509413/how-do-i-use-mindee-api-with-python3
        self.splitwiseAPI: SplitwiseAPI = SplitwiseAPI()

    def _send_request(self, image_path: str):
        self._res = requests.post(self._url,
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

    def add_expense(self, amount_shared: float, expense_description: str, receipt_path: str = None):
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
        if receipt_path is not None:
            # FIXME currently returning SplitwiseBadRequestException
            expense.setReceipt(receipt_path)
        expense.setSplitEqually(True)
        expense, errors = self._splitwiseObj.createExpense(expense)
        return errors


class OCRAPI(OCRRequestSender):
    def __init__(self):
        super(OCRAPI, self).__init__()
        # Init a new client
        self._mindee_client: Client = Client(api_key=config.get("OCR_ENGINE", 'MINDEE_API_KEY'))
        self._input_doc: DocumentClient = None
        self._api_response: PredictResponse = None

    def scan_directory(self):
        directory = os.fsencode(self.receipts_folder_path)
        partially_shared: bool
        for file in os.listdir(directory):
            filename = os.fsdecode(file)
            ocr_parsed: bool = False
            if filename.endswith(FileExtensions.JSON) or filename in db_transactions.get_receipts_added2splitwise(
                    col_name=db_transactions.FILE_NAME) or FileExtensions.DRIVE_DOWNLOAD_DENOMINATOR in filename \
                    or FileExtensions.DRIVE_UPLOAD_DENOMINATOR in filename:
                # file is json or filename has already been added to splitwise got o next file
                continue
            # file is image
            json_response_path = os.path.join(self.receipts_folder_path, filename + FileExtensions.JSON)
            image_path = os.path.join(self.receipts_folder_path, filename)
            if FileExtensions.PARTIAL_DENOMINATOR not in filename:
                # use mindee parser class
                receipt_parser = ReceiptParserMindee()
                # expense is not partially shared
                partially_shared = False
                # Load a file from disk
                self._input_doc = self._mindee_client.doc_from_path(image_path)
                # Parse the document by passing the appropriate type
                self._api_response = self._input_doc.parse(documents.TypeReceiptV3)
                # TODO verify self._api_response to see if the return content is actually the parsed receipt or if the monthly limit has been reached
                # when response is saved or if it already exists, parse receipt
                receipt_parser.extract_expenses_data(self._api_response)
                ocr_parsed = True
            else:
                # use json parser class and set json path
                receipt_parser = ReceiptParser()
                receipt_parser.set_json_response_path(json_response_path)
                # expense is partially shared, thus the individual expenses that are not sharable have to be subtracted
                partially_shared = True
                if not os.path.exists(json_response_path):
                    # if corresponding json file does not exist send request to ocr engine and save it
                    self._send_request(
                        image_path=image_path
                    )
                    self._save_response(
                        json_response_path=json_response_path
                    )
                    # TODO verify self._res.text to see if the return content is actually the parsed receipt or if the day limit has been reached, then delete json file
                receipt_parser.parse_receipt()
                ocr_parsed = True
            # check if the splitwise_description_unique has already been added to splitwise to account for adding a new image that has already been parsed
            splitwise_description_unique = receipt_parser.splitwise_description + f"    {str(receipt_parser.splitwise_amount)}€"
            if splitwise_description_unique not in db_transactions.get_receipts_added2splitwise(
                    col_name=db_transactions.SPLITWISE_DESCRIPTION):
                # if not yet added to splitwise based on description, add expense via Splitwise API
                errors = self.splitwiseAPI.add_expense(amount_shared=receipt_parser.splitwise_amount,
                                                       expense_description=splitwise_description_unique)
            else:
                continue
            if errors is None:
                # if no error with expense creation, tag receipt image or track via sql database
                db_transactions.insert_receipt(file_name=filename, added2splitwise=True, ocr_parsed=ocr_parsed,
                                               splitwiseAPI_error="", partially_shared=partially_shared,
                                               splitwise_description=splitwise_description_unique)
            else:
                # log error in sql
                error_txt: str = errors.errors.get("base")[0]
                db_transactions.insert_receipt(file_name=filename, added2splitwise=False, ocr_parsed=ocr_parsed,
                                               splitwiseAPI_error=error_txt, partially_shared=partially_shared,
                                               splitwise_description=splitwise_description_unique)


OCRAPI().scan_directory()
# TODO download drive images to folder (https://stackoverflow.com/questions/38511444/python-download-files-from-google-drive-using-url && https://iq.opengenus.org/google-drive-file-download-upload/)
# host in replit https://www.youtube.com/watch?v=D7OWuslFYCw
