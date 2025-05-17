from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import tensorflow as tf
import numpy as np
from PIL import Image
import io
import base64

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database connection
conn = mysql.connector.connect(host='localhost', user='root', password='', database='wasla_project')
cursor = conn.cursor()

# Load the machine learning model
try:
    model = tf.keras.models.load_model('models/sign_language_model.h5')
except Exception as e:
    print(f"Error loading model: {e}")
    model = None

# Dictionary for digit translations (English and Arabic)
DIGIT_TRANSLATIONS = {
    0: {'english': 'Zero', 'arabic': 'صفر'},
    1: {'english': 'One', 'arabic': 'واحد'},
    2: {'english': 'Two', 'arabic': 'اثنان'},
    3: {'english': 'Three', 'arabic': 'ثلاثة'},
    4: {'english': 'Four', 'arabic': 'أربعة'},
    5: {'english': 'Five', 'arabic': 'خمسة'},
    6: {'english': 'Six', 'arabic': 'ستة'},
    7: {'english': 'Seven', 'arabic': 'سبعة'},
    8: {'english': 'Eight', 'arabic': 'ثمانية'},
    9: {'english': 'Nine', 'arabic': 'تسعة'}
}

# Image preprocessing function
def preprocess_image(image):
    image = image.resize((64, 64))
    image_array = np.array(image)
    if image_array.shape[-1] != 3:
        image_array = np.stack((image_array,) * 3, axis=-1)
    image_array = image_array / 255.0
    image_array = np.expand_dims(image_array, axis=0)
    return image_array

# Existing routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/login_validation', methods=['POST'])
def login_validation():
    username = request.form.get('username')
    password = request.form.get('password')
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    if user:
        if check_password_hash(user[5], password):
            session['user_id'] = user[0]
            return redirect(url_for('camera'))
        else:
            flash('Incorrect password. Please try again.', 'danger')
            return redirect(url_for('login'))
    else:
        flash('Username not found. Please register.', 'warning')
        return redirect(url_for('register'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        username = request.form.get('username')
        phone_number = request.form.get('phone_number')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if password != confirm_password:
            flash("Passwords do not match. Please try again.", "danger")
            return redirect(url_for('register'))
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if user:
            flash("Username already exists. Please use a different username.", "warning")
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        try:
            cursor.execute("""
                INSERT INTO users (first_name, last_name, username, phone_number, password)
                VALUES (%s, %s, %s, %s, %s)
            """, (first_name, last_name, username, phone_number, hashed_password))
            conn.commit()
            flash('Registration successful! You can now login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('An error occurred during registration. Please try again.', 'danger')
            print(f"Error: {e}")
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username')
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if user:
            return render_template('reset_password.html', username=username)
        else:
            flash("Username not found. Please register.", "warning")
            return redirect(url_for('register'))
    return render_template('forgot_password.html')

@app.route('/reset_password', methods=['POST'])
def reset_password():
    username = request.form.get('username')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    if new_password != confirm_password:
        flash("Passwords do not match. Try again.", "danger")
        return render_template('reset_password.html', username=username)
    hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')
    try:
        cursor.execute("UPDATE users SET password = %s WHERE username = %s", (hashed_password, username))
        conn.commit()
        flash("Password reset successfully! You can now login.", "success")
        return redirect(url_for('login'))
    except Exception as e:
        print("Error updating password:", e)
        flash("An error occurred. Please try again.", "danger")
        return render_template('reset_password.html', username=username)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        flash('Please log in to access your profile.', 'warning')
        return redirect(url_for('login'))
    user_id = session['user_id']
    cursor.execute("SELECT first_name, last_name, username, phone_number FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.execute("SELECT id, comment, timestamp FROM feedback WHERE user_id = %s ORDER BY timestamp DESC", (user_id,))
    feedback = [type('Feedback', (), {'id': row[0], 'comment': row[1], 'timestamp': row[2]}) for row in cursor.fetchall()]
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        username = request.form.get('username')
        phone_number = request.form.get('phone_number')
        password = request.form.get('password')
        try:
            if password:
                hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
                cursor.execute("""
                    UPDATE users SET first_name = %s, last_name = %s, username = %s, phone_number = %s, password = %s
                    WHERE id = %s
                """, (first_name, last_name, username, phone_number, hashed_password, user_id))
            else:
                cursor.execute("""
                    UPDATE users SET first_name = %s, last_name = %s, username = %s, phone_number = %s
                    WHERE id = %s
                """, (first_name, last_name, username, phone_number, user_id))
            conn.commit()
            flash('Profile updated successfully!', 'success')
        except Exception as e:
            flash('Error updating profile.', 'danger')
            print(f"Error: {e}")
        return redirect(url_for('profile'))
    return render_template('profile.html', user=user, feedback=feedback)

    
@app.route('/history')
def history():
    if 'user_id' not in session:
        flash('Please log in to view your history.', 'warning')
        return redirect(url_for('login'))
    cursor.execute("SELECT id, message, timestamp FROM translations WHERE user_id = %s ORDER BY timestamp DESC", (session['user_id'],))
    translations = [type('Translation', (), {'id': row[0], 'message': row[1], 'timestamp': row[2]}) for row in cursor.fetchall()]
    return render_template('history.html', translations=translations)

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    if 'user_id' not in session:
        flash('Please log in to submit feedback.', 'warning')
        return redirect(url_for('login'))
    user_id = session['user_id']
    comment = request.form.get('comment', '').strip()
    try:
        cursor.execute("""
            INSERT INTO feedback (user_id, comment, timestamp)
            VALUES (%s, %s, %s)
        """, (user_id, comment, datetime.now()))
        conn.commit()
        flash('Feedback submitted successfully!', 'success')
    except Exception as e:
        flash('Error submitting feedback.', 'danger')
        print(f"Error: {e}")
    return redirect(url_for('profile'))

@app.route('/camera', methods=['GET', 'POST'])
def camera():
    if 'user_id' not in session:
        flash('Please log in to access the camera.', 'warning')
        return redirect(url_for('login'))
    return render_template('camera.html')

# New route for webcam prediction
@app.route('/predict_camera', methods=['POST'])
def predict_camera():
    if 'user_id' not in session:
        flash('Please log in to access the camera.', 'warning')
        return redirect(url_for('login'))
    
    if not model:
        flash('Model not loaded. Please contact the administrator.', 'danger')
        return redirect(url_for('camera'))
    
    # Get the base64 image data
    image_data = request.form.get('image_data')
    if not image_data:
        flash('No image captured.', 'danger')
        return redirect(url_for('camera'))
    
    # Decode base64 image
    try:
        image_data = image_data.split(',')[1]  # Remove "data:image/jpeg;base64,"
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        flash('Error processing image.', 'danger')
        print(f"Error: {e}")
        return redirect(url_for('camera'))
    
    # Preprocess and predict
    image_array = preprocess_image(image)
    prediction = model.predict(image_array)
    predicted_digit = np.argmax(prediction, axis=1)[0]
    
    # Get bilingual prediction
    prediction_text = DIGIT_TRANSLATIONS[predicted_digit]
    
    # Save prediction to translations table
    try:
        cursor.execute("""
            INSERT INTO translations (user_id, message, timestamp)
            VALUES (%s, %s, %s)
        """, (session['user_id'], f"{prediction_text['english']} ({prediction_text['arabic']})", datetime.now()))
        conn.commit()
    except Exception as e:
        flash('Error saving prediction.', 'danger')
        print(f"Error: {e}")
    
    return render_template('camera.html', prediction=prediction_text)

@app.route('/submit_prediction', methods=['POST'])
def submit_prediction():
    if 'user_id' not in session:
        flash('Please log in to submit predictions.', 'warning')
        return redirect(url_for('login'))
    
    prediction_english = request.form.get('prediction_english')
    prediction_arabic = request.form.get('prediction_arabic')
    if not prediction_english or not prediction_arabic:
        flash('Invalid prediction data.', 'danger')
        return redirect(url_for('camera'))
    
    # Save prediction to translations table
    try:
        cursor.execute("""
            INSERT INTO translations (user_id, message, timestamp)
            VALUES (%s, %s, %s)
        """, (session['user_id'], f"{prediction_english} ({prediction_arabic})", datetime.now()))
        conn.commit()
        flash('Prediction saved successfully!', 'success')
    except Exception as e:
        flash('Error saving prediction.', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('camera'))

@app.route('/delete_history', methods=['POST'])
def delete_history():
    if 'user_id' not in session:
        flash('Please log in to delete history.', 'warning')
        return redirect(url_for('login'))
    
    try:
        cursor.execute("DELETE FROM translations WHERE user_id = %s", (session['user_id'],))
        conn.commit()
        flash('Translation history deleted successfully!', 'success')
    except Exception as e:
        flash('Error deleting history.', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('history'))

@app.route('/delete_translation', methods=['POST'])
def delete_translation():
    if 'user_id' not in session:
        flash('Please log in to delete translations.', 'warning')
        return redirect(url_for('login'))
    
    translation_id = request.form.get('translation_id')
    if not translation_id:
        flash('Invalid translation ID.', 'danger')
        return redirect(url_for('history'))
    
    try:
        cursor.execute("DELETE FROM translations WHERE id = %s AND user_id = %s", (translation_id, session['user_id']))
        conn.commit()
        if cursor.rowcount == 0:
            flash('Translation not found or not authorized.', 'danger')
        else:
            flash('Translation deleted successfully!', 'success')
    except Exception as e:
        flash('Error deleting translation.', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('history'))

@app.route('/delete_feedback', methods=['POST'])
def delete_feedback():
    if 'user_id' not in session:
        flash('Please log in to delete feedback.', 'warning')
        return redirect(url_for('login'))
    
    feedback_id = request.form.get('feedback_id')
    if not feedback_id:
        flash('Invalid feedback ID.', 'danger')
        return redirect(url_for('profile'))
    
    try:
        cursor.execute("DELETE FROM feedback WHERE id = %s AND user_id = %s", (feedback_id, session['user_id']))
        conn.commit()
        if cursor.rowcount == 0:
            flash('Feedback not found or not authorized.', 'danger')
        else:
            flash('Feedback deleted successfully!', 'success')
    except Exception as e:
        flash('Error deleting feedback.', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('profile'))

@app.route('/delete_all_feedback', methods=['POST'])
def delete_all_feedback():
    if 'user_id' not in session:
        flash('Please log in to delete feedback.', 'warning')
        return redirect(url_for('login'))
    
    try:
        cursor.execute("DELETE FROM feedback WHERE user_id = %s", (session['user_id'],))
        conn.commit()
        flash('All feedback deleted successfully!', 'success')
    except Exception as e:
        flash('Error deleting feedback.', 'danger')
        print(f"Error: {e}")
    
    return redirect(url_for('profile'))

if __name__ == "__main__":
    app.run(debug=True)