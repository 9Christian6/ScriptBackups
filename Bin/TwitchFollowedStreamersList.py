import requests
from twitchAPI.twitch import Twitch
from twitchAPI.helper import List
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope
import asyncio
import time
import sys
import os
import threading
import json
import argparse
from datetime import datetime, timedelta

# Replace these with your own credentials from Twitch Dev Console
#APP_ID = 'ds04gq574qqencjhxb15yo6yito9sc'
#APP_SECRET = 'knqilwhetlc4w08v3rlzuwcaj0jbho'
APP_ID = ''
APP_SECRET = ''
# Load credentials from files
try:
    with open('/home/christian/Opt/PythonEnvs/TwitchFollowedStreamers/Credentials/APP_ID', 'r') as f:
        APP_ID = f.read().strip()
    with open('/home/christian/Opt/PythonEnvs/TwitchFollowedStreamers/Credentials/APP_SECRET', 'r') as f:
        APP_SECRET = f.read().strip()
except FileNotFoundError as e:
    print(f"Error: Could not find credential file: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error reading credentials: {e}")
    sys.exit(1)

TIME_INTERVAL = 60

# Token cache file
# TOKEN_CACHE_FILE = os.path.expanduser('~/.twitch_token_cache.json')
TOKEN_CACHE_FILE = os.path.expanduser('~/Opt/PythonEnvs/TwitchFollowedStreamers/.twitch_token_cache.json')

# Global variable to control spinner
spinner_running = False
remaining_time = 0
pretty_prints = True

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Monitor your followed Twitch streamers')
    parser.add_argument('--no-pretty-prints', action='store_true', 
                       help='Disable pretty prints and spinner animations')
    parser.add_argument('--time', type=int, metavar='N',
                       help='Set time interval in seconds (default is 60)')
    return parser.parse_args()

def save_tokens(token, refresh_token):
    """Save tokens to cache file with expiration time"""
    token_data = {
        'access_token': token,
        'refresh_token': refresh_token,
        'expires_at': (datetime.now() + timedelta(days=60)).isoformat(),  # Tokens typically last 60 days
        'created_at': datetime.now().isoformat()
    }
    
    try:
        with open(TOKEN_CACHE_FILE, 'w') as f:
            json.dump(token_data, f)
        if pretty_prints:
            print("Authentication tokens saved to cache.")
    except Exception as e:
        if pretty_prints:
            print(f"Warning: Could not save tokens to cache: {e}")

def load_tokens():
    """Load tokens from cache file if they exist and are not expired"""
    if not os.path.exists(TOKEN_CACHE_FILE):
        return None, None
    
    try:
        with open(TOKEN_CACHE_FILE, 'r') as f:
            token_data = json.load(f)
        
        # Check if tokens are expired
        expires_at = datetime.fromisoformat(token_data['expires_at'])
        if datetime.now() > expires_at:
            print("Cached tokens are expired.")
            return None, None
        
        if pretty_prints:
            print("Using cached authentication tokens.")
        return token_data['access_token'], token_data['refresh_token']
    
    except Exception as e:
        if pretty_prints:
            print(f"Warning: Could not load cached tokens: {e}")
        return None, None

def clear_token_cache():
    """Clear the token cache file"""
    try:
        if os.path.exists(TOKEN_CACHE_FILE):
            os.remove(TOKEN_CACHE_FILE)
            if pretty_prints:
                print("Token cache cleared.")
    except Exception as e:
        if pretty_prints:   
            print(f"Warning: Could not clear token cache: {e}")

def spinner_animation():
    """Simple spinner animation that runs in a separate thread with countdown timer"""
    spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    i = 0
    global remaining_time

    while spinner_running:
        # Calculate minutes and seconds remaining
        minutes = int(remaining_time // 60)
        seconds = int(remaining_time % 60)

        if minutes > 0:
            time_str = f"{minutes}m {seconds}s"
        else:
            time_str = f"{seconds}s"

        # Use a fixed-width spinner character and ensure consistent line length
        spinner_line = f"\r{spinner_chars[i]} Waiting for next update... ({time_str} remaining) (Press Ctrl+C to stop)"
        # Pad the line to ensure consistent length
        spinner_line = spinner_line.ljust(80)  # Adjust 80 to match your terminal width if needed
        if pretty_prints:
            print(spinner_line, end='', flush=True)
        time.sleep(0.1)
        i = (i + 1) % len(spinner_chars)
        remaining_time -= 0.1

async def get_live_channels(twitch, user):
    # Get followed channels
    followed_channels = twitch.get_followed_streams(user.id)

    if not followed_channels:
        if pretty_prints:
            print("You are not following any streamers.")
        return []

    # Get live streams for followed channels
    live_channels = []
    async for channel in followed_channels:
        if channel.type == 'live':
            live_channels.append(channel.user_name)
    return live_channels

def parse_time(cmd_time=None):
    global TIME_INTERVAL
    if cmd_time is not None:
        TIME_INTERVAL = cmd_time
        if TIME_INTERVAL < 1:
            if pretty_prints:
                print("Time interval must be at least 1 second. Using default of 60 seconds.")
            TIME_INTERVAL = 60
        return
    
    try:
        TIME_INTERVAL = 60
        user_input = input("Enter time interval in seconds (default is 60): ")
        if user_input.strip() and user_input.isdigit():
            TIME_INTERVAL = int(user_input)
            if TIME_INTERVAL < 1:
                if pretty_prints:
                    print("Time interval must be at least 1 second. Using default of 60 seconds.")
                TIME_INTERVAL = 60
            
    except ValueError:
        if pretty_prints:   
            print("Invalid input. Using default time interval of 60 seconds.")
        TIME_INTERVAL = 60

async def main():
    global spinner_running, TIME_INTERVAL, remaining_time, pretty_prints
    args = parse_arguments()
    if args.no_pretty_prints:
        pretty_prints = False
    else:
        user_input = input("Do you want pretty prints? (Y|n): ").strip().lower()
        if user_input in ['n', 'no']:
            pretty_prints = False
        else:
            pretty_prints = True
    parse_time(args.time)
    
    # Initialize the Twitch instance
    twitch = await Twitch(APP_ID, APP_SECRET)
    
    # Try to load cached tokens first
    token, refresh_token = load_tokens()
    
    if token and refresh_token:
        # Try to use cached tokens
        try:
            target_scope = [AuthScope.USER_READ_FOLLOWS]
            await twitch.set_user_authentication(token, target_scope, refresh_token)
            if pretty_prints:
                print("Successfully authenticated using cached tokens.")
        except Exception as e:
            if pretty_prints:
                print(f"Cached tokens are invalid: {e}")
                print("Clearing cache and re-authenticating...")
            clear_token_cache()
            token, refresh_token = None, None
    
    if not token or not refresh_token:
        # Set up user authentication
        target_scope = [AuthScope.USER_READ_FOLLOWS]
        if pretty_prints:
            print('target scope')
        auth = UserAuthenticator(twitch, target_scope, force_verify=False)
        if pretty_prints:
            print('auth')
        token, refresh_token = await auth.authenticate(use_browser=True)
        if pretty_prints:
            print('token')
        await twitch.set_user_authentication(token, target_scope, refresh_token)
        
        # Save tokens to cache
        save_tokens(token, refresh_token)

    # Get the user
    users = twitch.get_users(logins=['skyi0ne'])
    user = await anext(users) if users else None
    if not user:
        if pretty_prints:
            print("User not found")
        return

    try:
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            live_channels = await get_live_channels(twitch, user)
            if pretty_prints:
                print(str(len(live_channels)) + " Channels are live:\n")
            if live_channels:
                for channel in live_channels:
                    print(channel)
                    #print(f"{channel}")
            else:
                if pretty_prints:
                    print("\nNo live channels at the moment.")
                    print('\n')
            # Start spinner in background thread
            spinner_running = True
            remaining_time = TIME_INTERVAL
            spinner_thread = threading.Thread(target=spinner_animation, daemon=True)
            spinner_thread.start()

            # Wait for the specified interval
            time.sleep(TIME_INTERVAL)

            # Stop spinner
            spinner_running = False
            spinner_thread.join(timeout=0.1)  # Wait a bit for thread to finish

    except KeyboardInterrupt:
        spinner_running = False
        if pretty_prints:
            print("\nStopping channel monitor. Goodbye!")
        sys.exit(0)

if __name__ == '__main__':
    asyncio.run(main())
