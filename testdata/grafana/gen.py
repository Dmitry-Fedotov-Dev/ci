import json, sys
json.dump({"title": "selftest", "panels": []}, open(sys.argv[1], "w"), indent=1)
