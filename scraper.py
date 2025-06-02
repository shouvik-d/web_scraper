from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time

# Setting up the webdriver with the website link
driver = webdriver.Chrome()
driver.get("https://www.truckstopsandservices.com/truckstop-directory2.php")
wait = WebDriverWait(driver, 15)

#Initial state input ( currently unused except for final file name )
state = 'CO'

# selecting the desired state
Select(wait.until(EC.presence_of_element_located((By.ID, "state_selector")))).select_by_visible_text("CO - Colorado")
time.sleep(2)

# selects truck stops tab from the drop down.
Select(wait.until(EC.presence_of_element_located((By.ID, "cat_selector")))).select_by_visible_text("Truck Stops")
time.sleep(2)

# getting all highway selections
highway_dropdown = wait.until(EC.presence_of_element_located((By.ID, "highway_selector")))
highway_options = [
    option.get_attribute("value")
    for option in highway_dropdown.find_elements(By.TAG_NAME, "option")
    if option.get_attribute("value")
]

data = []

# Looping through each highway 
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

            # Get all <p> tags (location info)
            p_tags = row.find_all('p')

            # Highway and Exit
            highway_exit = p_tags[0].text.strip() if len(p_tags) > 0 else ""

            highway_route = ''
            exit_num = ''

            if 'Hwy' in highway_exit:
                split_info = highway_exit.replace('Hwy', '').strip().split('-')
                if len(split_info) >= 1:
                    highway_route = split_info[0].strip()
                if 'Exit' in highway_exit:
                    exit_split = highway_exit.split('Exit')
                    if len(exit_split) > 1:
                        exit_num = 'Exit ' + exit_split[1].strip()

            # Address lines (combine remaining <p> text)
            address_lines = [p.text.strip() for p in p_tags[1:]]
            address = ' '.join(address_lines)

            #appending all the truck stop info in the data list
            data.append({
                'State': state,
                'Truck Stop Name': name,
                'Highway Route': highway_route,
                'Exit': exit_num,
                'Address': address
            })

        except Exception as e:
            print(f"Error extracting data: {e}")

# saving all the data as a CSV file in 
df = pd.DataFrame(data)
df.to_csv(f"{state}_truck_stops.csv", index=False, encoding='utf-8')
print(f"\n Scraping complete. Saved {len(df)} truck stops to {state}_truck_stops.csv")

driver.quit()
