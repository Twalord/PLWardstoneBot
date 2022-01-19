"""
Take in a Primeleague group to watch.
Take in a Primeleague team to watch.
Find all matches in that group for that team.
Fetch the log section of the match page for each match.
Save these log section locally.
On a regular interval, check the match pages again and compare the log sections with the local save.
Note any special events, such as schedule suggestions, autoconfirms and played.
Send out messages about these events to the target channel.
Update the local saves of the log section.
"""

import requests
import bs4
from pprint import pprint
from datetime import datetime
import json
from pathlib import Path
import schedule
import time
import settings

significant_events = ["played", "lineup_missing", "scheduling_suggest", "scheduling_confirm", "scheduling_autoconfirm",
                      "change_status"]
completed_events = ["played", "lineup_missing", "change_status"]
saved_logs_dir = "saved_logs"
match_urls = set()  # helper set


def generate_file_path(match_up):
    return Path(saved_logs_dir + "/" + match_up + ".json")


def get_match_urls_for_group(group_url, team):
    page = requests.get(group_url)

    soup = bs4.BeautifulSoup(page.text, features="html.parser")

    urls = set()
    for link in soup.find_all('a', href=True):
        if "-vs-" + team in link['href'] or team + "-vs-" in link['href']:
            urls.add(link['href'])
    print("Found match urls:")
    pprint(urls)
    return urls


def filter_logs(match_log_dict):
    logs_dict = match_log_dict["logs"]
    filter_logs_dict = []
    for log_dict in logs_dict:
        if "Action" not in log_dict:
            continue
        if log_dict["Action"].strip() in significant_events:
            filter_logs_dict.append(log_dict)

    match_log_dict["logs"] = filter_logs_dict
    return match_log_dict


def get_logs_for_match(match_url):
    page = requests.get(match_url)

    soup = bs4.BeautifulSoup(page.text, features="html.parser")

    logs_section = soup.find("section", class_="boxed-section league-match-logs")
    log_table = logs_section.find("table", class_="table table-flex table-responsive table-static")

    # print(log_table.prettify())

    logs = []

    keys = ["Player", "Action", "Details", "UnixTime", "Time"]

    rows = log_table.find_all("tr")
    for row in rows:
        cols_td = row.find_all("td")
        cols = [ele.text.strip() for ele in cols_td]
        for ele in cols_td:
            time_class = ele.find("span", class_="itime")
            if time_class:
                time_stamp = int(time_class.attrs["data-time"])
                cols.append(time_stamp)
                cols.append(datetime.utcfromtimestamp(time_stamp).strftime('%Y-%m-%d %H:%M:%S'))
        logs.append([ele for ele in cols if ele])

    logs_dict = []

    completed = False
    for log in logs:
        log_dict = dict(zip(keys, log))
        if "Action" in log_dict:
            if log_dict["Action"].strip() in completed_events:
                completed = True
        logs_dict.append(log_dict)

    # print(logs)
    # pprint(logs_dict)

    match_log_dict = {"URL": match_url, "logs": logs_dict, "Completed": completed}

    print(f"Got {len(logs)} logs for {match_url}")
    return filter_logs(match_log_dict)


def get_match_up_from_match_url(match_url):
    split = match_url.split("/")
    match_up = split[-1]
    return match_up


def save_logs_to_disk(match_log_dict, match_up):
    json_dict = json.dumps(match_log_dict)
    file = generate_file_path(match_up)
    overwritten = False
    if file.is_file():
        overwritten = True
    with open(file, "w") as f:
        f.write(json_dict)
    print(f"Saved {file}")
    return overwritten


def load_logs_from_disk(match_up):
    file = generate_file_path(match_up)
    if not file.is_file():
        print(f"Error loading logs from disk. File {file} not found.")
        return dict()
    else:
        with open(file) as f:
            match_log_dict = json.load(f)
        print(f"Loaded {file}")
        return match_log_dict


def delete_logs_from_disk(match_up):
    file = generate_file_path(match_up)
    if file.is_file():
        file.unlink()
        print(f"Delete {file}")
    else:
        print(f"Error deleting logs from disk. File {file} not found.")


def format_messages(logs, match_url):
    messages = []
    for event in logs:
        message = ""
        message += event["Time"] + " , "
        message += event["Player"] + " , "
        message += event["Action"] + " , "
        message += event["Details"] + " , "
        message += match_url
        messages.append(message)
    return messages


def send_alert_via_webhook(messages):
    output = "Detected the following new events:"
    for message in messages:
        output += "\n" + message

    data = {"content": output}
    r = requests.post(settings.webhook, json=data)
    print(f"Send message to webhook, got status code: {r.status_code}")


def report_new_logs(logs, match_url):
    messages = format_messages(logs, match_url)
    send_alert_via_webhook(messages)


def check_for_new_events_helper():
    urls_to_remove = []
    for match_url in match_urls:
        print(f"Checking {match_url} for new events.")
        keep_url = check_for_new_events(match_url)
        if not keep_url:
            urls_to_remove.append(match_url)

    for url in urls_to_remove:
        match_urls.remove(url)
        print(f"Removed {url} from watchlist.")

    if len(match_urls) == 0:
        print("No more urls to watch, stopping watch.")
        return schedule.CancelJob


def check_for_new_events(match_url):
    match_up = get_match_up_from_match_url(match_url)

    file = generate_file_path(match_up)
    file_exists = file.is_file()

    new_match_log_dict = get_logs_for_match(match_url)

    if new_match_log_dict["Completed"]:
        if file_exists:
            delete_logs_from_disk(match_up)
        print(f"This match is completed {match_url}")
        return False

    if file_exists:
        loaded_match_log_dict = load_logs_from_disk(match_up)
    else:
        save_logs_to_disk(new_match_log_dict, match_up)
        return True

    diff = [i for i in new_match_log_dict["logs"] if i not in loaded_match_log_dict["logs"]]

    if len(diff) == 0:
        print("No new events found.")
        return True
    else:
        print("New events found.")
        pprint(diff)

        save_logs_to_disk(new_match_log_dict, match_up)

        report_new_logs(diff, match_url)

    return True


if __name__ == '__main__':
    match_urls = get_match_urls_for_group(settings.group_url, settings.team)

    schedule.every(2).hours.do(check_for_new_events_helper)

    while True:
        schedule.run_pending()
        if len(match_urls) == 0:
            break
        time.sleep(1800)
