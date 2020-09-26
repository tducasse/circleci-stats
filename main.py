import requests
from dotenv import load_dotenv, find_dotenv
import os
import matplotlib.pyplot as plt
import pandas as pd
from dateutil.parser import parse
import math
from slugify import slugify
import webbrowser
import pathlib
from statistics import mean
import jinja2

root = pathlib.Path(__file__).parent.absolute()
load_dotenv(find_dotenv())

TOKEN = os.getenv("TOKEN", "")
BRANCH = os.getenv("BRANCH", "")
WORKFLOW = os.getenv("WORKFLOW", "")
PROJECT = os.getenv("PROJECT", "")
LIMIT = int(os.getenv("LIMIT", ""))
WSL_ROOT = os.getenv("WSL_ROOT", "")

actual_root = ("wsl$/Ubuntu" if WSL_ROOT else "") + str(root)

url = "https://circleci.com/api/v1.1/project/" + PROJECT
querystring = {"shallow": "true", "filter": "successful", "limit": "100"}
headers = {"circle-token": TOKEN}

# just to convert from milliseconds to something readable
def convert(millis):
    millis = int(millis)
    seconds = int((millis / 1000) % 60)
    minutes = int((millis / (1000 * 60)) % 60)
    hours = int((millis / (1000 * 60 * 60)) % 24)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{millis%1000:003}"


offset = 0
build_nums = []
keep_going = True
while len(build_nums) < LIMIT and keep_going:
    querystring["offset"] = offset
    response = requests.request("GET", url, headers=headers, params=querystring)
    if not response:
        # network or auth error
        print("No response")
        exit()
    json = response.json()
    if not json:
        # the list is empty
        keep_going = False
        break

    build_nums.extend(
        [
            x.get("build_num")
            for x in json
            if x.get("branch", None) == BRANCH
            and x.get("workflows", {}).get("job_name", None) == WORKFLOW
        ]
    )
    offset += 100

build_nums = sorted(build_nums[0 : min([LIMIT, len(build_nums)])])

grouped_jobs = {}
for build_num in build_nums:
    response = requests.request("GET", url + f"/{build_num}", headers=headers)
    if not response:
        # network or auth error
        print("No response")
        exit()
    json = response.json()
    jobs = json.get("steps")
    if not jobs:
        print("Invalid response")
        exit()
    committer_date = json.get("committer_date")

    for job in jobs:
        grouped_jobs.setdefault(job["name"], []).append(
            {
                "committer_date": parse(committer_date) if committer_date else None,
                "run_time": job.get("actions", [{}])[0].get("run_time_millis"),
            }
        )

data = []
for key, value in grouped_jobs.items():
    df = pd.DataFrame(value)
    df.plot(x="committer_date", y="run_time", title=key)
    slug = slugify(key)

    plt.savefig(f"{root}/svg/{slug}.svg")
    values = df["run_time"]
    data.append(
        {
            "name": slug,
            "mean": convert(round(values.mean())),
            "max": convert(round(values.max())),
            "min": convert(round(values.min())),
            "file": f"file://{actual_root}/svg/{slug}.svg",
        }
    )

templateLoader = jinja2.FileSystemLoader(searchpath=str(root))
templateEnv = jinja2.Environment(loader=templateLoader)
TEMPLATE_FILE = "/template.html"
template = templateEnv.get_template(TEMPLATE_FILE)

outputText = template.render(data=data)

f = open(str(root) + "/index.html", "w+")
f.write(outputText)
f.close()


webbrowser.open("file://" + actual_root + "/index.html", new=2)
