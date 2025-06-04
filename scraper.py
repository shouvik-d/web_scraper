from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from geopy.geocoders import ArcGIS, Nominatim, Photon
from geopy.extra.rate_limiter import RateLimiter
import pandas as pd
import time
import re

def get_state_mapping(driver):
    """Get all available states and their codes from the dropdown"""
    wait = WebDriverWait(driver, 15)
    state_dropdown = wait.until(EC.presence_of_element_located((By.ID, "state_selector")))
    state_options = state_dropdown.find_elements(By.TAG_NAME, "option")
    
    state_mapping = {}
    for option in state_options:
        value = option.get_attribute("value")
        if value:  # Skip the default empty option
            text = option.text
            # Extract the 2-letter code from the text (e.g., "WA - Washington")
            code = text.split()[0]
            state_mapping[code] = text
    return state_mapping

def get_user_input():
    """Get user input for state selection before starting any scraping"""
    print("\nTruck Stop Scraper - State Selection")
    print("Options:")
    print("1. Enter a single state code (e.g., WA)")
    print("2. Enter multiple state codes separated by commas (e.g., WA,OR,CA)")
    print("3. Enter 'ALL' to process all states")
    
    while True:
        user_input = input("\nEnter your selection: ").strip().upper()
        
        if user_input == "ALL":
            return "ALL"
        
        # Check for multiple states
        if ',' in user_input:
            states = [s.strip() for s in user_input.split(',') if s.strip()]
            if states:
                return states
        
        # Check for single state
        if len(user_input) == 2 and user_input.isalpha():
            return user_input
        
        print("Invalid input. Please enter a valid state code, multiple codes separated by commas, or 'ALL'.")

def setup_geocoders():
    """Initialize geocoders"""
    arcgis_locator = ArcGIS(user_agent="arcgis_geo_coder", timeout=3)
    arcgis_geocoder = RateLimiter(arcgis_locator.geocode, min_delay_seconds=1)
    nominatim_locator = Nominatim(user_agent="nominatim_geo_coder", timeout=3)
    nominatim_geocoder = RateLimiter(nominatim_locator.geocode, min_delay_seconds=1)
    photon_locator = Photon(user_agent="photon_geo_coder", timeout=3)
    photon_geocoder = RateLimiter(photon_locator.geocode, min_delay_seconds=1)
    return [arcgis_geocoder, nominatim_geocoder, photon_geocoder]

def geocode_usa(query, geo_coders):
    for geocoder in geo_coders:
        try:
            result = geocoder(query)
            if result:
                return result
        except:
            continue
    return None

def process_state(driver, state_code, state_text, geo_coders, output_dir):
    """Process a single state and save its data"""
    print(f"\nProcessing state: {state_text}")
    wait = WebDriverWait(driver, 15)
    
    # Select the state
    Select(wait.until(EC.presence_of_element_located((By.ID, "state_selector")))).select_by_visible_text(state_text)
    time.sleep(2)

    # Select "Truck Stops" from the dropdown
    Select(wait.until(EC.presence_of_element_located((By.ID, "cat_selector")))).select_by_visible_text("Truck Stops")
    time.sleep(2)

    # Get all highway options
    highway_dropdown = wait.until(EC.presence_of_element_located((By.ID, "highway_selector")))
    highway_options = [
        option.get_attribute("value")
        for option in highway_dropdown.find_elements(By.TAG_NAME, "option")
        if option.get_attribute("value")
    ]

    data = []

    # Loop through each highway
    for highway in highway_options:
        print(f"Scraping highway: {highway}")
        Select(highway_dropdown).select_by_value(highway)
        time.sleep(2)

        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "adminclickablerow")))
        except:
            print(f"No listings appeared for {highway}, skipping..")
            continue

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        listings = soup.find_all('tr', class_='adminclickablerow')
        print(f"Found {len(listings)} listings on {highway}")

        for row in listings:
            try:
                name_tag = row.find('span')
                name = name_tag.text.strip() if name_tag else "N/A"

                p_tags = row.find_all('p')
                highway_exit = p_tags[0].text.strip() if len(p_tags) > 0 else ""

                # Extract highway route
                match = re.search(r'(I|US)[\s\-]+(\d+[A-Z\-]*)', highway_exit)
                highway_route = f"{match.group(1)}-{match.group(2)}" if match else ""

                # Extract exit
                exit_num = ''
                if 'Exit' in highway_exit:
                    exit_match = re.search(r'Exit\s*([A-Za-z0-9\-]+)', highway_exit)
                    if exit_match:
                        exit_num = f"Exit {exit_match.group(1)}"

                # Get number of parking spots
                truck_parking_spots = 0
                for p in p_tags:
                    if '# Truck Parking Spots:' in p.text:
                        try:
                            truck_parking_spots = int(re.search(r'# Truck Parking Spots:\s*(\d+)', p.text).group(1))
                        except:
                            truck_parking_spots = 0
                        break

                if truck_parking_spots == 0:
                    continue  # Skip non-truck stops

                # Build address and exclude extra facility info
                address_lines = []
                for p in p_tags[1:]:
                    line = ' '.join(t.strip() for t in p.stripped_strings)
                    if '(TRAVEL CENTER)' in line or '# Showers' in line or '# Fuel Lanes' in line:
                        break
                    address_lines.append(line)
                address = ', '.join(address_lines)

                # Geocode address
                location = geocode_usa(address, geo_coders)
                latitude = location.latitude if location else None
                longitude = location.longitude if location else None

                # Append to data
                data.append({
                    'State': state_code,
                    'Truck Stop Name': name,
                    'Highway Route': highway_route,
                    'Exit': exit_num,
                    'Address': address,
                    'Latitude': latitude,
                    'Longitude': longitude
                })

            except Exception as e:
                print(f"Error extracting data: {e}")

    # Export to CSV
    if data:
        df = pd.DataFrame(data)
        df.to_csv(f"{output_dir}\\{state_code}_truck_stops.csv", index=False, encoding='utf-8')
        print(f"Saved {len(df)} truck stops to {output_dir}\\{state_code}_truck_stops.csv")
    else:
        print(f"No truck stop data found for {state_code}")

def main():
    # Get all user input FIRST before starting any web drivers
    user_selection = get_user_input()
    output_dir = r"C:\Users\SHOUVIK\Desktop\ElectroT\web_scraper\Truckstop_data"
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Running in headless version 
    # Only now initialize the web driver
    driver = webdriver.Chrome(options=options)
    try:
        driver.get("https://www.truckstopsandservices.com/truckstop-directory2.php")
        
        # Get all available states from the dropdown
        state_mapping = get_state_mapping(driver)
        
        # Setup geocoders
        geo_coders = setup_geocoders()
        
        # Process based on user selection
        if user_selection == "ALL":
            print("\nProcessing ALL states...")
            for state_code, state_text in state_mapping.items():
                process_state(driver, state_code, state_text, geo_coders, output_dir)
        elif isinstance(user_selection, list):
            print("\nProcessing multiple states...")
            for state_code in user_selection:
                if state_code in state_mapping:
                    process_state(driver, state_code, state_mapping[state_code], geo_coders, output_dir)
                else:
                    print(f"Warning: State code '{state_code}' not found in available states.")
        else:
            if user_selection in state_mapping:
                process_state(driver, user_selection, state_mapping[user_selection], geo_coders, output_dir)
            else:
                print(f"Error: State code '{user_selection}' not found in available states.")
        
        print("\nScraping complete.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()