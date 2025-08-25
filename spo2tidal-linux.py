import json
import sys
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import tidalapi
import time
import os
import csv
from datetime import datetime

# ==== CONFIGURATION ====
SPOTIFY_CLIENT_ID = 'add id'
SPOTIFY_CLIENT_SECRET = 'add secret'
PLAYLIST_NAME_PREFIX = 'Imported: '
# ========================

def extract_playlist_id(playlist_url):
    """Extract the playlist ID from a Spotify playlist URL"""
    if 'spotify.com/playlist/' in playlist_url:
        playlist_id = playlist_url.split('playlist/')[-1].split('?')[0]
        return playlist_id
    return None

def print_usage():
    print("Usage: python spo2tidal-linux.py <spotify_playlist_url> [spotify_playlist_url2 ...]")
    print("Example: python spo2tidal-linux.py https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")
    sys.exit(1)

# Authenticate Spotify
print("🔐 Authenticating with Spotify...")
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))
print("✅ Spotify authentication successful.")

# Authenticate Tidal
print("🔐 Authenticating with Tidal...")
session = tidalapi.Session()
try:
    # This will print a URL that the user needs to visit
    print("\nPlease visit this URL to authorize Tidal:")
    session.login_oauth_simple()
    print("✅ Tidal authentication successful.")
except Exception as e:
    print("❌ Tidal authentication failed!")
    print(f"Error: {str(e)}")
    sys.exit(1)

def fetch_spotify_tracks(playlist_id):
    print("📥 Fetching tracks from Spotify...")
    results = sp.playlist_tracks(playlist_id)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])

    track_data = []
    for item in tracks:
        track = item['track']
        if track:  # Check if track exists (not None)
            name = track['name']
            artists = [artist['name'] for artist in track['artists']]
            artist = artists[0]  # Primary artist
            all_artists = ', '.join(artists)  # All artists
            album = track['album']['name']
            print(f"🎵 Found: {name} - {all_artists}")
            track_data.append({
                'title': name,
                'artist': artist,
                'all_artists': all_artists,
                'album': album
            })
    return track_data

def import_to_tidal(tracks, playlist_name):
    print(f"\n📀 Creating Tidal playlist: {playlist_name}")
    
    missing_tracks = []
    success_count = 0
    
    try:
        # Create new playlist
        playlist = session.user.create_playlist(playlist_name, "Imported from Spotify")
        print(f"✅ Created playlist: {playlist_name}")
        
        for t in tracks:
            query = f"{t['title']} {t['artist']}"
            print(f"🔍 Searching: {query}")
            
            try:
                # Search for track on Tidal
                search_results = session.search(query, models=[tidalapi.media.Track])
                
                if search_results.tracks and len(search_results.tracks) > 0:
                    # Find best match
                    best_match = None
                    for track in search_results.tracks:
                        if (track.name.lower() == t['title'].lower() and 
                            any(artist.name.lower() == t['artist'].lower() 
                                for artist in track.artists)):
                            best_match = track
                            break
                    
                    if best_match:
                        playlist.add([best_match])
                        success_count += 1
                        print(f"   ✅ Added: {t['title']} by {t['artist']}")
                    else:
                        print(f"   ❌ No exact match found: {query}")
                        missing_tracks.append({
                            'title': t['title'],
                            'artist': t['all_artists'],
                            'album': t['album'],
                            'reason': 'No exact match found'
                        })
                else:
                    print(f"   ❌ Not found: {query}")
                    missing_tracks.append({
                        'title': t['title'],
                        'artist': t['all_artists'],
                        'album': t['album'],
                        'reason': 'Not found in Tidal'
                    })
            except Exception as e:
                print(f"   ❌ Error processing {query}: {e}")
                missing_tracks.append({
                    'title': t['title'],
                    'artist': t['all_artists'],
                    'album': t['album'],
                    'reason': f'Error: {str(e)}'
                })
            
            time.sleep(1)  # Rate limiting
    
    except Exception as e:
        print(f"❌ Failed to create or modify playlist: {e}")
        return

    # Create CSV file for missing tracks
    if missing_tracks:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f'missing_tracks_{timestamp}.csv'
        try:
            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=['title', 'artist', 'album', 'reason'])
                writer.writeheader()
                writer.writerows(missing_tracks)
            print(f"\n📝 Created CSV file with {len(missing_tracks)} missing tracks: {csv_filename}")
        except Exception as e:
            print(f"❌ Failed to create CSV file: {e}")
    
    print(f"\n✅ Import complete! Successfully added {success_count} of {len(tracks)} tracks")

# Main process
if len(sys.argv) < 2:
    print_usage()

for playlist_url in sys.argv[1:]:
    playlist_id = extract_playlist_id(playlist_url)
    if not playlist_id:
        print(f"❌ Invalid Spotify playlist URL: {playlist_url}")
        continue

    print(f"\n--- Processing playlist: {playlist_id} ---")
    try:
        playlist_info = sp.playlist(playlist_id)
        playlist_name = PLAYLIST_NAME_PREFIX + playlist_info['name']
        tracks = fetch_spotify_tracks(playlist_id)
        import_to_tidal(tracks, playlist_name)
    except Exception as e:
        print(f"❌ Failed to import {playlist_id}: {e}")
