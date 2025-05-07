import pandas as pd
import random
import pickle
import numpy as np
from datetime import datetime

# Brand-specific models
brand_models = {
    "Honda": ["CBR 150", "Shine", "Activa 125"],
    "Yamaha": ["FZ-S", "R15", "Fascino"],
    "Suzuki": ["Gixxer", "Access 125", "Intruder"],
    "Bajaj": ["Pulsar 220", "Avenger 220", "Platina 100"],
    "Royal Enfield": ["Classic 350", "Bullet 500", "Meteor 350"],
    "KTM": ["Duke 200", "RC 390", "Adventure 250"]
}

years = list(range(2015, 2024))
engine_capacity = [100, 125, 150, 200, 250, 350, 500]
mileage = [35, 40, 45, 50, 55, 60, 65]
conditions = ["Excellent", "Good", "Fair"]

data = []
for _ in range(2000):
    brand = random.choice(list(brand_models.keys()))
    model = random.choice(brand_models[brand])
    year = random.choice(years)
    engine = random.choice(engine_capacity)
    km_driven = random.randint(5000, 80000)
    mileage_val = random.choice(mileage)
    condition = random.choice(conditions)
    base_price = random.randint(30000, 150000)

    # Calculate factors
    engine_factor = 0.7 + (engine - min(engine_capacity)) / (max(engine_capacity) - min(engine_capacity)) * 0.6
    km_factor = 1.2 - (km_driven - 5000) / (80000 - 5000) * 0.6
    mileage_factor = 0.8 + (mileage_val - min(mileage)) / (max(mileage) - min(mileage)) * 0.4
    year_factor = 0.8 + (year - min(years)) / (max(years) - min(years)) * 0.4

    condition_factor = {
        "Excellent": 1.2,
        "Good": 1.0,
        "Fair": 0.8
    }[condition]

    final_price = int(base_price * engine_factor * km_factor * mileage_factor * year_factor * condition_factor)

    data.append([brand, model, year, engine, km_driven, mileage_val, condition, final_price])

# Create DataFrame
df = pd.DataFrame(data, columns=["Brand", "Model", "Year", "Engine_CC", "KM_Driven", "Mileage_KMPL", "Condition", "Price"])

# Save to CSV
df.to_csv("used_bike_data.csv", index=False)

# Calculate additional statistics
stats = {
    'timestamp': datetime.now(),
    'record_count': len(df),
    'price_stats': {
        'mean': df['Price'].mean(),
        'median': df['Price'].median(),
        'min': df['Price'].min(),
        'max': df['Price'].max(),
        'std': df['Price'].std()
    },
    'correlations': {
        'engine_price': df['Engine_CC'].corr(df['Price']),
        'km_price': df['KM_Driven'].corr(df['Price']),
        'mileage_price': df['Mileage_KMPL'].corr(df['Price']),
        'year_price': df['Year'].corr(df['Price'])
    },
    'brand_distribution': df['Brand'].value_counts().to_dict(),
    'condition_distribution': df['Condition'].value_counts().to_dict(),
    'avg_price_by_brand': df.groupby('Brand')['Price'].mean().to_dict(),
    'avg_price_by_condition': df.groupby('Condition')['Price'].mean().to_dict(),
    'avg_price_by_engine': df.groupby('Engine_CC')['Price'].mean().to_dict()
}

# Create a dictionary with both DataFrame and statistics
dataset_package = {
    'data': df,
    'statistics': stats,
    'metadata': {
        'brand_models': brand_models,
        'years_range': [min(years), max(years)],
        'engine_capacity_range': [min(engine_capacity), max(engine_capacity)],
        'mileage_range': [min(mileage), max(mileage)],
        'conditions': conditions
    }
}

# Save to pickle file
pickle_filename = 'bike_dataset.pkl'
with open(pickle_filename, 'wb') as f:
    pickle.dump(dataset_package, f)

# Print summary information
print("\nDataset Summary:")
print(f"Total number of records: {stats['record_count']}")

print("\nPrice Statistics (in Rupees):")
print(f"Average price: ₹{stats['price_stats']['mean']:.2f}")
print(f"Median price: ₹{stats['price_stats']['median']:.2f}")
print(f"Minimum price: ₹{stats['price_stats']['min']:.2f}")
print(f"Maximum price: ₹{stats['price_stats']['max']:.2f}")
print(f"Standard deviation: ₹{stats['price_stats']['std']:.2f}")

print("\nCorrelations with Price:")
for factor, corr in stats['correlations'].items():
    print(f"{factor}: {corr:.3f}")

print("\nBike Conditions Distribution:")
print(df['Condition'].value_counts())

print("\nBrand Distribution:")
print(df['Brand'].value_counts())

print("\nAverage Prices by Engine Capacity:")
print(df.groupby('Engine_CC')['Price'].mean().sort_values(ascending=True))

print(f"\nDataset saved to {pickle_filename}")

# Example of how to load the pickle file
print("\nDemonstrating pickle file loading:")
with open(pickle_filename, 'rb') as f:
    loaded_data = pickle.load(f)
    
print("\nPickle file contents:")
print("Keys:", list(loaded_data.keys()))
print("Number of records:", len(loaded_data['data']))
print("Available statistics:", list(loaded_data['statistics'].keys()))
print("Metadata:", list(loaded_data['metadata'].keys()))
