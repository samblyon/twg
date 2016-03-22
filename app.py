import os
import sendgrid
from sendgrid import SendGridError, SendGridClientError, SendGridServerError
from flask import Flask, render_template, json, request, redirect, session, url_for
from flask.ext.mysql import MySQL
from werkzeug import generate_password_hash, check_password_hash

mysql = MySQL()
app = Flask(__name__)
app.secret_key = 'nope'

#sendgrid configuration
sg = sendgrid.SendGridClient(os.environ['SENDGRID_USERNAME'],os.environ['SENDGRID_PASSWORD'])

#MySQL configurations
app.config['MYSQL_DATABASE_USER'] = os.environ['DATABASE_USER']
app.config['MYSQL_DATABASE_PASSWORD'] = os.environ['DATABASE_PASSWORD']
app.config['MYSQL_DATABASE_DB'] = os.environ['DATABASE_NAME']
app.config['MYSQL_DATABASE_HOST'] = os.environ['DATABASE_HOST']
app.config['MYSQL_DATABASE_CHARSET'] = 'utf8mb4'
app.config['MYSQL_USE_UNICODE'] = 'True'
mysql.init_app(app)

@app.route("/")
def main():
	if session.get('user'):
		return redirect('/showDashboard')
	else:
		return render_template('index.html')

@app.route("/showSignin")
def showSignin():
	if session.get('user'):
		return redirect('/showDashboard')
	else:
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

@app.route('/showDashboard/<int:post_id>')
def showDashboard_two(post_id):
	return render_template('dashboard.html',user=session.get('username'),anchor=('%s' % post_id))


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
			return render_template('error.html',error = 'Wrong Email address or Password!')

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

			# Add the new wait to the database
			conn = mysql.connect()
			cursor = conn.cursor()
			cursor.callproc('sp_addWait',(_title,_description,_user))
			data = cursor.fetchall()

			# Get the username of the poster
			cursor.execute('SELECT user_name FROM tbl_user WHERE user_id = %s',(_user,))
			result = cursor.fetchall()
			_username = result[0][0]
			

			if len(data) is 0:
				conn.commit()

				# Notify admin of new post
				params = (_username,_title,_description)
				message = sendgrid.Mail()
				message.add_to('sblyon@me.com')
				message.set_from('twg! <hi.from.twg@gmail.com>')
				message.set_subject('New Post by %s' % _username)
				message.set_html('%s is waiting %s for %s, twg-twg.herokuapp.com/showDashboard/922' % params)

				msg = sg.send(message)

				# Redirect to home
				return redirect('/showDashboard')
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

@app.route('/addComment',methods=['POST'])
def addComment():
	# return str(session.get('user'))
	try:
		if session.get('user'):
			_user = session.get('user')
			_comment = request.form['comment']
			_wait_id = request.form['id']

			conn = mysql.connect()
			cursor = conn.cursor()
			sql = ("insert into tbl_comment (wait_id, comment_text, poster_id, comment_date) values (%s,%s,%s, NOW())")
			params = (_wait_id,_comment,_user)
			cursor.execute(sql,params)
			data = cursor.fetchall()

			if len(data) is 0:
				conn.commit()

				# Get commenter username
				sql = ("SELECT u.user_name as 'poster' FROM tbl_user as u WHERE user_id = %s")
				params = (_user,)
				cursor.execute(sql, params)
				result = cursor.fetchall()
				_poster = result[0][0]

				# Get waiter username and email
				sql = ("SELECT u.user_name as 'waiter', u.user_username as 'waiter_email', u.user_id FROM tbl_user as u JOIN tbl_wait as w ON w.wait_user_id = u.user_id WHERE wait_id = %s" % _wait_id)
				cursor.execute(sql)
				result = cursor.fetchall()
				_waiter = result[0][0]
				_waiter_email = result[0][1]
				_waiter_user_id = result[0][2]

				#Notify admin of new comment
				message = sendgrid.Mail()
				message.add_to('sblyon@me.com')
				message.set_from('twg! <hi.from.twg@gmail.com>')
				params = (_poster,_waiter)
				message.set_subject('New comment by %s on %s\'s post' % params)
				message.set_text(_poster + ": " + _comment)

				msg = sg.send(message)

				# send comment email if user != wait poster
				if _user != _waiter_user_id:
					params = (_poster,_poster,_comment)
					message = sendgrid.Mail()
					message.add_to(_waiter_email)
					message.set_from('twg! <hi.from.twg@gmail.com>')
					message.set_subject('New comment from %s!' % _poster)
					message.set_html('<p>Hey, %s commented on your post!<br> %s was all like, \"%s\"<br><br>Post and comment are at twg-twg.herokuapp.com &#x1F604; <br><br><br><i>(Reply "Very hermit amaze quiet" to stop being told when people comment on your posts, or just if you feel like it.)</i></p>' % params)

					msg = sg.send(message)	

				return json.dumps({'status':'OK'})
			else:
				return json.dumps({'status':'ERROR'})
	except Exception as e:
		return str(e)			

@app.route('/getCommentsByWaitId',methods=['POST'])
def getCommentsByWaitId():
	try:
		if session.get('user'):
			_user = session.get('user')
			_wait_id = request.form['id']

			con = mysql.connect()
			cursor = con.cursor()
			sql = ("SELECT comment_id, comment_text, user_name, (TIMESTAMPDIFF(MINUTE, NOW(), tbl_comment.comment_date) * -1) AS timeElapsed FROM tbl_comment JOIN tbl_user on tbl_comment.poster_id = tbl_user.user_id WHERE wait_id = %s")
			params = (_wait_id,)
			cursor.execute(sql, params)
			comments = cursor.fetchall()

			comments_dict = []
			for comment in comments:
				comment_dict = {
					'Id': comment[0],
					'Comment': comment[1],
					'Poster': comment[2],
					'TimeElapsed': comment[3]
					}
				comments_dict.append(comment_dict)

			return json.dumps(comments_dict)
		else:
			return render_template('error.html', error = "Unauthorized Access")
	except Exception as e:
		return render_template('error.html', error = str(e))

@app.route('/deleteComment', methods=['POST'])
def deleteComment():
	try:
		if session.get('user'):
			_user = session.get('user')
			_id = request.form['id']

			conn = mysql.connect()
			cursor = conn.cursor()
			sql = ("DELETE FROM tbl_comment where poster_id = %s and comment_id = %s")
			params = (_user,_id)
			cursor.execute(sql,params)
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
			
			# get waits and ids
			cursor.execute("select w.wait_id, w.wait_title, w.wait_description, sum(i.wait_like), u.user_name, (TIMESTAMPDIFF(MINUTE, NOW(), w.wait_date) * -1) AS timeElapsed FROM tbl_likes AS i INNER JOIN tbl_wait as w ON i.wait_id = w.wait_id INNER JOIN tbl_user AS u ON w.wait_user_id = u.user_id GROUP BY w.wait_id ORDER BY w.wait_date DESC")
			wait_data = cursor.fetchall()

			# get dict of haslikeds by wait id
			cursor.execute("SELECT tbl_wait.wait_id, tbl_likes.wait_like FROM tbl_wait JOIN tbl_likes ON tbl_wait.wait_id = tbl_likes.wait_id WHERE user_id = %s group by wait_id",(_user,))
			has_liked_data = cursor.fetchall()

			#get dict of comment counts by wait id
			cursor.execute("SELECT wait_id, count(comment_text) FROM tbl_comment GROUP BY wait_id")
			comment_counts = cursor.fetchall()
			# return comment_counts
			
			# Convert nested lists to dictionaries
			hasLikeds = {}
			for wait in has_liked_data:
				hasLikeds[str(wait[0])] = wait[1]

			comment_counts_dict = {}
			for comment in comment_counts:
				comment_counts_dict[str(comment[0])] = comment[1]
			
			# Compose dic of waits. Get hasliked, comment count by wait id
			
			waits_dict = []
			for row in wait_data:
				_id = str(row[0])
				
				wait_dict = {
					'Id': row[0],
					'Title': row[1],
					'Description': row[2],
					'Like': str(row[3]),
					'HasLiked': str(hasLikeds[_id]) if _id in hasLikeds.keys() else 0,
					'Poster': row[4],
					'TimeElapsed': row[5],
					'CommentsCount': str(comment_counts_dict[_id]) if _id in comment_counts_dict.keys() else 0
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
				
				sql = ("select CAST(sum(wait_like) as char), CAST(exists(select 1 from tbl_likes where wait_id = %s and user_id = %s and wait_like = 1) as char) as hasLiked from tbl_likes where wait_id = %s")
				params = (_waitId, _user, _waitId)
				
				cursor.execute(sql,params)
				result = cursor.fetchall()

				# Send Like Email if Liked
				if result[0][1] == "1":
					# Get some params to send a like email.
					# Get post title, desc, poster email, username
					sql = ('select w.wait_title, w.wait_description, u.user_name, u.user_username as poster_email from tbl_user as u JOIN tbl_wait as w ON w.wait_user_id = u.user_id WHERE w.wait_id = %s')
					param = (_waitId,)
					cursor.execute(sql,param)
					poster_data = cursor.fetchall()
					
					_title = poster_data[0][0]
					_description = poster_data[0][1]
					poster_username = poster_data[0][2]
					poster_email = poster_data[0][3]

					# Get liker username
					sql = ('select u.user_name from tbl_user as u where u.user_id = %s')
					param = (_user,)
					cursor.execute(sql,param)
					liker_data = cursor.fetchall()
					liker_username = liker_data[0][0]
					# send like email
					params = (liker_username,poster_username,_title,_description)
					message = sendgrid.Mail()
					message.add_to(poster_email)
					message.set_from('twg! <hi.from.twg@gmail.com>')
					message.set_subject('%s liked your post!' % liker_username)
					message.set_html('<p>Hey, %s liked your post!<br>%s is waiting %s for %s<br>Want to see your post? Head to twg-twg.herokuapp.com &#x1F604; <br><br><i>(Reply "Fuck Off!" to stop being told when people like your posts, or just if you feel like it.)</i></p>' % params)

					msg = sg.send(message)				
					
				return json.dumps({'status':'OK','total':result[0][0],'likeStatus':result[0][1]})
			else:
				return render_template('error.html',error = 'An error occurred!')
		else:
			return render_template('error.html',error = 'Unauthorized Access')
	except Exception, e:
		return json.dumps({'status':'i am an error' + str(e)})
	finally:
		cursor.close()
		conn.close()

if __name__ == "__main__":
	# Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get("PORT", 5000))
    app.debug = True
    app.run(host='0.0.0.0', port=port)
