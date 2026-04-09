import argparse
import random
import time
import os

class Colony:
    def __init__(self, name, environment):
        self.name = name
        self.environment = environment
        self.buildings = []

    def add_building(self, building):
        self.buildings.append(building)

class Building:
    def __init__(self, name, sustainability_rating):
        self.name = name
        self.sustainability_rating = sustainability_rating

def create_colony(colony_name, environment):
    new_colony = Colony(colony_name, environment)
    print(f"Creating colony: {new_colony.name} in {new_colony.environment}")
    for i in range(5):
        new_building = Building(f"Building_{i}", random.randint(1, 10))
        new_colony.add_building(new_building)
        print(f"Added building: {new_building.name} with sustainability rating: {new_building.sustainability_rating}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("colony_name", help="Name of the colony")
    parser.add_argument("environment", choices=["desert", "polar"], help="Environment for the colony")
    args = parser.parse_args()

    create_colony(args.colony_name, args.environment)

if __name__ == "__main__":
    os.chdir(os.path.abspath(os.path.join(os.getcwd(), "..")))  # Change the current working directory to the parent folder
    main()