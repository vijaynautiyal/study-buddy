from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql.expression import func
import os
from werkzeug.security import generate_password_hash, check_password_hash
import json # We need this to parse the AI's response
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser



app = Flask(__name__)
app.secret_key = "super_secret_study_buddy_key" # This locks the session data!


# AI LOGIC (Feel free to ignore this part, it's just for fun!)

# 1. Initialize LangChain with Groq (Free Tier)
# Using Llama-3.3-70b-versatile or DeepSeek-R1-Distill for high reasoning
llm = ChatGroq(
    temperature=0.7,
    groq_api_key=os.environ.get("GROQ_API_KEY"),
    model_name="llama-3.3-70b-versatile" 
)

# # Configure Gemini AI
# genai.configure(api_key="AIzaSyBxYPfkI4v3B-Rep6zb-70Tl1n_YV9Q0Qs") # <--- PASTE YOUR KEY HERE
# model = genai.GenerativeModel('gemini-2.0-flash')




# --- DATABASE CONFIGURATION ---
# This tells Python to look for a Render database FIRST. If it doesn't find one, it uses your local one!
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://postgres:GrokDeep234##@localhost/study_buddy')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- DATABASE MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False) # NEW FIELD!
    role = db.Column(db.String(20), nullable=False) 
    grade_class = db.Column(db.Integer, nullable=True) 
    reward_points = db.Column(db.Integer, default=0)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    grade_class = db.Column(db.Integer, nullable=False) # e.g., 5
    subject = db.Column(db.String(50), nullable=False)  # e.g., 'Maths'
    question_text = db.Column(db.String(500), nullable=False)
    option_a = db.Column(db.String(100), nullable=False)
    option_b = db.Column(db.String(100), nullable=False)
    option_c = db.Column(db.String(100), nullable=False)
    option_d = db.Column(db.String(100), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False) # 'A', 'B', 'C', or 'D'

class Commodity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    cost = db.Column(db.Integer, nullable=False)

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    grade_class = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(50), nullable=False)

# --- ROUTES ---

# 1. Show the Webpage
# Home Page (Login/Signup)
@app.route('/')
def home():
    # If they already have a wristband, send them straight in!
    if 'user_id' in session:
        return redirect('/parent_dashboard' if session['role'] == 'Parent' else '/student_dashboard')
    return render_template('index.html')


# 2. The API to Register Users
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    existing_user = User.query.filter_by(name=data['name'], role=data['role'], grade_class=data.get('grade_class')).first()
    if existing_user:
        return jsonify({"success": False, "message": "User already exists!"}), 400

    hashed_pw = generate_password_hash(data['password'])
    new_user = User(name=data['name'], password_hash=hashed_pw, role=data['role'], grade_class=data.get('grade_class'))
    db.session.add(new_user)
    db.session.commit()
    
    # Give them a wristband immediately!
    session['user_id'] = new_user.id
    session['name'] = new_user.name
    session['role'] = new_user.role
    session['grade_class'] = new_user.grade_class
    
    redirect_url = '/parent_dashboard' if new_user.role == 'Parent' else '/student_dashboard'
    return jsonify({"success": True, "redirect": redirect_url})

# 3. Show the Parent Dashboard
@app.route('/parent')
def parent_tool():
    if 'role' not in session or session['role'] != 'Parent': return redirect('/')
    return render_template('parent.html', session=session)

@app.route('/parent_dashboard')
def parent_dashboard():
    if 'role' not in session or session['role'] != 'Parent': return redirect('/')
    return render_template('parent_dashboard.html', session=session)

# 4. The API to Add a Question
@app.route('/api/add_question', methods=['POST'])
def add_question():
    data = request.get_json()
    
    new_question = Question(
        grade_class=int(data['grade_class']),
        subject=data['subject'],
        question_text=data['question_text'],
        option_a=data['option_a'],
        option_b=data['option_b'],
        option_c=data['option_c'],
        option_d=data['option_d'],
        correct_option=data['correct_option']
    )
    
    db.session.add(new_question)
    db.session.commit()
    
    return jsonify({"message": "Question added successfully!"}), 201

# 5. Show the Student Dashboard
@app.route('/student')
def student_arena():
    if 'role' not in session or session['role'] != 'Student': return redirect('/')
    return render_template('student.html', session=session)

# Dashboards
@app.route('/student_dashboard')
def student_dashboard():
    if 'role' not in session or session['role'] != 'Student': return redirect('/')
    return render_template('student_dashboard.html', session=session)

# 6. The API to Get a Random Question
@app.route('/api/get_question', methods=['GET'])
def get_question():
    grade = request.args.get('grade_class')
    subject = request.args.get('subject')
    
    # Search the database for a random question matching the grade and subject
    question = Question.query.filter_by(grade_class=grade, subject=subject).order_by(func.random()).first()
    
    if not question:
        return jsonify({"error": "No questions found for this subject yet!"}), 404
        
    # Send the question to the website (but hide the correct answer!)
    return jsonify({
        "id": question.id,
        "question_text": question.question_text,
        "option_a": question.option_a,
        "option_b": question.option_b,
        "option_c": question.option_c,
        "option_d": question.option_d
    })

# 7. The API to Check the Answer and Give Points
@app.route('/api/check_answer', methods=['POST'])
def check_answer():
    data = request.get_json()
    
    question = Question.query.get(data['question_id'])
    user = User.query.filter_by(name=data['student_name'], role='Student').first()
    
    if not user:
        return jsonify({"message": "Student not found! Did you sign up?", "correct": False})
        
    if question.correct_option == data['selected_option']:
        user.reward_points += 10  # 🌟 Give 10 points!
        db.session.commit()
        return jsonify({"message": f"Correct! +10 Points! (Total: {user.reward_points}) 🍫", "correct": True})
    else:
        return jsonify({"message": f"Oops! The correct answer was {question.correct_option}.", "correct": False})


# 8. Show the Student Display Window
@app.route('/shop')
def shop():
    if 'role' not in session or session['role'] != 'Student': return redirect('/')
    return render_template('shop.html', session=session)

# 9. Show the Parent Shop Control Center
@app.route('/parent_shop')
def parent_shop():
    if 'role' not in session or session['role'] != 'Parent': return redirect('/')
    return render_template('parent_shop.html', session=session)

# 10. API to Fetch All Commodities
@app.route('/api/commodities', methods=['GET'])
def get_commodities():
    items = Commodity.query.all()
    return jsonify([{"id": i.id, "name": i.name, "cost": i.cost} for i in items])

# 11. API for Parents to Add a Commodity (UPGRADED: No Duplicates)
@app.route('/api/add_commodity', methods=['POST'])
def add_commodity():
    data = request.get_json()
    item_name = data['name'].strip() # Removes accidental spaces
    
    # Check if item exists (case-insensitive)
    existing_item = Commodity.query.filter(func.lower(Commodity.name) == func.lower(item_name)).first()
    
    if existing_item:
        return jsonify({"success": False, "message": f"'{existing_item.name}' already exists in the shop!"})
        
    new_item = Commodity(name=item_name, cost=int(data['cost']))
    db.session.add(new_item)
    db.session.commit()
    return jsonify({"success": True, "message": f"{item_name} added successfully!"})

# 11A. API to Delete a Commodity
@app.route('/api/delete_commodity/<int:item_id>', methods=['DELETE'])
def delete_commodity(item_id):
    item = Commodity.query.get(item_id)
    if item:
        db.session.delete(item)
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False}), 404

# 11B. API to Update a Commodity's Cost
@app.route('/api/update_commodity', methods=['PUT'])
def update_commodity():
    data = request.get_json()
    item = Commodity.query.get(data['id'])
    if item:
        item.cost = int(data['cost'])
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False}), 404

# 12. API for Parents to Deduct Points (NOW WITH CLASS FILTER)
@app.route('/api/parent_redeem', methods=['POST'])
def parent_redeem():
    data = request.get_json()
    
    # Search by BOTH name and grade_class
    user = User.query.filter_by(
        name=data['student_name'], 
        grade_class=data['grade_class'], 
        role='Student'
    ).first()
    
    if not user:
        return jsonify({"success": False, "message": f"Student not found in Class {data['grade_class']}!"})

    cost = int(data['cost'])
    if user.reward_points >= cost:
        user.reward_points -= cost
        db.session.commit()
        return jsonify({"success": True, "message": f"Success! Deducted {cost} points. {user.name} now has {user.reward_points} left."})
    else:
        return jsonify({"success": False, "message": f"Not enough points! {user.name} only has {user.reward_points} points."})

# 13. API to Check Student Balance (NOW WITH CLASS FILTER)
@app.route('/api/balance', methods=['GET'])
def get_balance():
    student_name = request.args.get('name')
    grade_class = request.args.get('grade')
    
    # Search by BOTH name and grade_class
    user = User.query.filter_by(
        name=student_name, 
        grade_class=grade_class, 
        role='Student'
    ).first()
    
    if not user:
        return jsonify({"error": "Student not found"}), 404
    return jsonify({"name": user.name, "points": user.reward_points})


# 14. API to Fetch Subjects for a Specific Class
@app.route('/api/subjects/<int:grade>', methods=['GET'])
def get_subjects(grade):
    subjects = Subject.query.filter_by(grade_class=grade).all()
    return jsonify([{"id": s.id, "name": s.name} for s in subjects])

# 15. API for Parents to Add a Subject
@app.route('/api/add_subject', methods=['POST'])
def add_subject():
    data = request.get_json()
    grade = int(data['grade_class'])
    name = data['name'].strip()
    
    # Check for duplicates (Case Insensitive)
    existing = Subject.query.filter(Subject.grade_class == grade, func.lower(Subject.name) == func.lower(name)).first()
    if existing:
        return jsonify({"success": False, "message": f"'{existing.name}' already exists in Class {grade}!"})
        
    new_sub = Subject(grade_class=grade, name=name)
    db.session.add(new_sub)
    db.session.commit()
    return jsonify({"success": True, "message": f"Added {name} to Class {grade}!"})

# 16. API to Delete a Subject
@app.route('/api/delete_subject/<int:sub_id>', methods=['DELETE'])
def delete_subject(sub_id):
    sub = Subject.query.get(sub_id)
    if sub:
        db.session.delete(sub)
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False}), 404

# 17. The Secure Login API
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(name=data['name'], role=data['role'], grade_class=data.get('grade_class')).first()
    
    if user and check_password_hash(user.password_hash, data['password']):
        # Give them a wristband!
        session['user_id'] = user.id
        session['name'] = user.name
        session['role'] = user.role
        session['grade_class'] = user.grade_class
        
        redirect_url = '/parent_dashboard' if user.role == 'Parent' else '/student_dashboard'
        return jsonify({"success": True, "redirect": redirect_url})
    else:
        return jsonify({"success": False, "message": "Invalid credentials!"}), 401

# 18. The Logout API
@app.route('/logout')
def logout():
    session.clear() # Rips off the wristband
    return redirect('/')



# 19. The AI Question Generator (UPGRADED FOR GROK)
@app.route('/api/generate_ai_questions', methods=['POST'])
def generate_ai_questions():
    data = request.get_json()
    grade = data.get('grade_class')
    subject = data.get('subject')
    is_olympiad = data.get('is_olympiad', False)

    # Professional Prompt Engineering for CBSE/Olympiad
    difficulty = "Olympiad Level (Logical, Multi-step)" if is_olympiad else "CBSE Metro Standard (Delhi/Mumbai/Bangalore)"
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a senior curriculum developer for top CBSE schools in India."),
        ("human", """Generate 1 challenging MCQ for Class {grade}, Subject: {subject}.
        Difficulty: {difficulty}.
        Ensure it matches the 2026 Indian curriculum standards.
        
        Return ONLY a JSON object with these keys: 
        question_text, option_a, option_b, option_c, option_d, correct_option (A, B, C, or D).""")
    ])

    # Chain the steps: Prompt -> Model -> JSON Parser
    chain = prompt | llm | JsonOutputParser()

    try:
        q_data = chain.invoke({
            "grade": grade, 
            "subject": subject, 
            "difficulty": difficulty
        })
        
        # Save to Database
        new_q = Question(
            grade_class=int(grade),
            subject=subject,
            question_text=q_data['question_text'],
            option_a=q_data['option_a'],
            option_b=q_data['option_b'],
            option_c=q_data['option_c'],
            option_d=q_data['option_d'],
            correct_option=q_data['correct_option']
        )
        db.session.add(new_q)
        db.session.commit()
        
        return jsonify({"success": True, "question": q_data['question_text']})

    except Exception as e:
        print(f"LangChain/Groq Error: {e}")
        return jsonify({"success": False, "message": "AI is busy. Please try again!"}), 500




# 20. API to Fetch Questions for Audit
@app.route('/api/view_questions', methods=['GET'])
def view_questions():
    grade = request.args.get('grade_class')
    subject = request.args.get('subject')
    
    if not grade or not subject:
        return jsonify([])

    questions = Question.query.filter_by(grade_class=grade, subject=subject).all()
    
    output = []
    for q in questions:
        output.append({
            "id": q.id,
            "text": q.question_text,
            "options": f"A: {q.option_a} | B: {q.option_b} | C: {q.option_c} | D: {q.option_d}",
            "correct": q.correct_option
        })
    return jsonify(output)

# 21. API to Delete a Specific Question
@app.route('/api/delete_question/<int:id>', methods=['DELETE'])
def delete_question(id):
    q = Question.query.get(id)
    if q:
        db.session.delete(q)
        db.session.commit()
        return jsonify({"success": True, "message": "Question deleted!"})
    return jsonify({"success": False, "message": "Not found"}), 404

# --- AUTO-BUILD DATABASE & DEFAULTS ---
with app.app_context():
    # db.drop_all()
    db.create_all()
    
    # If the Subject table is completely empty, auto-fill the CBSE defaults!
    if not Subject.query.first():
        defaults = {
            1: ['EVS', 'Hindi', 'Maths', 'English'],
            2: ['EVS', 'Hindi', 'Maths', 'English'],
            3: ['EVS', 'Hindi', 'Maths', 'English'],
            4: ['EVS', 'Hindi', 'Maths', 'English'],
            5: ['EVS', 'Hindi', 'Maths', 'English'],
            6: ['Geography', 'Civics', 'History', 'Science', 'English', 'Hindi', 'Maths'],
            7: ['Geography', 'Civics', 'History', 'Science', 'English', 'Hindi', 'Maths'],
            8: ['Geography', 'Civics', 'History', 'Science', 'English', 'Hindi', 'Maths']
        }
        for grade, subjects in defaults.items():
            for sub_name in subjects:
                db.session.add(Subject(grade_class=grade, name=sub_name))
        db.session.commit()
        print("✅ CBSE Default Subjects Loaded!")

if __name__ == '__main__':
    app.run(debug=True, port=5000)