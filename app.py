import os
from flask import Flask, render_template, json, request, redirect, session
from flask.ext.mysql import MySQL
from werkzeug import generate_password_hash, check_password_hash

mysql = MySQL()
app = Flask(__name__)
app.secret_key = 'nope'

#MySQL configurations
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = 'balloon'
app.config['MYSQL_DATABASE_DB'] = 'BucketList'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
app.config['MYSQL_DATABASE_CHARSET'] = 'utf8mb4'
app.config['MYSQL_USE_UNICODE'] = 'True'
#mysql.init_app(app)

@app.route("/")
def main():
	if session.get('user'):
		return redirect('/showDashboard')
	else:
		return render_template('index.html')

@app.route("/showSignin")
def showSignin():
	return render_template('signin.html')

@app.route('/userHome')
def userHome():
	if session.get('user'):
		return render_template('userHome.html')
	else:
		return render_template('error.html',error= 'Unauthorized Access')

@app.route("/showAddWish")
def showAddWish():
	return render_template('addWish.html')

@app.route('/showSignUp')
def showSignUp():
	return render_template('signup.html')

@app.route('/logout')
def logout():
	session.pop('user',None)
	return redirect('/')

@app.route('/showDashboard')
def showDashboard():
	return render_template('dashboard.html',user= session.get('username'))

@app.route('/signUp',methods=['POST','GET'])
def signUp():
	try:
		#read the posted values from the UI
		_name = request.form['inputName']
		_email = request.form['inputEmail']
		_password = request.form['inputPassword']

		#validate the received values
		if _name and _email and _password:
		
			# all good, let's call MySQL
			conn = mysql.connect()
			cursor = conn.cursor()
			#salt the password using method from Werkzeug 
			_hashed_password = generate_password_hash(_password)

			#call the database procedure
			cursor.callproc('sp_createUser',(_name,_email,_hashed_password))

			#check if it went through, if so commit
			data = cursor.fetchall()

			if len(data) is 0:
				conn.commit()
				return json.dumps({'message':'User created successfully !'})
			else:
				return json.dumps({'error':str(data[0])})
		else:
			return json.dumps({'html':'<span>Enter the required fields</span>'})

	except Exception as e:
		return json.dumps({'error':str(e)})
	finally:
		cursor.close()
		conn.close()
		return render_template('signin.html')


@app.route('/validateLogin',methods=['POST'])
def validateLogin():
	try:
		_username = request.form['inputEmail']
		_password = request.form['inputPassword']

		conn = mysql.connect()
		cursor = conn.cursor()
		#cursor.callproc('sp_validateLogin',(_username,))
		cursor.execute("SELECT * FROM tbl_user where user_username='" + _username + "'")
		data = cursor.fetchall()

		if len(data) > 0:
			row = data[0]
			if check_password_hash(str(data[0][3]),_password):
				session['user'] = row[0]
				session['username'] = row[1]
				return redirect('/showDashboard')
			else:
				return render_template('error.html',error = 'Wrong Email address or Password!')
		else:
			return render_template('error.html',error = 'Len not 0 Wrong Email address or Password!')

	except Exception as e:
		return render_template('error.html',error = str(e))

	finally:
		cursor.close()
		conn.close()

@app.route('/addWish',methods=['POST'])
def addWish():
	try:
		if session.get('user'):
			_title = request.form['inputTitle']
			_description = request.form['inputDescription']
			_user = session.get('user')

			conn = mysql.connect()
			cursor = conn.cursor()
			cursor.callproc('sp_addWait',(_title,_description,_user))
			data = cursor.fetchall()

			if len(data) is 0:
				conn.commit()
				return redirect('/userHome')
			else:
				return render_template('error.html',error = 'An error occurred!')
				#return json.dumps({'error':str(data[0])})
		else:
			return render_template('error.html',error = 'Unauthorized Access')
	except Exception as e:
		return render_template('error.html',error = str(e))

	finally:
		cursor.close()
		conn.close()

@app.route('/getWait',methods=['GET'])
def getWait():
	try:
		if session.get('user'):
			_user = session.get('user')

			con = mysql.connect()
			cursor = con.cursor()
			cursor.callproc('sp_GetWaitByUser',(_user,))
			waits = cursor.fetchall()

			waits_dict = []
			for wait in waits:
				wait_dict = {
					'Id': wait[0],
					'Title': wait[1],
					'Description': wait[2],
					'Date': wait[4]}
				waits_dict.append(wait_dict)

			return json.dumps(waits_dict)
		else:
			return render_template('error.html', error = "Unauthorized Access")
	except Exception as e:
		return render_template('error.html', error = str(e))

@app.route('/getWaitById',methods=['POST'])
def getWaitById():
	try:
		if session.get('user'):
			_id = request.form['id']
			_user = session.get('user')

			conn = mysql.connect()
			cursor = conn.cursor()
			cursor.callproc('sp_GetWaitById',(_id,_user,))
			result = cursor.fetchall()

			wait = []
			wait.append({'Id':result[0][0],'Title':result[0][1],'Description':result[0][2]})

			return json.dumps(wait)
		else:
			return render_template('error.html', error = 'Unauthorized Access')

	except Exception, e:
		return render_template('error.html', error = str(e))
	finally:
		cursor.close()
		conn.close()

@app.route('/getAllWaits')
def getAllWaits():
	try:
		if session.get('user'):
			_user = session.get('user')
			conn = mysql.connect()
			cursor = conn.cursor()
			cursor.execute("SELECT tbl_wait.wait_id,tbl_wait.wait_title,tbl_wait.wait_description,getSum(wait_id),hasLiked(wait_id, %s),tbl_user.user_name,(TIMESTAMPDIFF(MINUTE, NOW(), wait_date) * - 1) FROM tbl_wait, tbl_user WHERE tbl_wait.wait_user_id = tbl_user.user_id ORDER BY wait_date DESC",(_user,))
			# cursor.callproc('sp_GetAllWaitsTwo',(_user,))
			result = cursor.fetchall()
			waits_dict = []
			for wait in result:
				wait_dict = {
					'Id': wait[0],
					'Title': wait[1],
					'Description': wait[2],
					'Like': wait[3],
					'HasLiked': wait[4],
					'Poster': wait[5],
					'TimeElapsed': wait[6]
					}
				waits_dict.append(wait_dict)

			return json.dumps(waits_dict)

		else:
			return render_template('error.html', error = 'Unauthorized Access')

	except Exception, e:
		return render_template('error.html', error = str(e))
	finally:
		cursor.close()
		conn.close()

@app.route('/updateWait', methods=['POST'])
def updateWish():
    try:
        if session.get('user'):
            _user = session.get('user')
            _title = request.form['title']
            _description = request.form['description']
            _wait_id = request.form['id']

            

            conn = mysql.connect()
            cursor = conn.cursor()
            cursor.callproc('sp_updateWait',(_title,_description,_wait_id,_user))
            data = cursor.fetchall()

            if len(data) is 0:
                conn.commit()
                return json.dumps({'status':'OK'})
            else:
                return json.dumps({'status':'ERROR'})
    except Exception as e:
        return json.dumps({'status':'Unauthorized access'})
    finally:
        cursor.close()
        conn.close()

@app.route('/deleteWait', methods=['POST'])
def deleteWait():
	try:
		if session.get('user'):
			_user = session.get('user')
			_id = request.form['id']

			conn = mysql.connect()
			cursor = conn.cursor()
			cursor.callproc('sp_deleteWait',(_id,_user))
			result = cursor.fetchall()

			if len(result) is 0:
				conn.commit()
				return json.dumps({'status':'OK'})
			else:
				return json.dumps({'status':'An Error occured'})
		else:
			return render_template('error.html',error = 'Unauthorized Access')
	except Exception, e:
		return json.dumps({'status':str(e)})
	finally:
		cursor.close()
		conn.close()

@app.route('/addUpdateLike',methods=['POST'])
def addUpdateLike():
	try:
		if session.get('user'):
			_waitId = request.form['wait']
			_user = session.get('user')
			_like = request.form['like']

			conn = mysql.connect()
			cursor = conn.cursor()
			cursor.callproc('sp_AddUpdateLikes',(_waitId,_user,_like))
			result = cursor.fetchall()

			if len(result) is 0:
				conn.commit()
				cursor.close()
				conn.close()

				conn = mysql.connect()
				cursor = conn.cursor()
				cursor.callproc('sp_getLikeStatus',(_waitId,_user,))
				result = cursor.fetchall()

				return json.dumps({'status':'OK','total':result[0][0],'likeStatus':result[0][1]})
			else:
				return render_template('error.html',error = 'An error occurred!')
		else:
			return render_template('error.html',error = 'Unauthorized Access')
	except Exception, e:
		return json.dumps({'status':str(e)})
	finally:
		cursor.close()
		conn.close()

if __name__ == "__main__":
	# Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)