from flask import Flask, request, jsonify

app = Flask(__name__)

# Словарь для хранения данных
currency_data = {}

@app.route('/add_currency', methods=['POST'])
def add_currency():
    data = request.json
    currency = data.get('currency')
    price = data.get('price')
    if currency and price:
        currency_data[currency] = price
        return jsonify({'message': 'Data added successfully'}), 200
    else:
        return jsonify({'error': 'Invalid data'}), 400

if __name__ == '__main__':
    app.run(debug=True)

