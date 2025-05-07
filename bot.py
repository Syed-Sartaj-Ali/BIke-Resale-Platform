from flask import Flask, request, jsonify
from pymongo import MongoClient
from bson import ObjectId
import os
from bike_price_model import predict_bike_price  # Import the prediction function

app = Flask(__name__)

# Hardcoded MongoDB Configuration
MONGO_URI = 'mongodb+srv://kr4785543:1234567890@cluster0.220yz.mongodb.net/'
client = MongoClient(MONGO_URI)
db = client['bike_rental']
bikes_collection = db['bikes']

@app.route('/api/bikes/search', methods=['GET'])
def search_bikes():
    try:
        # Initialize query dictionary
        query = {}
        
        # Get all query parameters
        brand = request.args.get('brand', '').strip()
        model = request.args.get('model', '').strip()
        year = request.args.get('year', type=int)
        condition = request.args.get('condition', '').strip()
        listing_type = request.args.get('listing_type', '').strip()
        price_min = request.args.get('price_min', type=float)
        price_max = request.args.get('price_max', type=float)
        engine_min = request.args.get('engine_min', type=int)
        engine_max = request.args.get('engine_max', type=int)
        km_driven_max = request.args.get('km_driven_max', type=int)

        # Build query based on provided parameters
        if brand:
            query['brand'] = {'$regex': brand, '$options': 'i'}
        if model:
            query['model'] = {'$regex': model, '$options': 'i'}
        if year:
            query['year'] = year
        if condition:
            query['condition'] = {'$regex': condition, '$options': 'i'}
        if listing_type:
            query['listing_type'] = listing_type

        # Price range
        if price_min is not None or price_max is not None:
            query['sale_price'] = {}
            if price_min is not None:
                query['sale_price']['$gte'] = price_min
            if price_max is not None:
                query['sale_price']['$lte'] = price_max

        # Engine capacity range
        if engine_min is not None or engine_max is not None:
            query['engine_cc'] = {}
            if engine_min is not None:
                query['engine_cc']['$gte'] = engine_min
            if engine_max is not None:
                query['engine_cc']['$lte'] = engine_max

        # Maximum kilometers driven
        if km_driven_max is not None:
            query['km_driven'] = {'$lte': km_driven_max}

        # Execute search
        bikes = bikes_collection.find(query)

        # Format results
        results = []
        for bike in bikes:
            bike['_id'] = str(bike['_id'])  # Convert ObjectId to string
            results.append({
                'id': bike['_id'],
                'brand': bike['brand'],
                'model': bike['model'],
                'year': bike['year'],
                'condition': bike['condition'],
                'engine_cc': bike.get('engine_cc'),
                'km_driven': bike.get('km_driven'),
                'listing_type': bike['listing_type'],
                'sale_price': bike.get('sale_price'),
                'price_per_day': bike.get('price_per_day'),
                'created_at': bike['created_at'].isoformat() if 'created_at' in bike else None,
                'metadata': bike.get('metadata', {})
            })

        return jsonify({
            'status': 'success',
            'count': len(results),
            'bikes': results
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/bikes/<bike_id>/analyze', methods=['GET'])
def analyze_bike(bike_id):
    try:
        # Convert string ID to MongoDB ObjectId
        # First try with SQL ID
        bike = bikes_collection.find_one({'sql_id': int(bike_id)})
        
        # If not found, try with MongoDB ObjectId
        if not bike:
            try:
                bike = bikes_collection.find_one({'_id': ObjectId(bike_id)})
            except:
                return jsonify({
                    'success': False,
                    'message': 'Invalid bike ID format'
                }), 400

        if not bike:
            return jsonify({
                'success': False,
                'message': 'Bike not found'
            }), 404

        # Get the required parameters for prediction
        params = {
            'brand': bike['brand'],
            'model': bike['model'],
            'year': int(bike['year']),  # Ensure numeric
            'engine_cc': int(bike['engine_cc']),  # Ensure numeric
            'km_driven': int(bike['km_driven']),  # Ensure numeric
            'mileage': float(bike['mileage']),  # Ensure numeric
            'condition': bike['condition']
        }

        # Print parameters for debugging
        print("Prediction parameters:", params)

        # Get estimated price from the AI model
        estimated_price = predict_bike_price(**params)

        return jsonify({
            'success': True,
            'estimated_price': float(estimated_price),  # Ensure it's serializable
            'actual_price': float(bike['sale_price']),  # Ensure it's serializable
            'parameters': params
        }), 200

    except Exception as e:
        print(f"Analysis error: {str(e)}")  # Add error logging
        return jsonify({
            'success': False,
            'message': f"Analysis error: {str(e)}"
        }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5008))
    app.run(host='0.0.0.0', port=port)



