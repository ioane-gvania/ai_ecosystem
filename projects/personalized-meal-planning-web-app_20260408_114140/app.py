```python
from flask import Flask, render_template, jsonify, request
import os

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/data', methods=['GET'])
def get_data():
    demo_data = [{"meal": "Breakfast", "plan": "Plan 1"}, {"meal": "Lunch", "plan": "Plan 2"}]
    return jsonify(demo_data)

@app.route('/api/add', methods=['POST'])
def add_data():
    data = request.get_json()
    # Add your logic here to save the data in a database or perform any other operation
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
```
