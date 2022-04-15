class LkmlstyleException(Exception):
    code: int = NotImplemented


class InvalidRule(LkmlstyleException, TypeError):
    code = 110


class InvalidConfig(LkmlstyleException):
    code = 111


class InvalidRuleCode(LkmlstyleException):
    code = 112
