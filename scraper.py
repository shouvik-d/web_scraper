from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
import re

# Setting up the webdriver with the website link
driver = webdriver.Chrome()
driver.get("https://www.truckstopsandservices.com/truckstop-directory2.php")
wait = WebDriverWait(driver, 15)

# Initial state input (currently unused except for final file name)
state = 'CO'

# Select the desired state
Select(wait.until(EC.presence_of_element_located((By.ID, "state_selector")))).select_by_visible_text("CO - Colorado")
time.sleep(2)

# Select 'Truck Stops' from the service category
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

    # Wait for truck stop listings to appear
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
            # Truck stop name
            name_tag = row.find('span')
            name = name_tag.text.strip() if name_tag else "N/A"

            # Get all <p> tags
            p_tags = row.find_all('p')
            highway_exit = p_tags[0].text.strip() if len(p_tags) > 0 else ""

            # Extract highway route 
            match = re.search(r'Hwy\s+([A-Z]+)[\s\-]+([0-9A-Z]+)', highway_exit)    # Running search against multiple Regex patterns (including spaces)
            highway_route = f"{match.group(1)}-{match.group(2)}" if match else ''   # Specifically targeting Interstate and Highway routes

            # Extract exit
            exit_num = ''
            if 'Exit' in highway_exit:
                exit_match = re.search(r'Exit\s*([A-Za-z0-9\-]+)', highway_exit)
                if exit_match:
                    exit_num = f"Exit {exit_match.group(1)}"

            # Extract number of truck parking spots
            truck_parking_spots = 0
            for p in p_tags:
                if '# Truck Parking Spots:' in p.text:
                    try:
                        truck_parking_spots = int(re.search(r'# Truck Parking Spots:\s*(\d+)', p.text).group(1))
                    except:
                        truck_parking_spots = 0
                    break

            if truck_parking_spots == 0:
                continue  # Skip if no parking spots

            # Build address and stop before (TRAVEL CENTER) or fuel stats
            address_lines = []
            for p in p_tags[1:]:
                line = p.text.strip()
                if '(TRAVEL CENTER)' in line or '# Showers' in line or '# Fuel Lanes' in line:
                    break
                address_lines.append(line)
            address = ' '.join(address_lines)

            # Store clean data
            data.append({
                'State': state,
                'Truck Stop Name': name,
                'Highway Route': highway_route,
                'Exit': exit_num,
                'Address': address
            })

        except Exception as e:
            print(f"Error extracting data: {e}")

# Save to CSV
df = pd.DataFrame(data)
df.to_csv(f"{state}_truck_stops.csv", index=False, encoding='utf-8')
print(f"\nScraping complete. Saved {len(df)} truck stops to {state}_truck_stops.csv")

driver.quit()
