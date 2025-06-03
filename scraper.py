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

# Setup geocoders
arcgis_locator = ArcGIS(user_agent="arcgis_geo_coder", timeout=3)
arcgis_geocoder = RateLimiter(arcgis_locator.geocode, min_delay_seconds=1)
nominatim_locator = Nominatim(user_agent="nominatim_geo_coder", timeout=3)
nominatim_geocoder = RateLimiter(nominatim_locator.geocode, min_delay_seconds=1)
photon_locator = Photon(user_agent="photon_geo_coder", timeout=3)
photon_geocoder = RateLimiter(photon_locator.geocode, min_delay_seconds=1)

geo_coder_list = [arcgis_geocoder, nominatim_geocoder, photon_geocoder]

def geocode_usa(query, geo_coders):
    for geocoder in geo_coders:
        try:
            result = geocoder(query)
            if result:
                return result
        except:
            continue
    return None

# Set up the web driver
driver = webdriver.Chrome()
driver.get("https://www.truckstopsandservices.com/truckstop-directory2.php")
wait = WebDriverWait(driver, 15)

# Choose the state to scrape
state = 'WA'
Select(wait.until(EC.presence_of_element_located((By.ID, "state_selector")))).select_by_visible_text(f"{state} - Washington")
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
            location = geocode_usa(address, geo_coder_list)
            latitude = location.latitude if location else None
            longitude = location.longitude if location else None

            # Append to data
            data.append({
                'State': state,
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
df = pd.DataFrame(data)
output_dir = r"C:\Users\SHOUVIK\Desktop\ElectroT\web_scraper\Truckstop_data"
df.to_csv(f"{output_dir}\\{state}_truck_stops.csv", index=False, encoding='utf-8')
print(f"\nScraping complete. Saved {len(df)} truck stops to {output_dir}\\{state}_truck_stops.csv")

driver.quit()
