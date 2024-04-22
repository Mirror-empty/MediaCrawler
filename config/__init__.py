from .base_config import *
from .db_config import *

class ConfigParams:
    def __init__(self, platform, lt, type, start, keywords, accounts):
        self.platform = platform
        self.lt = lt
        self.type = type
        self.start = start
        self.keywords = keywords
        self.accounts = accounts

    def to_dict(self):
        return {
            "platform": self.platform,
            "lt": self.lt,
            "type": self.type,
            "start": self.start,
            "keywords": self.keywords,
            "accounts": self.accounts,
        }