from configparser import ConfigParser
import os
# Load the configuration file

config = ConfigParser(allow_no_value=True)
file_directory_path = os.path.dirname(__file__)
config.read(os.path.join(file_directory_path, "config.ini"))