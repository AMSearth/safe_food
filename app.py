from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import sqlite3
import requests
import database as db

app = Flask(__name__)
app.secret_key = 'super_secret_safe_food_key'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

HF_API_URL = "https://api-inference.huggingface.co/models/google/vit-base-patch16-224"

def query_huggingface(filepath):
    try:
        with open(filepath, "rb") as f:
            data = f.read()
        response = requests.post(HF_API_URL, data=data)
        return response.json()
    except Exception as e:
        return []

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize DB on start
db.init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = db.get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = db.get_db()
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
        except sqlite3.IntegrityError:
            flash("Username already exists")
            return redirect(url_for('register'))
        finally:
            conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/medical', methods=['GET', 'POST'])
def medical():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = db.get_db()
    
    if request.method == 'POST':
        age = request.form['age']
        weight = request.form['weight']
        height = request.form['height']
        conditions = request.form['conditions']
        allergies = request.form['allergies']
        
        # Upsert logic
        profile = conn.execute('SELECT * FROM medical_profile WHERE user_id = ?', (session['user_id'],)).fetchone()
        if profile:
            conn.execute('UPDATE medical_profile SET age=?, weight=?, height=?, conditions=?, allergies=? WHERE user_id=?',
                         (age, weight, height, conditions, allergies, session['user_id']))
        else:
            conn.execute('INSERT INTO medical_profile (user_id, age, weight, height, conditions, allergies) VALUES (?, ?, ?, ?, ?, ?)',
                         (session['user_id'], age, weight, height, conditions, allergies))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
        
    profile = conn.execute('SELECT * FROM medical_profile WHERE user_id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return render_template('medical.html', profile=profile)

@app.route('/analysis', methods=['GET', 'POST'])
def analysis():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    result = None
    if request.method == 'POST':
        food_name = request.form.get('food_name', '')
        file = request.files.get('file')
        
        if file and file.filename != '':
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            
            # Use Hugging Face API Vision Model
            hf_response = query_huggingface(filepath)
            if isinstance(hf_response, list) and len(hf_response) > 0 and 'label' in hf_response[0]:
                # vit-base predictions look like "Granny Smith, apple"
                food_name = hf_response[0]['label'].split(',')[0].strip()
            else:
                food_name = "Unknown Food"
                
        if food_name:
            food_lower = food_name.lower()
            
            # Fetch user medical profile to cross-reference
            conn = db.get_db()
            profile = conn.execute('SELECT * FROM medical_profile WHERE user_id = ?', (session['user_id'],)).fetchone()
            user_allergies = profile['allergies'].lower() if profile and profile['allergies'] else ""
            
            allergy_conflict = any(allergy.strip() in food_lower for allergy in user_allergies.split(',') if allergy.strip() and allergy.strip() != 'none')
            
            if allergy_conflict:
                result = {"name": food_name.title(), "status": "Bad", "impact": "Contains an allergen specified in your medical profile! Please avoid."}
            elif 'sugar' in food_lower or 'candy' in food_lower or 'donut' in food_lower or 'pizza' in food_lower or 'chocolate' in food_lower or 'burger' in food_lower or 'hotdog' in food_lower:
                result = {"name": food_name.title(), "status": "Bad", "impact": "High empty calories and low nutritional value. Avoid for better health."}
            elif 'unknown' in food_lower:
                result = {"name": food_name.title(), "status": "Bad", "impact": "Our model couldn't identify this food. Try a clearer image."}
            else:
                result = {"name": food_name.title(), "status": "Good", "impact": "Healthy choice. Fits well with your medical profile."}
                
            if result:
                conn.execute('INSERT INTO food_logs (user_id, food_item, analysis_result) VALUES (?, ?, ?)',
                             (session['user_id'], result['name'], result['impact']))
                conn.commit()
            
            conn.close()
            
    return render_template('analysis.html', result=result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
