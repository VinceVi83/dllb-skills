import os
import re
import sys
import time
import argparse
import subprocess
from bs4 import BeautifulSoup
from config_loader import Utils
from datetime import datetime, time as dt_time

class AnimeCard:
    def __init__(self, poster_div):
        self.poster_div = poster_div
        self.article_parent = poster_div.find_parent("article", class_="anime")
        
        self.status = "none"
        if self.article_parent and self.article_parent.has_attr("data-library-status"):
            status_value = self.article_parent["data-library-status"].strip()
            if status_value:
                self.status = status_value

        self.name = "Unknown"
        if self.article_parent:
            title_tag = self.article_parent.find("h3", class_="main-title")
            if title_tag and title_tag.a:
                self.name = title_tag.a.text.strip()
        
        schedule_info_tag = poster_div.find("div", class_="release-schedule-info")
        self.episode_info = schedule_info_tag.text.strip() if schedule_info_tag else "EP ?"
        
        img_tag = poster_div.find("img", {"data-anime-card-target": "poster"})
        self.poster_url = img_tag["src"] if img_tag else None

        time_tag = poster_div.find("time", {"data-anime-card-target": "countdown"})
        if time_tag:
            self.countdown = time_tag.text.strip()
            self.timestamp = time_tag.get("data-timestamp")
        else:
            if self.article_parent and self.article_parent.has_attr("data-premiere"):
                self.timestamp = self.article_parent["data-premiere"]
                self.countdown = "Scheduled date"
            else:
                self.countdown = "Unavailable"
                self.timestamp = None

        if self.timestamp:
            try:
                if int(self.timestamp) < time.time():
                    self.countdown = "Released"
            except ValueError:
                pass

def _livechart_scrap(test_mode=False):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "../.."))
    
    scraper_path = os.path.join(project_root, "skills", "scrap-url", "scrap_url.py")
    session_file = os.path.join(current_dir, "livechart.json")
    
    cmd = [
        sys.executable, scraper_path,
        "--url", "https://www.livechart.me/",
        "-s", session_file,
        "-o", current_dir
    ]
    
    if test_mode:
        cmd.append("-t")
        
    print(f"Executing: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=False, text=True)
    
    if result.returncode != 0:
        print(f"Error executing scraper. Return code: {result.returncode}")

def _extract_and_filter_animes(file_name, hide_releases=False, sort_by_countdown=False):
    if not os.path.exists(file_name):
        return [], {}

    with open(file_name, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    poster_containers = soup.find_all("div", class_="poster-container", attrs={"data-anime-card-target": "posterContainer"})
    strict_statuses = ["watching", "planning", "considering"]
    extracted_animes = []
    for container in poster_containers:
        anime_obj = AnimeCard(container)
        if anime_obj.status in strict_statuses:
            if hide_releases and anime_obj.countdown == "Released":
                continue
            extracted_animes.append((anime_obj, container))
    if sort_by_countdown:
        def sort_key_timestamp(item):
            anime = item[0]
            if anime.countdown == "Released" or not anime.timestamp:
                return float('inf')
            try: return int(anime.timestamp)
            except ValueError: return float('inf')
        extracted_animes.sort(key=sort_key_timestamp)
    else:
        watching_list = [x for x in extracted_animes if x[0].status == "watching"]
        planning_list = [x for x in extracted_animes if x[0].status == "planning"]
        considering_list = [x for x in extracted_animes if x[0].status == "considering"]
        extracted_animes = watching_list + planning_list + considering_list

    filtered_divs_list = [item[1] for item in extracted_animes]
    animes_dict = {item[0].name: item[0] for item in extracted_animes}
            
    return filtered_divs_list, animes_dict


def _notif(anime_name):
    anime = DICO_ANIMES.get(anime_name)
    if not anime or not anime.timestamp:
        return

    mapping_sites = {
        "Mushoku Tensei Ⅲ: Isekai Ittara Honki Dasu": "Crunchyroll",
        "One Piece": "ADN",
    }
    streaming_site = mapping_sites.get(anime_name, "[Streaming site]")
    
    discord_alert = (
        f"📢 **New Episode Available!**\n"
        f"🎬 The anime **{anime.name}** ({anime.episode_info}) is available on **{streaming_site}** !\n"
        f"{anime.poster_url}\n"
    )

    try:
        timestamp_cut = int(anime.timestamp)
    except ValueError:
        return

    cleaned_name = re.sub(r'[^a-zA-Z0-9\s-]', '', anime.name)
    cleaned_name = cleaned_name.replace(' ', '_')
    print(f"Calling Utils.add_oneshot_task for {anime.name} at timestamp {timestamp_cut}")
    Utils.add_oneshot_task(
        task_id=f"notif_{cleaned_name}",
        function="mcp_server.send_discord_msg",
        date_or_timestamp=timestamp_cut,
        description=discord_alert,
        args=[discord_alert, 'notify-anime'],
        hidden="yes"
    )

def notify_new_anime():
    """
    Scans the anime list and triggers Discord notifications for any episodes 
    scheduled to release today.
    """
    _livechart_scrap()
    today_start = datetime.combine(datetime.now(), dt_time.min).timestamp()
    today_end = datetime.combine(datetime.now(), dt_time.max).timestamp()

    for anime in DICO_ANIMES.values():
        if anime.timestamp:
            try:
                anime_ts = int(anime.timestamp)
                if today_start <= anime_ts <= today_end:
                    _notif(anime.name)
            except ValueError:
                pass

target_file = "skills/anime-notify/www_livechart_me_raw.html"
_, DICO_ANIMES = _extract_and_filter_animes(target_file, hide_releases=False, sort_by_countdown=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", action="store_true")
    args = parser.parse_args()

    now = time.time()

    if args.t:
        valid_animes = [a for a in DICO_ANIMES.values() if a.timestamp]
        if valid_animes:
            closest_anime = min(valid_animes, key=lambda x: abs(int(x.timestamp) - now))
            _notif(closest_anime.name)