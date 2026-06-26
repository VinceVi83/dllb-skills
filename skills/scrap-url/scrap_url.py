import argparse
import os
import re
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
import trafilatura

def _get_safe_filename(url):
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.replace('.', '_')
    if not domain:
        domain = "extracted_page"
    return domain

def run_scraper(target_url, session_filename=None, test_mode=False, output_dir="output"):
    os.makedirs(output_dir, exist_ok=True)
    
    base_name = _get_safe_filename(target_url)
    nom_fichier_html = os.path.join(output_dir, f"{base_name}_raw.html")
    nom_fichier_texte = os.path.join(output_dir, f"{base_name}_clean.txt")

    with sync_playwright() as p:
        is_headless = not test_mode

        if test_mode:
            print("=== TEST MODE ENABLED : The browser will remain open. ===")
        else:
            print(f"Launching the bot (Headless: {is_headless})...")

        browser = p.chromium.launch(headless=is_headless)
        
        if session_filename and os.path.exists(session_filename):
            print(f"Loading session: {session_filename}")
            context = browser.new_context(storage_state=session_filename)
        else:
            print("Browsing in anonymous mode (without session)...")
            context = browser.new_context()

        page = context.new_page()
        print(f"Connecting and loading: {target_url}")
        
        page.goto(target_url, timeout=60000)
        
        if test_mode:
            print("\n" + "="*60)
            print("THE BROWSER IS OPEN IN TEST MODE.")
            print("Navigate the window, check what you want.")
            print("To close the browser and quit, press [ENTER] here.")
            print("="*60 + "\n")
            
            input("Press Enter to quit...")
            browser.close()
            print("Browser closed. End of test.")
            return

        print("Waiting for network to be idle...")
        page.wait_for_load_state("networkidle")
        
        try:
            gdpr_button = page.get_by_role("button", name=re.compile(r"Consent|Accept|Accepter|Autoriser", re.IGNORECASE))
            if gdpr_button.is_visible():
                print("Cookie banner detected, clicking consent...")
                gdpr_button.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass

        html_brut = page.content()
        with open(nom_fichier_html, "w", encoding="utf-8") as f:
            f.write(html_brut)
        print(f"Raw HTML file created: '{nom_fichier_html}'")

        browser.close()
        print("Browser closed.")

    print("Extracting text with Trafilatura...")
    extracted_text = trafilatura.extract(html_brut)

    if extracted_text:
        with open(nom_fichier_texte, "w", encoding="utf-8") as f:
            f.write(extracted_text)
        print(f"Clean text file created: '{nom_fichier_texte}'")
    else:
        print("Trafilatura could not extract text from this page.")

    print("End of execution.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generic Web Scraper & Text Extractor")
    
    parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="The URL of the page to scrape"
    )
    parser.add_argument(
        "-s", "--session", 
        type=str, 
        default=None,
        help="Path to session JSON file for auth state (optional)"
    )
    parser.add_argument(
        "-t", "--test", 
        action="store_true",
        help="Open the page in visible mode for inspection without saving data"
    )
    parser.add_argument(
        "-o", "--output", 
        type=str, 
        default="output",
        help="Directory where output files will be saved"
    )

    args = parser.parse_args()
    
    run_scraper(
        target_url=args.url, 
        session_filename=args.session, 
        test_mode=args.test,
        output_dir=args.output
    )