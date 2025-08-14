import os
from autotest_client import app

app.config["JSON_SORT_KEYS"] = False

if __name__ == "__main__":
    app.run(host=os.environ["FLASK_HOST"], port=int(os.environ["FLASK_PORT"]), debug=True)
