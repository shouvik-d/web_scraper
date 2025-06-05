import pandas as pd
from collections import defaultdict
import yaml
import os

def generate_interstate_configs_from_excel(excel_path, output_dir: str = "./configs"):
    os.makedirs(output_dir, exist_ok=True)

    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        print(f" Failed to read Excel file: {e}")
        return

    def split_coords(coord):
        lat, lon = coord.strip().split(',')
        return float(lat), float(lon)

    grouped_configs = defaultdict(dict)

    for index, row in df.iterrows():
        try:
            route = int(row["route_number"])
            key = f"I-{route}"
            
            if key not in grouped_configs:
                # Initialize base config for this route
                grouped_configs[key] = {
                    "global_parameters": {
                        "time_step": 1,
                        "betEnergy_path": "./data/electric_trucks.csv",
                        "output_folder": "./temp_output",
                        "google_api_folder": "./google api",
                        "act2_avg_tonnage": 13,
                        "act3_avg_tonnage": 27,
                        "truck_days_in_year": 300,
                        "faf_year": 2023,
                    },
                    "simulation_varying_parameters": {
                        "act_cat_1_charge_rate": 19,
                        "act_cat_2_charge_rate": 150,
                        "act_cat_3_charge_rate": 450,
                        "AC": ["High"],
                        "market_adoption_rate": [1],
                        "charging_logic": ["upon depot arrival"]
                    },
                    "long_haul": {
                        "interstate": {
                            "name": key,
                            "nw_metro_station": "West Virginia",
                            "pt_nw_lat": 39.663552,
                            "pt_nw_lon": -79.476611,
                            "se_metro_station": "Baltimore",
                            "pt_se_lat": 39.71043103599872,
                            "pt_se_lon": -78.18724432872503
                        },
                        "SOC_threshold": 0.3,
                        "truck_arrival_distribution_path": "./data/longhaul/truck_stop_arrival_distribution.csv",
                        "routes_path": "./data/longhaul/od_routing_2023.pkl",
                        "scenario_data": "./data/scenario_data_MD.csv"
                    },
                    f"{key}_stations": {}
                }
            
            # Fix the name formatting to include hyphen
            station_name = f"{row['name']} - {row['address'].split(',')[0]}"
            lat_c, lon_c = split_coords(row["center_coords"])
            lat_n, lon_n = split_coords(row["north_coordinates"])
            lat_s, lon_s = split_coords(row["south_coordinates"])
            act2 = int(row["aadt_single_unit"])
            act3 = int(row["aadt_combination"])
            proximity = float(row["Proximity factor"])

            station_data = {
                "name": station_name,  # Now includes hyphen
                "id": f"ET-{row['id']}",
                "capture_rate": round(0.1 * proximity, 4),
                "center": {"lat": lat_c, "lon": lon_c},
                "north/west": {"lat": lat_n, "lon": lon_n},
                "south/east": {"lat": lat_s, "lon": lon_s},
                "hpms": {"act2": act2, "act3": act3}
            }

            grouped_configs[key][f"{key}_stations"][row["name"]] = station_data

        except KeyError as e:
            print(f"  Skipping row {index} — missing column: {e}")
            continue
        except ValueError as e:
            print(f"  Skipping row {index} — invalid value format: {e}")
            continue
        except Exception as e:
            print(f"  Skipping row {index} — unknown error: {e}")
            continue

    # Custom YAML formatting
    def write_yaml_section(f, data, indent_level=0, is_list=False):
        indent = ' ' * indent_level
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict):
                    f.write(f"{indent}{k}:\n")
                    write_yaml_section(f, v, indent_level + 2)
                elif isinstance(v, list):
                    f.write(f"{indent}{k}: {v}\n")
                else:
                    f.write(f"{indent}{k}: {v}\n")
        else:
            f.write(f"{indent}{data}\n")

    # Save configs with exact formatting
    for route_key, config in grouped_configs.items():
        output_path = os.path.join(output_dir, f"{route_key}.yaml")
        try:
            with open(output_path, 'w') as f:
                # Write header
                f.write("# General Urban CDS parameters\n")
                
                # Global parameters
                f.write("global_parameters:\n")
                f.write(" time_step: 1 # pct of hour\n")
                global_params = config["global_parameters"]
                for k in ["betEnergy_path", "output_folder", "google_api_folder", 
                         "act2_avg_tonnage", "act3_avg_tonnage", "truck_days_in_year", "faf_year"]:
                    f.write(f" {k}: {global_params[k]}\n")
                
                # Simulation parameters
                f.write("\nsimulation_varying_parameters:\n")
                sim_params = config["simulation_varying_parameters"]
                f.write(f" act_cat_1_charge_rate: {sim_params['act_cat_1_charge_rate']} \n")
                f.write(f" act_cat_2_charge_rate: {sim_params['act_cat_2_charge_rate']} \n")
                f.write(f" act_cat_3_charge_rate: {sim_params['act_cat_3_charge_rate']} # in kW\n")
                f.write(f" AC: ['High']\n")
                f.write(f" market_adoption_rate: [1]\n")
                f.write(f" charging_logic: ['upon depot arrival']\n")
                
                # Stations
                stations_key = f"{route_key}_stations"
                f.write(f" {stations_key}:\n")
                for station_name, station_data in config[stations_key].items():
                    f.write(f"  {station_name}:\n")
                    for k, v in station_data.items():
                        if isinstance(v, dict):
                            f.write(f"    {k}:\n")
                            for sub_k, sub_v in v.items():
                                f.write(f"      {sub_k}: {sub_v}\n")
                        else:
                            # Handle quotes for string values
                            if isinstance(v, str):
                                v = f"'{v}'"
                            f.write(f"    {k}: {v}\n")
                
                # Long haul section
                f.write("\n# General Long-haul CDS parameters\n")
                f.write("long_haul:\n")
                f.write(" interstate:\n")
                for k, v in config["long_haul"]["interstate"].items():
                    f.write(f"  {k}: {v}\n")
                for k, v in config["long_haul"].items():
                    if k != "interstate":
                        f.write(f" {k}: {v}\n")
                
            print(f" Saved: {output_path}")
        except Exception as e:
            print(f" Failed to save {route_key} config: {e}")

# Example usage:



def main():
    print("\nExcel file path is a necessary input field")
    print("Output files directory path is not neccessary, but can be specified ( Default = .\configs in the current working directory )")
    print("If an output directory is not specified, Default location will be used ( created if non existent )")
    print(r"Example input file path: C:\Users\JANEDOE\Desktop\FILENAME.xlsx")
    excel_path = input("Enter full path to excel file, without any quotes, ending with the file name + .xlsx: ").strip()
    generate_interstate_configs_from_excel(excel_path)


if __name__ == "__main__":
    main()