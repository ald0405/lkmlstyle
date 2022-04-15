from lkmlstyle.rules import ALL_RULES
import yaml

yamls = []
for rule in ALL_RULES:
    try:
        yaml.safe_dump(rule.__dict__(), allow_unicode=True)
    except Exception as e:
        print(e)
        print(rule.__dict__(), end="\n\n")
    else:
        yamls.append(rule)

with open("rules.yaml", "w+") as file:
    yaml.safe_dump(
        {"rules": [r.__dict__() for r in yamls]},
        file,
        allow_unicode=True,
        sort_keys=False,
    )
