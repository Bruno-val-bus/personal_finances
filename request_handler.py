import time as time
from gspread.worksheet import Worksheet
from gspread.exceptions import APIError

class RequestHandler():

    def __init__(self):
        self.__time_increase_factor = 1.1

    def get_request(self, row_idx: int, col_idx: int, ws: Worksheet, sleep_time=0.0) -> str:
        start_req = time.perf_counter()
        try:
            time.sleep(sleep_time)
            request_result = ws.cell(row_idx, col_idx).value
            print(self.__no_request_error_msg(sleep_time=sleep_time))
            return request_result
        except APIError:
            end_req = time.perf_counter()
            elapsed_time = end_req - start_req
            print(self.__request_error_msg(increased_time=elapsed_time * 1.1))
            self.get_request(row_idx=row_idx, col_idx=col_idx, ws=ws, sleep_time=elapsed_time * self.__time_increase_factor)

    def update_request(self, row_idx: int, col_idx: int, ws: Worksheet, new_value: any, sleep_time=0.0) -> None:
        start_req = time.perf_counter()
        try:
            time.sleep(sleep_time)
            ws.update_cell(row_idx, col_idx, new_value)
            print(self.__no_request_error_msg(sleep_time=sleep_time))
        except APIError:
            end_req = time.perf_counter()
            elapsed_time = end_req - start_req
            print(self.__request_error_msg(increased_time=elapsed_time * self.__time_increase_factor))
            self.update_request(row_idx=row_idx, col_idx=col_idx, ws=ws, new_value=new_value, sleep_time=elapsed_time * 1.1)

    @staticmethod
    def __request_error_msg(increased_time: float) -> str:
        return f"Request error. Sleep time increased to: {str(increased_time)}s"

    @staticmethod
    def __no_request_error_msg(sleep_time: float) -> str:
        return f"No request error using sleep time: {str(sleep_time)}s"