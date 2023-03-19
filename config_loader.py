from configparser import ConfigParser

# Load the configuration file

config = ConfigParser(allow_no_value=True)
config.read("config.ini")