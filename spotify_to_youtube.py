import requests
import base64
import yt_dlp
import sys
import re
from urllib.parse import urlparse, parse_qs
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
import os


SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

load_dotenv()

#verify command line arguments
if len(sys.argv) < 3:
    print("Usage: python spotify_to_youtube.py <Spotify Playlist ID> <YouTube Playlist ID> <Song number to start from (empty for all)>")
    sys.exit(1)

#get first youtube search result link
def first_result_link(video_name: str) -> str:
    ydl_opts = {
        "quiet": True,
        "noplaylist": True,
        'cookiesfrombrowser': ('firefox',),
        "default_search": "ytsearch1",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_name, download=False)
        if "entries" in info:
            return info["entries"][0]["webpage_url"]
        return info.get("webpage_url")

#searches for videos and returns a dictionary of video names and links
def search_videos(list_of_names):
    links = {}
    print('Listing links...')
    for name in list_of_names:
        link = first_result_link(f"{name} audio")
        links[name] = link
        print(link)
    return links

#authenticate to youtube api
def get_authenticated_service(client_secrets_file="client_secret.json"):
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
    credentials = flow.run_local_server(host='localhost', port=8080, open_browser=True)
    print("Autenticado! Continuando...")
    youtube = build("youtube", "v3", credentials=credentials)
    return youtube

#get the video id from a youtube url
def extract_video_id(youtube_url: str) -> str:
    match = re.search(r"v=([^&]+)", youtube_url)
    if match:
        return match.group(1)
    return None

#add a video to a youtube playlist
def add_video_to_playlist(youtube, playlist_id, video_id):
    try:
        request = youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id
                    }
                }
            }
        )
        response = request.execute()
        print(f"Added video {video_id} to playlist {playlist_id}")
        return response
    except HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred while adding video {video_id}: {e}")
        return None

#main function
if __name__ == "__main__":
    #connects to spotify api
    client_id = os.environ.get("CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET")

    auth_str = f"{client_id}:{client_secret}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()

    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Authorization": f"Basic {b64_auth_str}"
    }
    data = {
        "grant_type": "client_credentials"
    }

    #gets access token
    response = requests.post(url, headers=headers, data=data)

    if response.status_code == 200:
        token = response.json()["access_token"]
        print("Access Token:", token)
    else:
        print("Error:", response.status_code, response.text)

    playlist_id = str(sys.argv[1])
    playlist_url = f"https://api.spotify.com/v1/playlists/{playlist_id}"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    #gets song names and artists from spotify playlist
    response = requests.get(playlist_url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        tracks_data = data["tracks"]
        results = []

        print('Listing songs...')
        while tracks_data:
            for item in tracks_data["items"]:
                track = item["track"]
                results.append(f"{track['name']}, By {track['artists'][0]['name']}")
                print(results[len(results) - 1])
            
            # Get next page URL
            next_url = tracks_data["next"]
            if next_url:
                tracks_data = requests.get(next_url, headers=headers).json()
            else:
                tracks_data = None

    if len(sys.argv) == 4:
        try:
            n = int(sys.argv[3])
            if n > 0:
                del results[:n]
        except (ValueError, IndexError):
            print("Starting from the beginning of the playlist.")

    link_dict = search_videos(results)
    
    playlist_id = str(sys.argv[2])

    # Authenticate
    youtube = get_authenticated_service()
    
    # Loop through, extract video IDs, add to playlist
    for title, url in link_dict.items():
        video_id = extract_video_id(url)
        if not video_id:
            print(f"Could not extract video id from URL {url} (title: {title})")
            continue
        add_video_to_playlist(youtube, playlist_id, video_id)