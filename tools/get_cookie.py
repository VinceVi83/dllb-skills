import argparse
import time
from playwright.sync_api import sync_playwright

def manual_login_trigger(login_url, session_filename):
    """
    Launches a non-headless browser to allow manual user login, then saves the authenticated session state.

    This function opens a visible Chromium browser instance, navigates to the provided login URL, 
    and pauses execution until the user manually authenticates and confirms via the terminal. 
    Once confirmed, it exports the complete browser context state—including cookies, local storage, 
    and session storage—into a JSON file for future automated, authenticated sessions.

    Args:
        login_url (str): The URL of the target website's login page.
        session_filename (str): The path/filename of the JSON file where the session state will be saved.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print(f"Navigating to: {login_url}")
        page.goto(login_url)
        
        print("\n" + "="*60)
        print("LOG IN MANUALLY INSIDE THE BROWSER WINDOW.")
        print("Once you are logged in and on the correct page...")
        print("="*60 + "\n")
        
        confirmation = ""
        while confirmation.lower() != 'y':
            confirmation = input("Type 'y' in this terminal to save the session: ")

        time.sleep(2)

        context.storage_state(path=session_filename)
        print(f"\n✅ Session successfully saved to: {session_filename}")
        
        browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Manual login session saver using Playwright",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples of execution:
  python %(progs)s https://example.com/login
  python %(progs)s https://example.com/login -o my_session.json
  python %(progs)s https://example.com/login --output auth/target.json
        """
    )
    
    parser.add_argument("url", type=str, help="The login URL of the target website")
    
    parser.add_argument("-o", "--output", type=str, default="session.json", 
                        help="Output JSON file name (default: session.json)")

    args = parser.parse_args()
    manual_login_trigger(args.url, args.output)