import requests
import json
import os
from typing import List, Dict
from enumerations import ReceiptItems, UnsharedItemIDs


def get_expense_total(bought_items: List[Dict]):
    total: float = 0.0
    for item in bought_items:
        description = item.get(ReceiptItems.DESCRIPTION)
        amount = item.get(ReceiptItems.AMOUNT)
        if UnsharedItemIDs.YFOOD not in description and \
                UnsharedItemIDs.CRAZY_COCONUT not in description \
                and UnsharedItemIDs.COLD_BREW not in description\
                and UnsharedItemIDs.SUMME not in description:
            total = total + float(amount)


image = "IMG_0163.jpg"
RECEIPTS = "receipts"
receipts_folder = os.path.join(os.getcwd(), RECEIPTS)
image_path = os.path.join(receipts_folder, image)
json_response_path = os.path.join(os.getcwd(), RECEIPTS, image + ".json")
url = "https://ocr.asprise.com/api/v1/receipt" # Probably accepting only 5 requests per day. S. alternative (Mindee): https://stackoverflow.com/questions/72509413/how-do-i-use-mindee-api-with-python3

res = requests.post(url,
                    data={
                        "api_key": "TEST",
                        "recognizer": "auto",
                        "ref_no": "oct_python_123"
                    },
                    files={
                        "file": open(image_path, "rb"),
                    }
                    )

with open(json_response_path, "w") as f:
    response_loaded = json.loads(res.text)
    json.dump(response_loaded, f)

with open(json_response_path, "r") as f:
    data = json.load(f)
    receipt_content = data[RECEIPTS][0]
    items = receipt_content.get('items')
    # TODO if receipt_content.get("total") is None just substract unshareable items
    get_expense_total(items)
