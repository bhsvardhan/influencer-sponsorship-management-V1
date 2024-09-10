import sqlite3,os,re
from flask import Flask, render_template, request, jsonify, redirect, session
from flask import *
from datetime import datetime
app = Flask(__name__)
app.secret_key = "asdlkjqwepoirtyiuyzxc,mncvbnbv0912398735=-0`12"

@app.route('/')
def home():
    return redirect('/login')

@app.route('/logOut',methods=['GET'])
def logOut():
  session['user']=None
  session['role']=None
  return redirect('/login')

@app.route('/login',methods=['GET'])
def login():
    return render_template("login.html")

@app.route('/signUp',methods=['GET'])
def signUp():
    return render_template("signUp.html")

@app.route('/sponsor_dashboard2', methods=['GET'])
def sponsor_dashboard2():
    if(session.get('role') !=3):
        return render_template("unAuth.html")
    return render_template('sponsor_dashboard2.html',name=session.get('user'))

@app.route('/influencer_dashboard',methods=['GET'])
def influencer_dashboard():
    if(session.get('role') !=2):
        return render_template("unAuth.html")
    campaigns = get_current_campaigns()
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    return render_template("influencer_dashboard.html",campaigns=campaigns,name=session.get('user'))

@app.route('/admin_dashboard', methods=['GET'])
def admin_dashboard():
    if(session.get('role') !=1):
        return render_template("unAuth.html")
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # Fetch only active campaigns
    cur.execute("SELECT name, 'campaign' AS type, start_date, end_date FROM campaigns WHERE end_date >= date('now')")
    campaigns = cur.fetchall()

    # Fetch flagged users and campaigns
    cur.execute("SELECT name, type FROM flagged_users_campaigns")
    flagged_items = cur.fetchall()

    conn.close()
    return render_template('admin_dashboard.html',name=session.get('user'), campaigns=campaigns, flagged_items=flagged_items)

@app.route('/remove_flagged/<name>', methods=['GET'])
def remove_flagged(name):
    if(session.get('role') == None):
        return render_template("unAuth.html")
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    
    cur.execute("DELETE FROM flagged_users_campaigns WHERE name = ?", (name,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('admin_dashboard1'))

@app.route('/stats', methods=['GET'])
def stats():
    if(session.get('role') !=1):
        return render_template("unAuth.html")
    return render_template('stats.html',name=session.get('user'))

@app.route('/api/stats', methods=['GET'])
def api_stats():
    if(session.get('role') !=1):
        return render_template("unAuth.html")
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # Example statistics queries
    cur.execute("SELECT COUNT(*) AS total_campaigns FROM campaigns")
    total_campaigns = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) AS total_influencers FROM influencer_users")
    total_influencers = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) AS total_sponsors FROM sponsor_users")
    total_sponsors = cur.fetchone()[0]

    cur.execute("SELECT SUM(budget) AS total_budget FROM campaigns")
    total_budget = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) AS total_requests FROM ad_requests1")
    total_requests = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) AS total_accepted_requests FROM ad_requests1 WHERE status='accepted'")
    total_accepted_requests = cur.fetchone()[0]

    stats = {
        'total_campaigns': total_campaigns,
        'total_influencers': total_influencers,
        'total_sponsors': total_sponsors,
        'total_budget': total_budget,
        'total_requests': total_requests,
        'total_accepted_requests': total_accepted_requests,
    }

    conn.close()
    return jsonify(stats)


@app.route('/view_requests_influencer', methods=['GET'])
def view_requests_influencer():
    if session.get('role') is None:
        return render_template("unAuth.html")
    
    username = session.get('user')  # Get the logged-in user's username
    
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    
    # Query to fetch requests where the influencer username matches the logged-in user and status is 'pending'
    cur.execute("""
        SELECT campaign_name, influencer_username, messages, requirements, payment_amount, status
        FROM ad_requests1
        WHERE status='pending' AND influencer_username=?
    """, (username,))
    
    requests = cur.fetchall()
    conn.close()
    
    return jsonify(requests)


@app.route('/find_campaign', methods=['POST'])
def find_campaign():
    if(session.get('role') == None):
        return render_template("unAuth.html")
    data = request.json
    campaign_name = data.get('campaign_name')

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    campaign = cur.execute('SELECT * FROM campaigns WHERE name = ?', (campaign_name,)).fetchone()
    conn.close()

    if campaign:
        return jsonify({'campaign_info': list(campaign)})
    return jsonify({'error': 'Campaign not found'}), 404

@app.route('/accept_request_influencer', methods=['POST'])
def accept_request_influencer():
    if session.get('role') is None:
        return render_template("unAuth.html")
    
    data = request.json
    campaign_name = data.get('campaign_name')
    influencer_username = data.get('influencer_username')

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    try:
        # Retrieve the sponsor_username based on campaign_name and influencer_username
        cur.execute("""
            SELECT sponsor_username
            FROM ad_requests1
            WHERE campaign_name = ? AND influencer_username = ?
        """, (campaign_name, influencer_username))
        
        sponsor_username = cur.fetchone()

        if sponsor_username:
            sponsor_username = sponsor_username[0]
            
            # Update the status to 'accepted'
            cur.execute("""
                UPDATE ad_requests1
                SET status = 'accepted'
                WHERE campaign_name = ? AND influencer_username = ?
            """, (campaign_name, influencer_username))

            # Insert into the events table
            cur.execute("""
                INSERT INTO events(campaign_name, influencer_username, sponsor_username)
                VALUES (?, ?, ?)
            """, (campaign_name, influencer_username, sponsor_username))

            conn.commit()
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Request not found"}), 404
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/reject_request_influencer', methods=['POST'])
def reject_request_influencer():
    if(session.get('role') == None):
        return render_template("unAuth.html")
    data = request.json
    campaign_name = data.get('campaign_name')
    influencer_username = data.get('influencer_username')
    
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE ad_requests1
        SET status = 'rejected'
        WHERE campaign_name = ? AND influencer_username = ?
    """, (campaign_name, influencer_username))
    
    conn.commit()
    conn.close()
    
    return jsonify({"success": True})

@app.route('/create_adrequest', methods=['GET', 'POST'])
def create_adrequest():
    if(session.get('role') !=3):
        return render_template("unAuth.html")
    if request.method == 'POST':
        campaign_name = request.form['campaign_name']
        influencer_username = request.form['influencer_username']
        message = request.form['message']
        requirements = request.form['requirements']
        payment_amount = request.form['payment_amount']

        conn = sqlite3.connect('database.db')
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ad_requests1 (campaign_name, influencer_username, messages, requirements, payment_amount, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        """, (campaign_name, influencer_username, message, requirements, payment_amount))
        conn.commit()
        conn.close()

        return redirect(url_for('create_adrequest'))  # Redirect to the same form or another page after submission

    return render_template('create_adrequest.html')


@app.route('/all_data1', methods=['GET'])
def all_data1():
    if(session.get('role') == None):
        return render_template("unAuth.html")
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    results = []

    # Fetch all data from campaigns
    cur.execute("SELECT name, 'campaign' AS type, name AS id FROM campaigns")
    results.extend([{'name': row[0], 'type': row[1], 'id': row[2]} for row in cur.fetchall()])

    # Fetch all data from influencer_users
    cur.execute("SELECT username AS name, 'influencer' AS type, username AS id FROM influencer_users")
    results.extend([{'name': row[0], 'type': row[1], 'id': row[2]} for row in cur.fetchall()])

    conn.close()
    return jsonify(results)

@app.route('/search1', methods=['GET'])
def search1():
    if(session.get('role') == None):
        return render_template("unAuth.html")
    query = request.args.get('query', '')
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    results = []

    if query:
        # Search in campaigns
        cur.execute("SELECT name, 'campaign' AS type, name AS id FROM campaigns WHERE name LIKE ?", ('%' + query + '%',))
        results.extend([{'name': row[0], 'type': row[1], 'id': row[2]} for row in cur.fetchall()])

        # Search in influencer_users
        cur.execute("SELECT username AS name, 'influencer' AS type, username AS id FROM influencer_users WHERE username LIKE ?", ('%' + query + '%',))
        results.extend([{'name': row[0], 'type': row[1], 'id': row[2]} for row in cur.fetchall()])

    conn.close()
    return jsonify(results)

@app.route('/view_campaign1/<campaign_id>', methods=['GET'])
def view_campaign1(campaign_id):
    if(session.get('role') == None):
        return render_template("unAuth.html")
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM campaigns WHERE name = ?", (campaign_id,))
    campaign = cur.fetchone()
    conn.close()
    
    if campaign:
        keys = [description[0] for description in cur.description]
        campaign_data = dict(zip(keys, campaign))
        return jsonify(campaign_data)
    else:
        return jsonify({"error": "Campaign not found"}), 404

@app.route('/view_influencer1/<influencer_id>', methods=['GET'])
def view_influencer1(influencer_id):
    if(session.get('role') == None):
        return render_template("unAuth.html")
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM influencer_users WHERE username = ?", (influencer_id,))
    influencer = cur.fetchone()
    conn.close()
    
    if influencer:
        keys = [description[0] for description in cur.description]
        influencer_data = dict(zip(keys, influencer))
        return jsonify(influencer_data)
    else:
        return jsonify({"error": "Influencer not found"}), 404

@app.route('/send_request1/<influencer_id>', methods=['POST'])
def send_request1(influencer_id):
    if(session.get('role') == None):
        return render_template("unAuth.html")
    data = request.get_json()
    campaign_name = data['campaign_name']
    sponsor_name=session.get('user')
    message = data['message']
    requirements = data['requirements']
    payment_amount = data['payment_amount']
    
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO ad_requests1 (campaign_name,sponsor_username, influencer_username, messages, requirements, payment_amount, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
    """, (campaign_name,sponsor_name, influencer_id, message, requirements, payment_amount))
    conn.commit()
    conn.close()
    
    return jsonify({"success": True})

@app.route('/all_data', methods=['GET'])
def all_data():
    if(session.get('role') == None):
        return render_template("unAuth.html")
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    results = []

    # Fetch all data from campaigns
    cur.execute("SELECT name, 'campaign' AS type, name AS id FROM campaigns")
    results.extend(cur.fetchall())

    # Fetch all data from influencer_users
    cur.execute("SELECT name, 'influencer' AS type, username AS id FROM influencer_users")
    results.extend(cur.fetchall())

    # Fetch all data from sponsor_users
    cur.execute("SELECT name, 'sponsor' AS type, username AS id FROM sponsor_users")
    results.extend(cur.fetchall())

    conn.close()
    return jsonify(results)

@app.route('/search', methods=['GET'])
def search():
    if(session.get('role') == None):
        return render_template("unAuth.html")
    query = request.args.get('query', '')
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    results = []

    if query:
        # Search in campaigns
        cur.execute("SELECT name, 'campaign' AS type, name AS id FROM campaigns WHERE name LIKE ?", ('%' + query + '%',))
        results.extend(cur.fetchall())

        # Search in influencer_users
        cur.execute("SELECT name, 'influencer' AS type, username AS id FROM influencer_users WHERE name LIKE ?", ('%' + query + '%',))
        results.extend(cur.fetchall())

        # Search in sponsor_users
        cur.execute("SELECT name, 'sponsor' AS type, username AS id FROM sponsor_users WHERE name LIKE ?", ('%' + query + '%',))
        results.extend(cur.fetchall())

    conn.close()
    return jsonify(results)

@app.route('/admin_dashboard1', methods=['GET', 'POST'])
def admin_dashboard1():
    if(session.get('role') !=1):
        return render_template("unAuth.html")

    try:
        conn = sqlite3.connect('database.db')
        cur = conn.cursor()

        search_query = request.form.get('search_query', '')
        results = []

        if search_query:
        # Search in campaigns
            cur.execute("SELECT name, 'campaign' AS type, name AS id FROM campaigns WHERE name LIKE ?", ('%' + search_query + '%',))
            results.extend(cur.fetchall())

        # Search in influencer_users
            cur.execute("SELECT name, 'influencer' AS type, username AS id FROM influencer_users WHERE name LIKE ?", ('%' + search_query + '%',))
            results.extend(cur.fetchall())

        # Search in sponsor_users
            cur.execute("SELECT name, 'sponsor' AS type, username AS id FROM sponsor_users WHERE name LIKE ?", ('%' + search_query + '%',))
            results.extend(cur.fetchall())
        else:
        # No search query, just show all
            cur.execute("SELECT name, 'campaign' AS type, name AS id FROM campaigns")
            results.extend(cur.fetchall())

            cur.execute("SELECT name, 'influencer' AS type, username AS id FROM influencer_users")
            results.extend(cur.fetchall())

            cur.execute("SELECT name, 'sponsor' AS type, username AS id FROM sponsor_users")
            results.extend(cur.fetchall())
    
    except Exception as e:
        print("Internal Server Error: ",e)

    return render_template('admin_dashboard1.html', name=session.get('user'),results=results)
    

@app.route('/view/<item_id>', methods=['GET'])
def view_item(item_id):
    if(session.get('role') == None):
        return render_template("unAuth.html")
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # Find the type of the item
    cur.execute("SELECT 'campaign' AS type FROM campaigns WHERE name = ?", (item_id,))
    item = cur.fetchone()
    if not item:
        cur.execute("SELECT 'influencer' AS type FROM influencer_users WHERE username = ?", (item_id,))
        item = cur.fetchone()
    if not item:
        cur.execute("SELECT 'sponsor' AS type FROM sponsor_users WHERE username = ?", (item_id,))
        item = cur.fetchone()

    if item:
        type_ = item[0]
        if type_ == 'campaign':
            cur.execute("SELECT * FROM campaigns WHERE name = ?", (item_id,))
        elif type_ == 'influencer':
            cur.execute("SELECT * FROM influencer_users WHERE username = ?", (item_id,))
        elif type_ == 'sponsor':
            cur.execute("SELECT * FROM sponsor_users WHERE username = ?", (item_id,))
        
        item_data = cur.fetchone()
        conn.close()
        if (session.get('role') == 1):
            return render_template(f'{type_}_details.html', item=item_data)
        elif (session.get('role') == 2):
            return render_template(f'{type_}_details1.html', item=item_data)
    else:
        conn.close()
        return "Item not found", 404

@app.route('/flag/<item_id>', methods=['GET'])
def flag_item(item_id):
    if(session.get('role') == None):
        return render_template("unAuth.html")
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    cur.execute("SELECT 'campaign' AS type FROM campaigns WHERE name = ?", (item_id,))
    item = cur.fetchone()
    if not item:
        cur.execute("SELECT 'influencer' AS type FROM influencer_users WHERE username = ?", (item_id,))
        item = cur.fetchone()
    if not item:
        cur.execute("SELECT 'sponsor' AS type FROM sponsor_users WHERE username = ?", (item_id,))
        item = cur.fetchone()

    if item:
        type_ = item[0]

        cur.execute("INSERT INTO flagged_users_campaigns (name, type) VALUES (?, ?)", (item_id, type_))

        if type_ == 'campaign':
            cur.execute("DELETE FROM campaigns WHERE name = ?", (item_id,))
        elif type_ == 'influencer':
            cur.execute("DELETE FROM influencer_users WHERE username = ?", (item_id,))
        elif type_ == 'sponsor':
            cur.execute("DELETE FROM sponsor_users WHERE username = ?", (item_id,))
        
        cur.execute("DELETE FROM users WHERE username = ?", (item_id,))
        
        conn.commit()
        conn.close()
        return redirect(url_for('admin_dashboard'))
    else:
        conn.close()
        return "Item not found", 404

def get_current_campaigns():
    if(session.get('role') == None):
        return render_template("unAuth.html")
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("""
        SELECT name, description, start_date, end_date, budget, visibility, goals
        FROM campaigns
        WHERE date('now') BETWEEN start_date AND end_date
    """)
    campaigns = cur.fetchall()
    print(campaigns)
    conn.close()

    current_campaigns = []
    for campaign in campaigns:
        name, description, start_date, end_date, budget, visibility, goals = campaign
        current_campaigns.append((name, description, start_date, end_date, budget, visibility, goals))

    return current_campaigns

@app.route('/influencer_dashboard1',methods=['GET'])
def influencer_dashboard1():
    if(session.get('role') !=2):
        return render_template("unAuth.html")
    return render_template('influencer_dashboard1.html',name=session.get('user'))

@app.route('/sponsor_dashboard1', methods=['GET'])
def sponsor_dashboard1():
    if(session.get('role') !=3):
        return render_template("unAuth.html")
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM campaigns WHERE end_date >= date('now')")
    campaigns = cur.fetchall()
    conn.close()
    return render_template('sponsor_dashboard1.html', campaigns=campaigns,name=session.get('user'))

@app.route('/search_campaigns', methods=['GET'])
def search_campaigns():
    if(session.get('role') == None):
        return render_template("unAuth.html")
    search_query = request.args.get('search', '').lower()
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM campaigns WHERE LOWER(name) LIKE ?", (search_query + '%',))
    campaigns = cur.fetchall()
    conn.close()
    return jsonify(campaigns)

@app.route('/add_campaign',methods=['GET','POST'])
def add_campaign():
    if(session.get('role') !=3):
        return render_template("unAuth.html")
    if request.method=='POST':
        data=request.form
        name=data.get('name')
        description=data.get('description')
        start_date=data.get('start_date')
        end_date=data.get('end_date')
        budget=data.get('budget')
        visibility=data.get('visibility')
        goals=data.get('goals')

        conn=sqlite3.connect("database.db")
        cur=conn.cursor()

        try:
            cur.execute('''
                INSERT INTO campaigns(name,description,start_date,end_date,budget,visibility,goals)
                VALUES(?,?,?,?,?,?,?)
            ''',(name,description,start_date,end_date,budget,visibility,goals))
            conn.commit()

            return redirect('/sponsor_dashboard1')
        
        except sqlite3.IntegrityError:
            return 'Username already exists', 409
        finally:
            cur.close()
            conn.close()

    elif request.method == 'GET':
        return render_template("add_campaign.html")
    
    return redirect('/add_campaign')


@app.route('/sponsor_register',methods=['GET','POST'])
def sponsor_register():
    if request.method == 'POST':
        data = request.form
        username = data.get('username')
        password = data.get('password')
        name = data.get('name')
        industry=data.get('industry')
        budget=data.get('budget')

        conn = sqlite3.connect("database.db")
        cur=conn.cursor()
        regex = r"^[a-zA-Z0-9]{8,}$"
        if(username=="" or password=="" or not re.match(regex,password)):
            return jsonify({"BAD_REQUEST":"Invalid credentials!"})
        try:
            cur.execute('''
                INSERT INTO sponsor_users (username, password, name, industry,budget)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, password, name,industry,budget))
            cur.execute('''
                INSERT INTO users (username, password, role)
                VALUES (?, ?, ?)
            ''', (username, password,3))
            conn.commit()

            return redirect('/login')
        
        except sqlite3.IntegrityError:
            return 'Username already exists', 409
        finally:
            cur.close()
            conn.close()
        
    elif request.method == 'GET':
        return render_template("sponsor_register.html")
    
    return redirect('/sponsor_register')

@app.route('/send_request', methods=['POST'])
def send_request():
    if session.get('role') is None:
        return render_template("unAuth.html")
    
    data = request.json
    campaign_name = data['campaign_name']
    influencer_username = session.get('user')  # Get the actual logged-in influencer's username from session
    
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO ad_requests (campaign_name, influencer_username, status)
            VALUES (?, ?, 'pending')
        ''', (campaign_name, influencer_username))
        conn.commit()
        return jsonify({'message': 'Request sent successfully!'}), 200
    except sqlite3.IntegrityError:
        return jsonify({'message': 'Request already exists'}), 409
    finally:
        cur.close()
        conn.close()


@app.route('/view_requests', methods=['GET'])
def view_requests():
    if(session.get('role') == None):
        return render_template("unAuth.html")
    campaigns = get_current_campaigns()
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("""
        SELECT campaign_name, influencer_username 
        FROM ad_requests 
        WHERE status='pending'
    """)
    requests = cur.fetchall()
    conn.close()
    return render_template('view_requests.html', requests=requests,campaigns=campaigns, name=session.get('user'))

@app.route('/accept_request', methods=['POST'])
def accept_request():
    if(session.get('role') == None):
        return render_template("unAuth.html")
    data = request.json
    campaign_name = data['campaign_name']
    influencer_username = data['influencer_username']
    sponsor_username=session.get('user')
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE ad_requests
            SET status = 'accepted'
            WHERE campaign_name = ? AND influencer_username = ?
        ''', (campaign_name, influencer_username))
        cur.execute("""
            INSERT INTO events(campaign_name,influencer_username,sponsor_username) values(?,?,?)"""
            ,(campaign_name,influencer_username,sponsor_username))
        conn.commit()
        conn.commit()
        return jsonify({'message': 'Request accepted successfully!'}), 200
    except sqlite3.IntegrityError:
        return jsonify({'message': 'Failed to accept request'}), 409
    finally:
        cur.close()
        conn.close()


@app.route('/sponsor_dashboard', methods=['GET'])
def sponsor_dashboard():
    if(session.get('role') !=3):
        return render_template("unAuth.html")
    campaigns = get_current_campaigns()
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("""
        SELECT campaign_name, influencer_username 
        FROM ad_requests 
        WHERE status='pending'
    """)
    requests = cur.fetchall()
    conn.close()
    return render_template('sponsor_dashboard.html', campaigns=campaigns, requests=requests,name=session.get('user'))

@app.route('/reject_request', methods=['POST'])
def reject_request():
    if(session.get('role') == None):
        return render_template("unAuth.html")
    data = request.json
    campaign_name = data.get('campaign_name')
    influencer_username = data.get('influencer_username')
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("""
        UPDATE ad_requests
        SET status='rejected'
        WHERE campaign_name=? AND influencer_username=?
    """, (campaign_name, influencer_username))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})


@app.route('/campaign/<campaign_name>', methods=['GET'])
def view_campaign(campaign_name):
    if(session.get('role') == None):
        return render_template("unAuth.html")
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM campaigns WHERE name=?", (campaign_name,))
    campaign = cur.fetchone()
    conn.close()
    return render_template('view_campaign.html', campaign=campaign)


@app.route('/find_influencer', methods=['POST'])
def find_influencer():
    if session.get('role') is None:
        return render_template("unAuth.html")

    data = request.json
    influencer_username = data['influencer_username']
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT username, name, niche, category, reach, platform_presence
            FROM influencer_users
            WHERE username = ?
        ''', (influencer_username,))
        influencer_info = cur.fetchone()
        if influencer_info:
            influencer = {
                'username': influencer_info[0],
                'name': influencer_info[1],
                'niche': influencer_info[2],
                'category': influencer_info[3],
                'reach': influencer_info[4],
                'platform_presence': influencer_info[5]
            }
            return render_template('influencer_details1.html', influencer=influencer)
        else:
            return jsonify({'message': 'Influencer not found'}), 404
    except sqlite3.IntegrityError:
        return jsonify({'message': 'Failed to retrieve influencer information'}), 409
    finally:
        cur.close()
        conn.close()



@app.route('/influencer_register', methods=['GET','POST'])
def influencer_register():
    if request.method == 'POST':
        data = request.form
        username = data.get('username')
        password = data.get('password')
        name = data.get('name')
        niche = data.get('niche')
        category = data.get('category')
        reach = data.get('reach')
        phonenumber=data.get('phonenumber')
        platform_presence = data.get('platform_presence')

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()
        regex = r"^[a-zA-Z0-9]{8,}$"
        if(username=="" or password=="" or not re.match(regex,password)):
            return jsonify({"BAD_REQUEST":"Invalid credentials!"})
        try:
            cur.execute('''
                INSERT INTO influencer_users1 (username, password, name, niche, category, reach, platform_presence,phonenumber)
                VALUES (?, ?, ?, ?, ?, ?, ?,?)
            ''', (username, password, name, niche, category, reach, platform_presence,phonenumber))
            cur.execute('''
                INSERT INTO users (username, password, role)
                VALUES (?, ?, ?)
            ''', (username, password,2))
            conn.commit()

            return redirect('/login')
        except sqlite3.IntegrityError:
            return 'Username already exists', 409
        finally:
            cur.close()
            conn.close()
        
    elif request.method == 'GET':
        return render_template("influencer_register.html")
    
    return redirect('/influencer_register')

@app.route("/loginUser",methods=['POST'])
def loginUser():
    username = request.form.get("userName")
    password = request.form.get("password")
    if(username=="" or password==""):
        return jsonify({"BAD_REQUEST":"Invalid credentials!"})
    print(username,password)
    try:
        with sqlite3.connect("database.db") as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM users WHERE username = ? AND password = ?",(username,password))
            data= cur.fetchall()
            print(data)
            role=data[0][-1]
            session['user'] = username
            session['role'] = role
            print("User found successfully !")
            if(role == 1):
                print("admin")
                return redirect("/admin_dashboard")
            elif(role == 2):
                return redirect("/influencer_dashboard")
            elif(role == 3):
                return redirect("/sponsor_dashboard")
    except Exception as e:
        print("User data not found in database",str(e))
    return redirect("/login")

@app.route('/fetch_events', methods=['GET'])
def fetch_events():
    username = session.get('user')  # Assuming the username is stored in the session
    if not username:
        return jsonify({'error': 'User not logged in'}), 401

    try:
        # Directly establishing connection to SQLite database
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row  # To access columns by name
        cursor = conn.cursor()

        # Query to fetch events where the logged-in influencer is involved
        query = """
            SELECT campaign_name, sponsor_username
            FROM events
            WHERE influencer_username = ?
        """
        cursor.execute(query, (username,))
        events = cursor.fetchall()
        conn.close()

        if events:
            # Convert each row to a dictionary
            events_list = [{'campaign_name': event['campaign_name'], 'sponsor_username': event['sponsor_username']} for event in events]
            return jsonify(events_list)
        else:
            return jsonify([])  # No events found

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/fetch_events1', methods=['GET'])
def fetch_events1():
    sponsor_username = session.get('user')

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row  # To access columns by name
    cursor = conn.cursor()

    cursor.execute("""
        SELECT campaign_name, influencer_username
        FROM events
        WHERE sponsor_username = ?
    """, (sponsor_username,))
    events = cursor.fetchall()

    if events:
        event_list = [{"campaign_name": event[0], "influencer_username": event[1]} for event in events]
        return jsonify(event_list)
    else:
        return jsonify({"error": "No events found for this sponsor."})
      
if __name__ == '__main__':
    try:
        with sqlite3.connect("database.db") as conn:
            cur = conn.cursor()
            
            cur.execute("""
                    CREATE TABLE IF NOT EXISTS influencer_users(
                    username TEXT NOT NULL UNIQUE PRIMARY KEY,
                    password TEXT NOT NULL,
                    name TEXT,
                    niche TEXT,
                    category TEXT,
                    reach INTEGER,
                    phonenumber INTEGER,
                    platform_presence TEXT
                )
            """)
            cur.execute("""
                    CREATE TABLE IF NOT EXISTS influencer_users1(
                    username TEXT NOT NULL UNIQUE PRIMARY KEY,
                    password TEXT NOT NULL,
                    name TEXT,
                    niche TEXT,
                    category TEXT,
                    reach INTEGER,
                    phonenumber INTEGER,
                    platform_presence TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users(
                username TEXT NOT NULL UNIQUE PRIMARY KEY,
                password TEXT NOT NULL,
                role INTEGER NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS admin(
                username TEXT NOT NULL UNIQUE PRIMARY KEY,
                password TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sponsor_users (
                username TEXT NOT NULL UNIQUE PRIMARY KEY,
                password TEXT NOT NULL,
                name TEXT,
                industry TEXT,
                budget REAL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS campaigns (
                name TEXT NOT NULL UNIQUE PRIMARY KEY,
                description TEXT,
                start_date DATE,
                end_date DATE,
                budget REAL,
                visibility TEXT CHECK(visibility IN ('public', 'private')),
                goals TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ad_requests (
                campaign_name TEXT PRIMARY KEY,
                influencer_username TEXT,
                messages TEXT,
                requirements TEXT,
                payment_amount REAL,
                status TEXT CHECK(status IN ('pending', 'accepted', 'rejected')),
                FOREIGN KEY (campaign_name) REFERENCES campaigns(name),
                FOREIGN KEY (influencer_username) REFERENCES influencer_users(username)
                )
            """)
            cur.execute("""CREATE TABLE IF NOT EXISTS flagged_users_campaigns (
                name TEXT NOT NULL PRIMARY KEY,
                type TEXT NOT NULL,
                flag_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS ad_requests1 (
                campaign_name TEXT PRIMARY KEY,
                sponsor_username TEXT,
                influencer_username TEXT,
                messages TEXT,
                requirements TEXT,
                payment_amount REAL,
                status TEXT CHECK(status IN ('pending', 'accepted', 'rejected')),
                FOREIGN KEY (campaign_name) REFERENCES campaigns(name),
                FOREIGN KEY (influencer_username) REFERENCES influencer_users(username)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS events(
                campaign_name TEXT ,
                influencer_username TEXT,
                sponsor_username TEXT,
                PRIMARY KEY (campaign_name, influencer_username, sponsor_username)
                )
            """)
            try:
                cur.execute("INSERT INTO admin (username, password) VALUES (?, ?)", ('prasadrao', 'lbnm12345'))
                cur.execute("INSERT INTO users (username, password,role) VALUES (?, ?,?)", ('prasadrao', 'lbnm12345',1))
            except sqlite3.IntegrityError:
                print("Admin user already exists.")            
            print("Tables created successfully !")
            conn.commit()
    except Exception as e:
        print("Error in table creation or connecting to server: ",e)
    app.run(debug=True)