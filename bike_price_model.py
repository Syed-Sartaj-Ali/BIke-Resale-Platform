import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import matplotlib.pyplot as plt
import seaborn as sns
import joblib

# Load the dataset
df = pd.read_csv('used_bike_data.csv')

# Data Analysis
print("\nDataset Info:")
print(df.info())

print("\nBasic Statistics:")
print(df.describe())

print("\nMissing Values:")
print(df.isnull().sum())

# Feature Engineering
# Convert categorical variables to numerical
le_brand = LabelEncoder()
le_model = LabelEncoder()
le_condition = LabelEncoder()

df['Brand_Encoded'] = le_brand.fit_transform(df['Brand'])
df['Model_Encoded'] = le_model.fit_transform(df['Model'])
df['Condition_Encoded'] = le_condition.fit_transform(df['Condition'])

# Create feature matrix X and target variable y
X = df[[
    'Brand_Encoded',
    'Model_Encoded',
    'Year',
    'Engine_CC',
    'KM_Driven',
    'Mileage_KMPL',
    'Condition_Encoded'
]]

y = df['Price']

# Split the data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Scale the features
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Train Random Forest model
rf_model = RandomForestRegressor(
    n_estimators=100,
    max_depth=10,
    min_samples_split=5,
    min_samples_leaf=2,
    random_state=42
)

rf_model.fit(X_train_scaled, y_train)

# Make predictions
y_pred = rf_model.predict(X_test_scaled)

# Model Evaluation
mse = mean_squared_error(y_test, y_pred)
rmse = np.sqrt(mse)
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print("\nModel Performance Metrics:")
print(f"Root Mean Squared Error: ₹{rmse:.2f}")
print(f"Mean Absolute Error: ₹{mae:.2f}")
print(f"R² Score: {r2:.4f}")

# Cross-validation
cv_scores = cross_val_score(rf_model, X_train_scaled, y_train, cv=5)
print("\nCross-validation scores:", cv_scores)
print("Average CV score:", cv_scores.mean())

# Feature Importance
feature_importance = pd.DataFrame({
    'feature': X.columns,
    'importance': rf_model.feature_importances_
})
feature_importance = feature_importance.sort_values('importance', ascending=False)

print("\nFeature Importance:")
print(feature_importance)

# Visualizations
plt.figure(figsize=(12, 6))
plt.subplot(1, 2, 1)
sns.scatterplot(x=y_test, y=y_pred)
plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'r--', lw=2)
plt.xlabel('Actual Price')
plt.ylabel('Predicted Price')
plt.title('Actual vs Predicted Prices')

plt.subplot(1, 2, 2)
sns.barplot(x='importance', y='feature', data=feature_importance)
plt.title('Feature Importance')
plt.tight_layout()
plt.show()

# Save the model and preprocessing objects
model_artifacts = {
    'model': rf_model,
    'scaler': scaler,
    'label_encoders': {
        'brand': le_brand,
        'model': le_model,
        'condition': le_condition
    }
}

joblib.dump(model_artifacts, 'bike_price_model.joblib')

# Example prediction function
def predict_bike_price(brand, model, year, engine_cc, km_driven, mileage, condition):
    # Create a DataFrame with the input data
    input_data = pd.DataFrame([[
        brand, model, year, engine_cc, km_driven, mileage, condition
    ]], columns=['Brand', 'Model', 'Year', 'Engine_CC', 'KM_Driven', 'Mileage_KMPL', 'Condition'])
    
    # Encode categorical variables
    input_data['Brand_Encoded'] = le_brand.transform([brand])
    input_data['Model_Encoded'] = le_model.transform([model])
    input_data['Condition_Encoded'] = le_condition.transform([condition])
    
    # Select features in the correct order
    X_input = input_data[[
        'Brand_Encoded',
        'Model_Encoded',
        'Year',
        'Engine_CC',
        'KM_Driven',
        'Mileage_KMPL',
        'Condition_Encoded'
    ]]
    
    # Scale the features
    X_input_scaled = scaler.transform(X_input)
    
    # Make prediction
    predicted_price = rf_model.predict(X_input_scaled)[0]
    
    return predicted_price

# Example usage
print("\nExample Prediction:")
sample_price = predict_bike_price(
    brand="Honda",
    model="CBR 150",
    year=2020,
    engine_cc=150,
    km_driven=25000,
    mileage=45,
    condition="Good"
)
print(f"Predicted price for the sample bike: ₹{sample_price:.2f}")