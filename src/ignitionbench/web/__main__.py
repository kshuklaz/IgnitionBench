"""Run the IgnitionBench web UI: python -m ignitionbench.web"""

from . import create_app

create_app().run(host="127.0.0.1", port=8000)
