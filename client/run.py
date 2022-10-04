import os
from autotest_client import app

if __name__ == "__main__":
    app.run(host=os.environ["FLASK_HOST"], port=int(os.environ["FLASK_PORT"]), debug=True)
