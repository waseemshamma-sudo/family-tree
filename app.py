import os
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, abort
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row
from datetime import datetime
import io
import pandas as pd
import json
import re
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = 'family_tree_secret_key_2026_very_secure'
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def get_all_members():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM family_members ORDER BY id")
        members = cur.fetchall()
        cur.close()
        conn.close()
        return members
    except: return []

def get_country_flag(country_name):
    if not country_name: return "🌍"
    c = str(country_name).lower()
    if 'سوريا' in c or 'حمص' in c: return "🇸🇾"
    if 'سعود' in c: return "🇸🇦"
    if 'مصر' in c: return "🇪🇬"
    if 'تركيا' in c: return "🇹🇷"
    return "🌍"

def calculate_age(birth_date, death_date=None):
    if not birth_date: return None
    try:
        b_year = int(str(birth_date).split('-')[0])
        if death_date:
            d_year = int(str(death_date).split('-')[0])
            return d_year - b_year
        return datetime.now().year - b_year
    except: 
        return None

# ✅ دالة حماية تسجيل الدخول
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ✅ دالة حماية الصلاحيات (المشرفين فقط)
def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('role') not in allowed_roles:
                abort(403) # يمنع الوصول نهائياً
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ✅ دالة مساعدة لجلب عدد الطلبات المعلقة (للإشعارات)
def get_pending_count():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM pending_approvals WHERE status = 'pending'")
        count = cur.fetchone()['count']
        cur.close()
        conn.close()
        return count
    except:
        return 0

@app.context_processor
def inject_pending_count():
    if session.get('user_id'):
        return dict(pending_count=get_pending_count())
    return dict(pending_count=0)

# ================= المسارات (Routes) =================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        match = re.search(r'(\d+)$', username)
        if match:
            user_id = int(match.group(1))
            members = get_all_members()
            user = next((m for m in members if m['id'] == user_id), None)
            
            user_pass = user.get('password') if user and user.get('password') else '123@'
            
            # ✅ التحقق من كلمة المرور
            if user and (password == user_pass):
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['role'] = user.get('role', 'member')
                return redirect(url_for('index'))
                
        return render_template('login.html', error="اسم المستخدم أو كلمة المرور غير صحيحة")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pass = request.form.get('current_password')
        new_pass = request.form.get('new_password')
        confirm_pass = request.form.get('confirm_password')
        
        user_id = session['user_id']
        members = get_all_members()
        user = next((m for m in members if m['id'] == user_id), None)
        
        actual_pass = user.get('password') if user and user.get('password') else '123@'
        
        if current_pass != actual_pass:
            return render_template('change_password.html', error="كلمة المرور الحالية غير صحيحة")
        
        if new_pass != confirm_pass:
            return render_template('change_password.html', error="كلمة المرور الجديدة وتأكيدها غير متطابقين")
        
        if len(new_pass) < 4:
            return render_template('change_password.html', error="كلمة المرور يجب أن تكون 4 أحرف على الأقل")

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("UPDATE family_members SET password=%s WHERE id=%s", (new_pass, user_id))
            conn.commit()
            return render_template('change_password.html', success="✅ تم تغيير كلمة المرور بنجاح!")
        except Exception as e:
            # ✅ لا تعرض الخطأ الحقيقي للمستخدم
            return render_template('change_password.html', error="حدث خطأ داخلي.")
        finally:
            cur.close()
            conn.close()

    return render_template('change_password.html')

@app.route('/')
@login_required
def index():
    search = request.args.get('search', '')
    job_filter = request.args.get('job', '')
    location_filter = request.args.get('location', '')
    
    members = get_all_members()
    results = []
    for m in members:
        match_name = search.lower() in str(m.get('name', '')).lower() if search else True
        match_job = job_filter.lower() in str(m.get('job', '')).lower() if job_filter else True
        match_loc = location_filter.lower() in str(m.get('location', '')).lower() if location_filter else True
        
        if match_name and match_job and match_loc:
            m['flag'] = get_country_flag(m.get('location'))
            m['age'] = calculate_age(m.get('birth_year'), m.get('death_year'))
            father = next((f for f in members if f['id'] == m.get('father_id')), None)
            m['father_name'] = father['name'] if father else ""
            results.append(m)
            
    return render_template('index.html', members=results, search=search, job=job_filter, loc=location_filter)

@app.route('/person/<int:person_id>')
@login_required
def person_details(person_id):
    all_members = get_all_members()
    p = next((m for m in all_members if m['id'] == person_id), None)
    if not p: 
        abort(404)
    
    father = next((m for m in all_members if m['id'] == p.get('father_id')), None)
    children = [m for m in all_members if m.get('father_id') == person_id]
    brothers = [m for m in all_members if m.get('father_id') == p.get('father_id') and m['id'] != p['id']] if p.get('father_id') else []
    uncles = []
    if father and father.get('father_id'):
        uncles = [m for m in all_members if m.get('father_id') == father.get('father_id') and m['id'] != father['id']]
        
    p['age'] = calculate_age(p.get('birth_year'), p.get('death_year'))
    
    for child in children: child['age'] = calculate_age(child.get('birth_year'), child.get('death_year'))
    for b in brothers: b['age'] = calculate_age(b.get('birth_year'), b.get('death_year'))
    for u in uncles: u['age'] = calculate_age(u.get('birth_year'), u.get('death_year'))

    return render_template('person.html', p=p, father=father, children=children, brothers=brothers, uncles=uncles)

@app.route('/api/search_people')
@login_required
def api_search_people():
    q = request.args.get('q', '').lower()
    if not q or len(q) < 2:
        return {'results': []}

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT m.id, m.name, f.name as father_name 
            FROM family_members m
            LEFT JOIN family_members f ON m.father_id = f.id
            WHERE m.name ILIKE %s
            LIMIT 15
        """, ('%' + q + '%',))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        results = []
        for row in rows:
            display_name = f"{row['name']} بن {row['father_name']}" if row['father_name'] else row['name']
            results.append({'id': row['id'], 'text': display_name})
            
        return {'results': results}
    except Exception as e:
        return {'results': []}

@app.route('/relationship', methods=['GET', 'POST'])
@login_required
def relationship():
    all_members = get_all_members()
    result = None
    error = None
    p1_id = request.form.get('p1') or request.args.get('p1')
    p2_id = request.form.get('p2') or request.args.get('p2')
    
    if p1_id and p2_id:
        try:
            p1_id, p2_id = int(p1_id), int(p2_id)
        except ValueError:
            error = "بيانات غير صالحة"
            return render_template('relationship.html', all_members=all_members, result=result, error=error, p1_id=p1_id, p2_id=p2_id)
        
        def get_line_to_root(pid):
            line, curr = [], pid
            while curr:
                per = next((m for m in all_members if m['id'] == curr), None)
                if not per: break
                per['age'] = calculate_age(per.get('birth_year'), per.get('death_year'))
                per['is_dead'] = bool(per.get('death_year'))
                line.append(per)
                curr = per.get('father_id')
            return line

        line1 = get_line_to_root(p1_id)
        line2 = get_line_to_root(p2_id)
        
        common_ancestor = None
        d1, d2 = 0, 0
        found = False
        
        for i, per1 in enumerate(line1):
            for j, per2 in enumerate(line2):
                if per1['id'] == per2['id']:
                    common_ancestor, d1, d2 = per1, i, j
                    found = True
                    break
            if found: break
            
        if not common_ancestor:
            error = "لا توجد صلة قرابة مباشرة بين الشخصين."
        else:
            if d1 == d2: rel = "أخوة" if d1==1 else ("أبناء عم" if d1==2 else f"أبناء عم من الدرجة {d1-1}")
            elif d1 == 0: rel = "الأب" if d2==1 else "الجد"
            elif d2 == 0: rel = "الابن" if d1==1 else "الحفيد"
            elif d1 == 1 and d2 == 2: rel = "العم"
            elif d1 == 2 and d2 == 1: rel = "ابن الأخ"
            else: rel = "قريب"
            
            p1 = next(m for m in all_members if m['id'] == p1_id)
            p2 = next(m for m in all_members if m['id'] == p2_id)
            
            path1 = line1[1:d1]
            path2 = line2[1:d2]
            
            result = {
                'p1': p1, 'p2': p2,
                'ancestor': common_ancestor, 'relationship': rel,
                'path1': path1, 'path2': path2,
                'max_dist': max(d1, d2)
            }

    return render_template('relationship.html', all_members=all_members, result=result, error=error, p1_id=p1_id, p2_id=p2_id)

@app.route('/export_excel')
@login_required
def export_excel():
    try:
        members = get_all_members()
        if not members: return "لا توجد بيانات للتصدير", 404

        df = pd.DataFrame(members)
        
        column_mapping = {
            'id': 'المعرف', 'name': 'الاسم', 'father_id': 'معرف الأب',
            'birth_year': 'تاريخ الميلاد', 'death_year': 'تاريخ الوفاة',
            'job': 'الوظيفة', 'phone': 'رقم الجوال', 'location': 'مكان الإقامة',
            'email': 'البريد الإلكتروني'
        }
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        
        if 'معرف الأب' in df.columns:
            father_names = {m['id']: m['name'] for m in members}
            df.insert(2, 'اسم الأب', df['معرف الأب'].map(father_names).fillna(''))

        if 'رقم الجوال' in df.columns:
            df['رقم الجوال'] = df['رقم الجوال'].astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', '')

        cols = ['المعرف', 'الاسم', 'اسم الأب', 'معرف الأب', 'تاريخ الميلاد', 'تاريخ الوفاة', 'الوظيفة', 'رقم الجوال', 'مكان الإقامة', 'البريد الإلكتروني']
        df = df[[c for c in cols if c in df.columns]]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='عائلة شما')
        
        output.seek(0)
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='family_tree_export.xlsx')

    except Exception as e:
        return "حدث خطأ أثناء التصدير.", 500

@app.route('/tree')
@login_required
def full_tree():
    members = get_all_members()
    roots = [m for m in members if not m.get('father_id')]
    
    def build_branch(person):
        children = [m for m in members if m.get('father_id') == person['id']]
        children = sorted(children, key=lambda x: str(x.get('birth_year', '9999')))
        return {'person': person, 'children': [build_branch(c) for c in children]}
        
    tree = [build_branch(root) for root in roots]
    return render_template('tree.html', tree=tree)

@app.route('/add', methods=['GET', 'POST'])
@app.route('/edit/<int:person_id>', methods=['GET', 'POST'])
@login_required
def manage_person(person_id=None):
    all_members = get_all_members()
    person = None
    action = "إضافة شخص جديد"
    prefilled_father_id = request.args.get('father_id', 0)
    
    if person_id:
        person = next((m for m in all_members if m['id'] == person_id), None)
        if not person: abort(404)
        action = "تعديل البيانات"

    current_user_id = session['user_id']
    current_role = session.get('role', 'member')
    
    if person_id:
        if person_id != current_user_id and current_role == 'member':
            return "❌ ليس لديك صلاحية لتعديل بيانات الآخرين.", 403

    if request.method == 'POST':
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            name = request.form.get('name')
            father_id = int(request.form.get('father_id')) if request.form.get('father_id') else 0
            birth = request.form.get('birth_year')
            death = request.form.get('death_year')
            job = request.form.get('job')
            phone = request.form.get('phone')
            location = request.form.get('location')
            email = request.form.get('email')

            needs_approval = False
            if current_role not in ['super_admin', 'admin']:
                needs_approval = True

            if needs_approval:
                request_data = {
                    'name': name, 'father_id': father_id, 'birth_year': birth,
                    'death_year': death, 'job': job, 'phone': phone,
                    'location': location, 'email': email
                }
                req_type = 'edit' if person_id else 'add'
                target_id = person_id if person_id else 0
                
                cur.execute("""
                    INSERT INTO pending_approvals (request_type, target_person_id, requested_data, requested_by_id)
                    VALUES (%s, %s, %s, %s)
                """, (req_type, target_id, json.dumps(request_data), current_user_id))
                conn.commit()
                
                flash("⏳ تم إرسال طلبك للمشرف للاعتماد. يرجى الانتظار.", "warning")
                
                if person_id:
                    return redirect(url_for('person_details', person_id=person_id))
                else:
                    return redirect(url_for('index'))

            if person_id:
                cur.execute("""
                    UPDATE family_members 
                    SET name=%s, father_id=%s, birth_year=%s, death_year=%s, job=%s, phone=%s, location=%s, email=%s
                    WHERE id=%s
                """, (name, father_id, birth, death, job, phone, location, email, person_id))
            else:
                cur.execute("SELECT MAX(id) FROM family_members")
                new_id = (cur.fetchone()['max'] or 0) + 1
                cur.execute("""
                    INSERT INTO family_members (id, name, father_id, birth_year, death_year, job, phone, location, email)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (new_id, name, father_id, birth, death, job, phone, location, email))
                person_id = new_id
                
            conn.commit()
            flash("✅ تم حفظ البيانات بنجاح.", "success")
            return redirect(url_for('person_details', person_id=person_id))
        except Exception as e:
            return "حدث خطأ داخلي.", 500
        finally:
            cur.close()
            conn.close()

    return render_template('edit.html', action=action, person=person, all_members=all_members, prefilled_father_id=prefilled_father_id)

@app.route('/admin/pending')
@login_required
@role_required('super_admin', 'admin')
def admin_pending():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # جلب الطلبات المعلقة
    cur.execute("""
        SELECT p.*, u.name as requester_name 
        FROM pending_approvals p
        JOIN family_members u ON p.requested_by_id = u.id
        WHERE p.status = 'pending'
        ORDER BY p.created_at DESC
    """)
    pending = cur.fetchall()
    
    # جلب كل الأعضاء لاستخدامهم في تحويل معرفات الآباء إلى أسماء
    all_members = get_all_members()
    father_names = {m['id']: m['name'] for m in all_members}
    
    # معالجة كل طلب: تحويل JSON إلى قاموس، وجلب بيانات الشخص القديم (إذا كان تعديلاً)
    processed_pending = []
    for req in pending:
        req_dict = dict(req)
        
        # ✅ التعديل الجديد: التعامل مع البيانات سواء كانت نصاً أو قاموساً
        raw_data = req['requested_data']
        if isinstance(raw_data, str):
            req_dict['requested_data'] = json.loads(raw_data)
        elif isinstance(raw_data, dict):
            req_dict['requested_data'] = raw_data
        else:
            req_dict['requested_data'] = {}
        
        # جلب اسم الأب للبيانات المطلوبة
        father_id = req_dict['requested_data'].get('father_id')
        req_dict['new_father_name'] = father_names.get(father_id, 'غير معروف')
        
        # إذا كان الطلب تعديلاً، نجلب البيانات القديمة للمقارنة
        req_dict['old_data'] = None
        if req['request_type'] == 'edit' and req['target_person_id']:
            old_person = next((m for m in all_members if m['id'] == req['target_person_id']), None)
            if old_person:
                req_dict['old_data'] = dict(old_person)
                old_father_id = old_person.get('father_id')
                req_dict['old_father_name'] = father_names.get(old_father_id, 'غير معروف')
                
        processed_pending.append(req_dict)
        
    cur.close()
    conn.close()
    
    return render_template('pending.html', pending=processed_pending)


@app.route('/admin/approve/<int:req_id>')
@login_required
@role_required('super_admin', 'admin') # ✅ حماية مزدوجة
def approve_request(req_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM pending_approvals WHERE id=%s", (req_id,))
        req = cur.fetchone()
        
        if req:
            data = req['requested_data']
            if req['request_type'] == 'edit':
                cur.execute("""
                    UPDATE family_members 
                    SET name=%s, father_id=%s, birth_year=%s, death_year=%s, job=%s, phone=%s, location=%s, email=%s
                    WHERE id=%s
                """, (data['name'], data['father_id'], data['birth_year'], data['death_year'], data['job'], data['phone'], data['location'], data['email'], req['target_person_id']))
            elif req['request_type'] == 'add':
                cur.execute("SELECT MAX(id) FROM family_members")
                new_id = (cur.fetchone()['max'] or 0) + 1
                cur.execute("""
                    INSERT INTO family_members (id, name, father_id, birth_year, death_year, job, phone, location, email)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (new_id, data['name'], data['father_id'], data['birth_year'], data['death_year'], data['job'], data['phone'], data['location'], data['email']))
                
            cur.execute("UPDATE pending_approvals SET status='approved' WHERE id=%s", (req_id,))
            conn.commit()
            flash("✅ تم اعتماد الطلب بنجاح.", "success")
    except Exception as e:
        return "حدث خطأ داخلي.", 500
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('admin_pending'))

@app.route('/stats')
@login_required
def stats():
    members = get_all_members()
    total = len(members)
    alive = sum(1 for m in members if not m.get('death_year'))
    dead = sum(1 for m in members if m.get('death_year'))
    
    alive_ages = [calculate_age(m.get('birth_year')) for m in members if not m.get('death_year') and calculate_age(m.get('birth_year'))]
    avg_alive_age = round(sum(alive_ages) / len(alive_ages), 1) if alive_ages else 0
    
    dead_ages = [calculate_age(m.get('birth_year'), m.get('death_year')) for m in members if m.get('death_year') and calculate_age(m.get('birth_year'), m.get('death_year'))]
    avg_dead_age = round(sum(dead_ages) / len(dead_ages), 1) if dead_ages else 0

    oldest_alive = max((m for m in members if not m.get('death_year') and calculate_age(m.get('birth_year'))), key=lambda x: calculate_age(x.get('birth_year')), default=None)
    if oldest_alive: oldest_alive['age'] = calculate_age(oldest_alive.get('birth_year'))

    locations = {}
    for m in members:
        loc = m.get('location')
        if loc and str(loc).strip() and str(loc).lower() != 'nan':
            locations[loc] = locations.get(loc, 0) + 1
    sorted_locations = sorted(locations.items(), key=lambda x: x[1], reverse=True)

    return render_template('stats.html', total=total, alive=alive, dead=dead, avg_alive_age=avg_alive_age, avg_dead_age=avg_dead_age, oldest_alive=oldest_alive, sorted_locations=sorted_locations)

app.jinja_env.globals.update(calculate_age=calculate_age)

@app.route('/admin/reject/<int:req_id>')
@login_required
@role_required('super_admin', 'admin')
def reject_request(req_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # تحديث حالة الطلب إلى مرفوض
        cur.execute("UPDATE pending_approvals SET status='rejected' WHERE id=%s", (req_id,))
        conn.commit()
        flash("❌ تم رفض الطلب.", "danger")
    except Exception as e:
        return "حدث خطأ داخلي.", 500
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('admin_pending'))

if __name__ == '__main__':
    app.run(debug=False, port=5000) # ✅ إيقاف وضع التطوير في الإنتاج