import fitbit
from flask import render_template, flash, redirect, session, url_for, request, jsonify, send_from_directory
from random import choice
from highcharts import Chart
from flask_oauthlib.client import OAuth
import os
import json
import humanize
import dateutil.parser
from numpy import average
from config import get_var
import datetime
import requests
import logging
from datetime import datetime, timedelta

from flask import Flask, flash
from mysqlconnection import MySQLConnector
from flask.ext.bcrypt import Bcrypt
from flask_pymongo import PyMongo
import re
from fitbit.api import FitbitOauth2Client

app = Flask(__name__)
bcrypt = Bcrypt(app)
mysql = MySQLConnector(app, 'cmpe280')
app.secret_key = "TheSecretLifeOfTheKeys"
logger = logging.getLogger('mylogger')

#app.config['MONGO_DBNAME'] = 'mydb'
#app.config['MONGO_URI'] = 'mongodb://35.164.225.200:27017/fitbit'
app.config['MONGO_URI'] = 'mongodb://web2:27017/fitbit'
mongo = PyMongo(app)

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9.+_-]+@[a-zA-Z0-9._-]+\.[a-zA-Z]+$')
#Minimum 8 characters at least 1 Uppercase Alphabet, 1 Lowercase Alphabet and 1 Number:
PASSWORD_REGEX = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d]+$')

pushNotifyObject={}
pushNotifyObject['recommedation']=''
pushNotifyObject['calorieExceeds']=''
pushNotifyObject['calorieAvailable']=''


try:
    from urllib.parse import urlencode
except ImportError:
    # Python 2.x
    from urllib import urlencode

from requests_oauthlib import OAuth2, OAuth2Session
from oauthlib.oauth2.rfc6749.errors import TokenExpiredError
from fitbit.exceptions import (BadResponse, DeleteError, HTTPBadRequest,
                               HTTPUnauthorized, HTTPForbidden,
                               HTTPServerError, HTTPConflict, HTTPNotFound,
                               HTTPTooManyRequests)
from fitbit.utils import curry

CONVERSION = {
    "en_US": "Pounds"
}

class Fitbit(object):
    US = 'en_US'
    METRIC = 'en_UK'

    API_ENDPOINT = "https://api.fitbit.com"
    API_VERSION = 1
    WEEK_DAYS = ['SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY']
    PERIODS = ['1d', '7d', '30d', '1w', '1m', '3m', '6m', '1y', 'max']

    RESOURCE_LIST = [
        'body',
        'activities',
        'foods/log',
        'foods/log/water',
        'sleep',
        'heart',
        'bp',
        'glucose',
    ]

    QUALIFIERS = [
        'recent',
        'favorite',
        'frequent',
    ]

    def __init__(self, client_id, client_secret, system=US, **kwargs):

        self.system = system
        self.client = FitbitOauth2Client(client_id, client_secret, **kwargs)
        # All of these use the same patterns, define the method for accessing
        # creating and deleting records once, and use curry to make individual
        # Methods for each
        
    def make_request(self, *args, **kwargs):
        # This should handle data level errors, improper requests, and bad
        # serialization
        headers = kwargs.get('headers', {})
        headers.update({'Accept-Language': self.system})
        kwargs['headers'] = headers

        method = kwargs.get('method', 'POST' if 'data' in kwargs else 'GET')
        response = self.client.make_request(*args, **kwargs)
        if response.status_code == 202:
            return True
        if method == 'DELETE':
            if response.status_code == 204:
                return True
            else:
                raise DeleteError(response)
        try:
            rep = json.loads(response.content.decode('utf8'))
        except ValueError:
            raise BadResponse

        return rep

    def get_user_profile(self, user_id=None):
        """
        Get a user profile. You can get other user's profile information
        by passing user_id, or you can get the current user's by not passing
        a user_id

        .. note:
            This is not the same format that the GET comes back in, GET requests
            are wrapped in {'user': <dict of user data>}

        https://wiki.fitbit.com/display/API/API-Get-User-Info
        """
        url = "{0}/{1}/user/{2}/profile.json".format(*self._get_common_args(user_id))
        return self.make_request(url)

    def get_device_info(self):
        """
        https://wiki.fitbit.com/display/API/API-Get-Devices
        """
        url = "{0}/{1}/user/-/devices.json".format(*self._get_common_args())
        return self.make_request(url)

    def _get_common_args(self, user_id=None):
        common_args = (self.API_ENDPOINT, self.API_VERSION,)
        if not user_id:
            user_id = '-'
        common_args += (user_id,)
        return common_args

    def _get_date_string(self, date):
        if not isinstance(date, str):
            return date.strftime('%Y-%m-%d')
        return date

    def output_json(dp, resource, datasequence_color, graph_type):
        """ Return a properly formatted JSON file for Statusboard """
        graph_title = ''
        datapoints = list()
        
        for x in dp:
            datapoints.append(
                {'title': x['dateTime'], 'value': float(x['value'])})
            datasequences = []
            datasequences.append({
            "title": resource,
            # "color":        datasequence_color,
            "datapoints": datapoints,
            })

        graph = dict(graph={
        'title': graph_title,
        'yAxis': {'hide': False},
        'xAxis': {'hide': False},
        'refreshEveryNSeconds': 600,
        'type': graph_type,
        'datasequences': datasequences,
        })
        return graph

    def time_series(self, resource, user_id=None, base_date='today',
                    period=None, end_date=None):
        """
        The time series is a LOT of methods, (documented at url below) so they
        don't get their own method. They all follow the same patterns, and
        return similar formats.
        Taking liberty, this assumes a base_date of today, the current user,
        and a 1d period.
        https://wiki.fitbit.com/display/API/API-Get-Time-Series
        """
        if period and end_date:
            raise TypeError("Either end_date or period can be specified, not both")

        if end_date:
            end = self._get_date_string(end_date)
        else:
            if not period in Fitbit.PERIODS:
                raise ValueError("Period must be one of %s"
                                 % ','.join(Fitbit.PERIODS))
            end = period

        url = "{0}/{1}/user/{2}/{resource}/date/{base_date}/{end}.json".format(
            *self._get_common_args(user_id),
            resource=resource,
            base_date=self._get_date_string(base_date),
            end=end
        )
        return self.make_request(url)


    def intraday_time_series(self, resource, base_date='today', detail_level='1min', start_time=None, end_time=None):
        """
        The intraday time series extends the functionality of the regular time series, but returning data at a
        more granular level for a single day, defaulting to 1 minute intervals. To access this feature, one must
        send an email to api@fitbit.com and request to have access to the Partner API
        (see https://wiki.fitbit.com/display/API/Fitbit+Partner+API). For details on the resources available, see:
        https://wiki.fitbit.com/display/API/API-Get-Intraday-Time-Series
        """

        # Check that the time range is valid
        time_test = lambda t: not (t is None or isinstance(t, str) and not t)
        time_map = list(map(time_test, [start_time, end_time]))
        if not all(time_map) and any(time_map):
            raise TypeError('You must provide both the end and start time or neither')

        """
        Per
        https://wiki.fitbit.com/display/API/API-Get-Intraday-Time-Series
        the detail-level is now (OAuth 2.0 ):
        either "1min" or "15min" (optional). "1sec" for heart rate.
        """
        if not detail_level in ['1sec', '1min', '15min']:
            raise ValueError("Period must be either '1sec', '1min', or '15min'")

        url = "{0}/{1}/user/-/{resource}/date/{base_date}/1d/{detail_level}".format(
            *self._get_common_args(),
            resource=resource,
            base_date=self._get_date_string(base_date),
            detail_level=detail_level
        )

        if all(time_map):
            url = url + '/time'
            for time in [start_time, end_time]:
                time_str = time
                if not isinstance(time_str, str):
                    time_str = time.strftime('%H:%M')
                url = url + ('/%s' % (time_str))

        url = url + '.json'

        return self.make_request(url)


    def get_bodyweight(self, base_date=None, user_id=None, period=None, end_date=None):
        """
        https://wiki.fitbit.com/display/API/API-Get-Body-Weight
        base_date should be a datetime.date object (defaults to today),
        period can be '1d', '7d', '30d', '1w', '1m', '3m', '6m', '1y', 'max' or None
        end_date should be a datetime.date object, or None.
        You can specify period or end_date, or neither, but not both.
        """
        return self._get_body('weight', base_date, user_id, period, end_date)

    def _get_body(self, type_, base_date=None, user_id=None, period=None,
                  end_date=None):
        if not base_date:
            base_date = datetime.today().strftime('%Y-%m-%d')

        if period and end_date:
            raise TypeError("Either end_date or period can be specified, not both")

        base_date_string = self._get_date_string(base_date)

        kwargs = {'type_': type_}
        base_url = "{0}/{1}/user/{2}/body/log/{type_}/date/{date_string}.json"
        if period:
            if not period in Fitbit.PERIODS:
                raise ValueError("Period must be one of %s" %
                                 ','.join(Fitbit.PERIODS))
            kwargs['date_string'] = '/'.join([base_date_string, period])
        elif end_date:
            end_string = self._get_date_string(end_date)
            kwargs['date_string'] = '/'.join([base_date_string, end_string])
        else:
            kwargs['date_string'] = base_date_string

        url = base_url.format(*self._get_common_args(user_id), **kwargs)
        return self.make_request(url)


# Routes
# ----------------------------

@app.errorhandler(404)
def page_not_found(e):
    # app.logger.info('404')
    return render_template('404.html'), 404


@app.errorhandler(500)
def page_not_found(e):
    # app.logger.info('404')
    return render_template('500.html'), 404


@app.route('/getrecommendation')
def getRecommendation():
    try:
	data=[["N/A","Server not Found"]]
        url = 'http://web2:3000/recommend'
        params = dict(calorie=session['availableCalorie'])
	if int(session['availableCalorie']) >= 0:
		resp = requests.get(url=url, params=params)
		if resp.status_code == 404:
		    data = {"0","Server not Found"}
		else:
		    data = json.loads(resp.text)
	else:
		data = [["0","Calorie Goal For the Day Exceeded."]]
    except Exception as error : 
	logging.exception("message")
    return render_template('recommendation.html', data=data)

@app.route('/')
def index():
    try:
        if not session.get('fitbit_keys', False):
            return redirect(url_for('start'))
        userprofile_id = session['user_profile']['user']['encodedId']
        steps = get_activity(userprofile_id, 'steps', period='1d', return_as='raw')[0]['value']
	weights = fit.get_bodyweight(user_id=userprofile_id, period='1m')['weight']
	weight_last = weights[-1]['weight']
	if weight_last is not None:
		session['weight']=weight_last
        calories = get_activity(userprofile_id, 'calories', period='1d', return_as='raw')[0]['value']
	heartJson = get_activity(userprofile_id, 'heart', period='1d', return_as='raw')[0]['value']
	if 'restingHeartRate' in heartJson:
        	heartRate=heartJson['restingHeartRate']
	else:
        	heartRate =65
        weights = get_activity(userprofile_id, 'weight', period='1w', return_as='raw')
        weight0 = weights[0]['value']
        weightn = weights[-1]['value']
        diff = (float(weight0) - float(weightn))
        bmi=int(session['bmi'])
        calorieEstimate(calories)
        if diff > 0:
            diff = "+" + str(diff)
        else:
            diff = str(diff)
        sleep = get_activity(userprofile_id, 'timeInBed', period='1d', return_as='raw')[0]['value']
        chartdata = get_activity(userprofile_id, 'steps', period='1w', return_as='raw')
        weight_unit = CONVERSION[session['user_profile']['user']['weightUnit']]
        return render_template('home.html', Bmi = bmi, caloriesConsumed=session['caloriesConsumed'], caloriesEstimated=session['availableCalorie'], heartRate=heartRate,steps=steps, calories=calories, weight=diff, sleep=sleep, chartdata=chartdata,weights=weights, weight_unit=weight_unit)
    except Exception as error : 
	logging.exception("message")

@app.route('/profileDetails')
def profileDetails():
    if not session.get('fitbit_keys', False):
        return redirect(url_for('start'))
    return render_template('profileDetails.html')


@app.route('/profileDetailsUpdate', methods=["POST"])
def profileDetailsUpdate():
    try:
	session['weight'] = request.form['curweight']
	session['goal'] = request.form['goalweight']
	heightBmi=float(session['height'])*float(session['height'])
	session['bmi']=int((float(session['weight'])*703)/heightBmi)
	query = "Update UserProfile set Weight= :weight, goal=:goal,bmi=:bmi WHERE UserId = :userId"
	data = {
	"weight" : session['weight'],
	"goal" : session['goal'],
	"bmi" : session['bmi'],
	"userId" : session['user_Id']
	}
	mysql.query_db(query, data)
	userprofile_id = session['user_profile']['user']['encodedId']
	caloriesBurned = get_activity(userprofile_id, 'calories', period='1d', return_as='raw')[0]['value']
	calorieEstimate(caloriesBurned)
	print("Updated Successfully")
    except Exception as error : 
	logging.exception("message")
    return redirect(url_for('dashboard'))


@app.route('/steps')
def steps():
    try:
        if not session.get('fitbit_keys', False):
            return redirect(url_for('start'))
        userprofile_id = session['user_profile']['user']['encodedId']
        all_steps = get_activity(userprofile_id, 'steps', period='max', return_as="raw")
        year_steps = get_activity(userprofile_id, 'steps', period='1y', return_as="raw")
        month_steps = get_activity(userprofile_id, 'steps', period='1m', return_as="raw")
        week_steps = get_activity(userprofile_id, 'steps', period='1w', return_as="raw")
        day_steps = get_activity(userprofile_id, 'steps', period='1d', return_as="raw")
        statsbar = [
            {
                'icon': "fa-step-forward fa-rotate-270",
                'title': "All Time Max Steps",
                'value': max([int(d.get('value')) for d in all_steps]) 
            },
            {
                'icon': "fa-step-forward fa-rotate-90",
                'title': "Average Daily Steps",
                'value': int(average([int(d.get('value')) for d in all_steps]))
            },
            {
                'icon': "fa-calendar",
                'title': "Month Max Steps",
                'value': max([int(d.get('value')) for d in month_steps])
            },
            {
                'icon': "fa-balance-scale",
                'title': "Steps Today",
                'value': max([int(d.get('value')) for d in day_steps])
            }
        ]
        boxplot_data = group_by_month(clean_max(all_steps))
        charts = [
            {
                "title": "Steps for Past Month",
                "id": "month-steps",
                "chart": Chart("Steps for Past Month",
                               xType="datetime",
                               xCategories=[d.get('dateTime') for d in month_steps]
                               ).add_series("Steps",
                                            data=[d.get('value') for d in month_steps],
                                            type="column")

            },
            {
                "title": "Average Steps per Month",
                "id": "month-average",
                "chart": Chart(
                    "Average Steps Per Month",
                    xtype="datetime",
                    xCategories=[d.get('month') for d in boxplot_data]
                ).add_series(
                    "Steps",
                    data=[d.get('plot') for d in boxplot_data],
                    type="boxplot"
                ).add_series(
                    "Outliers",
                    data=[[d.get('index'), ] + d.get('outliers') for d in boxplot_data if d.get('outliers', False)],
                    type="scatter"
                )
            },
            {
                "title": "Monthly Average Yearcycle",
                "id": "yearcycle",
                "chart": Chart(
                    "Monthly Average Yearcycle",
                    xCategories=['Jan', 'Feb', 'Mar', "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                ).add_raw_series(get_yearcycle(clean_max(all_steps), return_as="raw"))
            }
            ,
            {
                "title": "Average for Time Period",
                "id": "time-period",
                "chart": Chart(
                    "Average Steps For Different Time Periods",
                    xCategories=["All Time", "Year", "Month", "Week"]
                ).add_raw_series(get_periods(clean_max(all_steps), year_steps, month_steps, week_steps))
            }
        ]
        
    except Exception as error : 
	logging.exception("message")
    return render_template('statpage.html', title="Steps", statsbar=statsbar, charts=charts, all_steps=all_steps, year_steps=year_steps, month_steps=month_steps, week_steps=week_steps, day_steps=day_steps, boxplot_data=boxplot_data)

@app.route('/calories')
def calories():
    try:
	if not session.get('fitbit_keys', False):
		return redirect(url_for('start'))
	# Fetches
	monthlyCalorieData = fit.time_series('activities/calories', base_date='today',period='1m')['activities-calories']
    except Exception as error : 
	logging.exception("message")
    return render_template('calories.html', monthlyCalorieData=monthlyCalorieData)


@app.route('/users/new', methods=["POST"])
def create():
    try:
	result = []
	session['email'] = request.form['email']
	session['password'] = request.form['password']
	session['name'] = request.form['name']

	if len(result) == 0:
		password = session['password']
		pw_hash = bcrypt.generate_password_hash(password)
		query = "INSERT INTO User ( Name, EmailId, Password) VALUES (:name,:email,:password)"
		data = {
		    "email" : session['email'],
		    "password" : pw_hash,
		    "name" : session['name']
		}
		mysql.query_db(query, data)
		# session.pop('email')
		# session.pop('password')
		query1 = "SELECT userId FROM User WHERE EmailId = :email"
		data = { "email" : session['email']}
		session['user_Id'] = mysql.query_db(query1,data)[0]['userId']
		flash("Registered Successfully",'success')
		return redirect(url_for('registration1'))
	else: 
		for message in result:
		    flash(message,'error')
    except Exception as error : 
	logging.exception("message")
    return redirect(url_for('registration'))


@app.route('/users/profile', methods=["POST"])
def userProfile():
    try:
	session['height'] = request.form['height']
	session['heightinch'] = request.form['heightinch']
	session['gender'] = request.form['gender']
	session['weight'] = request.form['weight']
	session['goal'] = request.form['goal']
	session['age'] = request.form['age']
	heightBmi=((float(request.form['height'])*12)+float(request.form['heightinch']))*((float(request.form['height'])*12)+float(request.form['heightinch']))
	print("heightBmi..... ")
	print(heightBmi)
	session['bmi']=int((float(request.form['weight'])*703)/heightBmi)
	print(session['bmi'])
	#session['bmi'] = float(round(((float(request.form['weight']) / ((float(request.form['height'])*12+float(request.form['heightinch']))*(float(request.form['height'])*12+float(request.form['heightinch']))))*703),2))
	query = "INSERT INTO UserProfile ( Weight, Height, Goal, Gender, BMI, Age, UserId) VALUES (:weight, :height,:goal,:gender,:bmi,:age,:userId)"
	data = {
	"weight" : session['weight'],
	"height" : str(int(session['height'])*12+int(session['heightinch'])),
	"goal" : session['goal'],
	"gender" : session['gender'],
	"bmi" : session['bmi'],
	"age" : session['age'],
	"userId" : session['user_Id']
	}
	mysql.query_db(query, data)
	session.pop('height')
	session.pop('heightinch')
	session.pop('goal')
	session.pop('age')
	session.pop('bmi')
	flash("Registered Successfully",'success')
    except Exception as error : 
	logging.exception("message")
    return redirect(url_for('signin'))
    

@app.route('/users/login', methods=["POST"])
def newlogin():
    try:
    	error = None
	email = request.form['email']
	password = request.form['password']
	query = "SELECT * FROM User WHERE EmailId = :email LIMIT 1"
	data = { "email": email }
	user = mysql.query_db(query,data)
	if user:
		if bcrypt.check_password_hash(user[0]['Password'], password):
		    print "LOGIN SUCCESSFUL"
        	    session['email']=email
		    error = "LOGIN SUCCESSFUL"
		    # flash("LOGIN SUCCESSFUL",'success')
		    return redirect(url_for('customurl'))
		else:
		    print "Invalid Credentials."
		    error = "Invalid Credentials."
    		    return redirect(url_for('signin',error=error))
	else:
		print "LOGIN UNSUCCESSFUL"
		error = "Invalid Credentials."
		flash("Invalid Credentials.",'error')
    		return redirect(url_for('signin',error=error))
    except Exception as error : 
	logging.exception("message")


@app.route('/food')
def foodEntry():
    return render_template('food_entry.html')

@app.route('/weight')
def weight():
    try:
	if not session.get('fitbit_keys', False):
		return redirect(url_for('start'))
	# Fetches
	userprofile_id = session['user_profile']['user']['encodedId']
	weight_unit = CONVERSION[session['user_profile']['user']['weightUnit']]
	weights = fit.get_bodyweight(user_id=userprofile_id, period='1m')['weight']
	all_weight = get_activity(userprofile_id, 'weight', period='max', return_as='raw')
	year_weight = get_activity(userprofile_id, 'weight', period='1y', return_as='raw')
	month_weight = get_activity(userprofile_id, 'weight', period='1m', return_as='raw')
	week_weight = get_activity(userprofile_id, 'weight', period='1w', return_as='raw')
	# series setup
	chartdata = group_by_day(weights, 'weight')
	boxplot = group_by_month(all_weight)
	yearcycle = get_yearcycle(all_weight)
	periods = get_periods(all_weight, year_weight, month_weight, week_weight)
	weight_max = max([d.get('value') for d in all_weight])
	weight_min = min([d.get('value') for d in all_weight])
	weight_last = weights[-1]['weight']
	month_max = max([d.get('value') for d in month_weight])
	statsbar = [
	{
	    'icon': "fa-step-forward fa-rotate-270",
	    'title': "All Time Max Weight",
	    'value': weight_max
	},
	{
	    'icon': "fa-step-forward fa-rotate-90",
	    'title': "All Time Min Weight",
	    'value': weight_min
	},
	{
	    'icon': "fa-calendar",
	    'title': "Month Max Weight",
	    'value': month_max
	},
	{
	    'icon': "fa-balance-scale",
	    'title': "Last Weight",
	    'value': weight_last
	}
	]
	charts = [
	{
	    "title": "Weight Fluctuations for Past Month",
	    "id": "weight",
	},
	{
	    "title": "Average Weight All Time",
	    "id": "allweight",
	},
	{
	    "title": "Monthly Boxplot",
	    "id": "boxplot",
	},
	{
	    "title": "Yearly Cycle",
	    "id": "yearcycle",
	},
	{
	    "title": "Averages for Periods",
	    "id": "period",
	},

	]
    except Exception as error : 
	logging.exception("message")
    return render_template('weight.html', weights=weights, weight_unit=weight_unit, chartdata=chartdata,
                           all_weight=all_weight, boxplot=boxplot, yearcycle=yearcycle, periods=periods,
                           statsbar=statsbar, charts=charts)


@app.route('/signin')
def signin():
    error=''
    if 'error' in request.args:
        error = request.args.get('error')
    return render_template('login.html',error=error)

@app.route('/start')
def start():
    return render_template('start.html')

@app.route('/registration')
def registration():
    return render_template('registration.html')

@app.route('/registration1')
def registration1():
    # email=request.form['Email']
    # pwd=request.form['Password']
    # return render_template('registration1.html', name=name, email=email)
    return render_template('registration1.html')

@app.route('/heartrate')
def heartRate():
    try:
	if not session.get('fitbit_keys', False):
	     return redirect(url_for('start'))
	# Fetches
	yesterdayDate=datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d')
	print(yesterdayDate)
	chartdata = fit.intraday_time_series('activities/heart', base_date=yesterdayDate, detail_level='15min', start_time='00:00', end_time='23:59')['activities-heart-intraday']['dataset']
	monthChartData = fit.time_series('activities/heart', base_date='today',period='1m')
	#print(chartdata)
    except Exception as error :
	logging.exception("message")
    	return render_template('heartrate.html', heartdata=[{"value": 0, "time": "09:15:00"}, {"value": 0, "time": "23:45:00"}])
    return render_template('heartrate.html', heartdata=chartdata, monthChartData=monthChartData)


@app.route('/heartrateDetail')
def heartrateDetail():
    return render_template('heartrateDetail.html')

@app.route('/customurl')
def customurl():
    if 'code' in request.args:
        code = request.args.get('code')
    return render_template('customurl.html')

@app.route('/login')
def login():
    try:
        """ Start login process
        """
	if 'email' in session:
        	email=session['email']
		print("email is...")
		print(email)
	else:
		email = 'yasham1990@gmail.com'
        	session['email'] = email
        if 'access-token' in request.args:
            access_token = request.args.get('access-token')
        if 'refresh-token' in request.args:
            refresh_token = request.args.get('refresh-token')
        if 'userId' in request.args:
            user_key = request.args.get('userId')
        if 'secretKey' in request.args:
            user_secret = request.args.get('secretKey')
        global fit
        fit=Fitbit(user_key,user_secret,access_token=access_token, refresh_token=refresh_token)
        session['fitbit_keys'] = (email, user_key, user_secret)
        query = "SELECT userId FROM User WHERE EmailId = :email"
        data = { "email" : email}
        userId = mysql.query_db(query,data)[0]['userId']
        session['user_Id'] = userId;
        query1 = "SELECT Weight, Gender, Height, Goal, BMI, Age FROM UserProfile WHERE UserId = :userId"
        data1 = { "userId" : userId}
        userProf = mysql.query_db(query1,data1)[0]
	if userProf is not None:
		session['weight'] = userProf['Weight']
		session['height'] = userProf['Height']
		session['gender'] =userProf['Gender']
		session['goal'] = userProf['Goal']
		session['bmi'] = userProf['BMI']
		session['age'] = userProf['Age']
	else:
        	print("userId is...")
        session['user_profile'] = fit.get_user_profile()
	session['functionName']='OnLogin'
    except Exception as error :
	logging.exception("message")
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    session['functionName']='OnDashboard'
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    try:
	""" Logout pops session cookie """
	session.pop('fitbit_keys', None)
	session.pop('user_profile', None)
	session.pop('weight', None)
	session.pop('height', None)
	session.pop('goal', None)
	session.pop('bmi', None)
	session.pop('age', None)
	session.pop('caloriesConsumed', None)
	session.pop('availableCalorie', None)
	session.pop('email', None)
	session.pop('password', None)
	session.pop('name', None)
	session.pop('user_Id', None)
	session.pop('heightinch', None)
	session.pop('gender', None)
	session.pop('functionName', None)
	session.pop('calorieEst', None)
	session.pop('caloriesConsumed', None)
    except Exception as error :
	logging.exception("message")
    return redirect(url_for('signin'))

@app.route('/fooditems', methods=['GET'])
def get_items():
    try:
        keyword="^"+request.args.get('keyword')+".*"
        itemsCur = mongo.db.food_data
        abc = itemsCur.find({"name":{"$regex":keyword, "$options" : "-i" }},{"name":1,"_id":0}).limit(10)
        output = []
        for doc in abc:
            output.append({'name':doc['name']})
    except Exception as error : 
	logging.exception("message")
    return jsonify({'result' : output})

@app.route('/fooditemsadd', methods=["POST"])
def fooditemsadd():
    try:
        fooditemname = request.form['fooditemname']
        foodquantity = request.form['qauntity']
    	fooddata = mongo.db.food_data
        docResult = fooddata.find({"name":fooditemname},{"_id":0,"__v":0});
        for doc in docResult:
            calEstimate = int(doc['calories'])
        session['calorieEst'] = int((float(foodquantity)*calEstimate)/100)
        query = "INSERT INTO FoodEntry ( Item, Quantity, TimeStamp, UserId, calorieEst) VALUES (:foodname, :foodquantity, CURDATE(),:userId, :calorieEst)"
        data = {
            "foodname" : fooditemname,
            "foodquantity" : foodquantity,
            "userId" : session['user_Id'],
            "calorieEst" : session['calorieEst']
        }
        mysql.query_db(query, data)
	userprofile_id = session['user_profile']['user']['encodedId']
	caloriesBurned = get_activity(userprofile_id, 'calories', period='1d', return_as='raw')[0]['value']
	calorieEstimate(caloriesBurned)
	session['functionName']='FoodEntry'
    except Exception as error : 
	logging.exception("message")
    return redirect(url_for('dashboard'))

# API
# ----------------------------

@app.route('/u/<user_id>/<resource>/<period>')
def get_activity(user_id, resource, period='1w', return_as='json'):
    """ Function to pull data from Fitbit API and return as json or raw specific to activities """
    global dash_resource
    app.logger.info('resource, %s, %s, %s, %s, %s' %
                    (user_id, resource, period, return_as, request.remote_addr))

    ''' Use  API to return resource data '''

    slash_resource = 'activities/' + resource

    colors = (
        'yellow',
        'green',
        'red',
        'blue',
        'mediumGray',
        'aqua',
        'orange',
        'lightGray')

    datasequence_color = choice(colors)

    if period in ('1d', '1w', '1m'):
        graph_type = 'bar'
    else:
        graph_type = 'line'

    # Activity Data
    if resource in ('distance',
                    'steps',
                    'heart',
                    'floors',
                    'calories',
                    'elevation',
                    'minutesSedentary',
                    'minutesLightlyActive',
                    'minutesFairlyActive',
                    'minutesVeryActive',
                    'activeScore',
                    'activityCalories'):
        slash_resource = 'activities/' + resource
        dash_resource = 'activities-' + resource

    # Sleep Data
    if resource in ('startTime',
                    'startTime',
                    'timeInBed',
                    'minutesAsleep',
                    'awakeningsCount',
                    'minutesAwake',
                    'minutesToFallAsleep',
                    'minutesAfterWakeup',
                    'efficiency'):
        slash_resource = 'sleep/' + resource
        dash_resource = 'sleep-' + resource

    if resource in ('weight',
                    'bmi',
                    'fat'):
        slash_resource = 'body/' + resource
        dash_resource = 'body-' + resource

    the_data = fit.time_series(
        slash_resource, base_date='today', period=period)[dash_resource]

    if return_as == 'raw':
        return the_data
    if return_as == 'json':
        return jsonify(output_json(the_data, resource, datasequence_color, graph_type))


# Filters
# ----------------------------

@app.template_filter()
def natural_time(datetime):
    """Filter used to convert Fitbit API's iso formatted text into
    an easy to read humanized format"""
    a = humanize.naturaltime(dateutil.parser.parse(datetime))
    return a


@app.template_filter()
def natural_number(number):
    """ Filter used to present integers cleanly """
    a = humanize.intcomma(number)
    return a


# Building Blocks
# ----------------------------

def output_json(dp, resource, datasequence_color, graph_type):
    """ Return a properly formatted JSON file for Statusboard """
    graph_title = ''
    datapoints = list()
    for x in dp:
        datapoints.append(
            {'title': x['dateTime'], 'value': float(x['value'])})
    datasequences = []
    datasequences.append({
        "title": resource,
        # "color":        datasequence_color,
        "datapoints": datapoints,
    })

    graph = dict(graph={
        'title': graph_title,
        'yAxis': {'hide': False},
        'xAxis': {'hide': False},
        'refreshEveryNSeconds': 600,
        'type': graph_type,
        'datasequences': datasequences,
    })

    return graph


# Graph Helpers
# ------------------------

def group_by_day(data, attr):
    grouped = []
    days = {}
    for point in data:
        days.setdefault(point['date'], []).append(point[attr])
    for key in sorted(days):
        min_val = min(days[key])
        max_val = max(days[key])
        avg_val = sum(days[key]) / len(days[key])
        grouped.append({"day": key, attr: avg_val, "error": [min_val, max_val]})
    return grouped


def group_by_month(data):
    try:
        i = 0
        grouped = []
        months = {}
        for point in data:
            year, month, day = point['dateTime'].split('-')
            yearmonth = "{0}-{1}".format(year, month)
            months.setdefault(yearmonth, []).append(point['value'])
        for key in sorted(months):
            outliers = []
            weights = sorted(months[key])
            plot = calculate_boxplot(weights)
            low, _, _, _, upr = plot
            for w in weights:
                if float(w) > upr or float(w) < low:
                    outliers.append(w)
            grouped.append({"month": key, "plot": plot, "outliers": outliers, "index": i})
            i += 1
        return grouped
    except Exception as error : 
	logging.exception("message")

def get_yearcycle(data, return_as="json"):
    years = {}
    output = []
    for point in data:
        year, month, day = point['dateTime'].split('-')
        if int(year) not in years:
            years[int(year)] = {}
        if int(month) not in years[int(year)]:
            years[int(year)][int(month)] = []
        years[int(year)][int(month)].append(flt(point['value']))
    for y in years:
        months = []
        for m in range(1, 13):
            if years[y].get(m, False):
                months.append(flt(sum(years[y][m]) / len(years[y][m])))
            else:
                months.append(None)
        output.append({
            "name": y,
            "data": months
        })
    if return_as is "json":
        return json.dumps(output)
    elif return_as is "raw":
        return output
    else:
        return output


def calculate_median(numbers):
    nums = sorted(numbers)
    if len(nums) % 2 == 0:
        median = (flt(nums[len(nums) / 2]) + flt(nums[(len(nums) / 2) - 1])) / 2
    else:
        median = nums[len(nums) / 2]
    return flt(median)


def calculate_quartiles(numbers):
    nums = sorted(numbers)
    if len(nums) % 2 == 0:
        low_qtr = calculate_median(nums[:(len(nums) / 2)])
        upr_qtr = calculate_median(nums[len(nums) / 2:])
    else:
        low_qtr = calculate_median(nums[:(len(nums) / 2)])
        upr_qtr = calculate_median(nums[(len(nums) / 2) + 1:])
    return (flt(low_qtr), flt(upr_qtr))


def calculate_boxplot(numbers):
    nums = sorted(numbers)
    median = calculate_median(nums)
    low_qtr, upr_qtr = calculate_quartiles(nums)
    iqr = upr_qtr - low_qtr
    upr_wsk = flt(upr_qtr + (1.5 * iqr))
    low_wsk = flt(low_qtr - (1.5 * iqr))
    if low_wsk < 0:
        low_wsk = 0
    return [low_wsk, low_qtr, median, upr_qtr, upr_wsk]


def get_periods(all, year, month, week, day=None):
    all_list = [flt(d.get('value')) for d in all]
    year_list = [flt(d.get('value')) for d in year]
    month_list = [flt(d.get('value')) for d in month]
    week_list = [flt(d.get('value')) for d in week]
    series = []
    series.append({
        "name": "Averages",
        "type": "line",
        "data": [flt(average(all_list)), flt(average(year_list)), flt(average(month_list)), flt(average(week_list))]
    })
    series.append({
        "name": "Stats",
        "type": "boxplot",
        "data": [calculate_boxplot(all_list), calculate_boxplot(year_list), calculate_boxplot(month_list),
                 calculate_boxplot(week_list)]
    })
    return series


def flt(arg):
    """
    return single digit float
    :param arg:
    :return:
    """
    return float("{0:.1f}".format(float(arg)))


def clean_max(data):
    """
    Removes the filled dates that fitbit adds when max is selected
    :param data:
    :return:
    """
    while data[0]['value'] == data[1]['value']:
        data.pop(0)
    return data

def calorieEstimate(caloriesBurned):
    try:
        userId = session['user_Id']
        query = "SELECT SUM(calorieEst) from FoodEntry where UserId = :userId and timestamp LIKE CONCAT(CURDATE(),'%')"
        data = {
            "userId" : userId
        }
	dataCalorie= mysql.query_db(query, data)[0]['SUM(calorieEst)']
	if dataCalorie is not None:
		calorieConsumed=int(dataCalorie)
	else:
        	calorieConsumed = 0
        session['caloriesConsumed'] = calorieConsumed
        goalWeight = (int(session['goal'])/2.2)
	gender = 'Male'
	if 'gender' in session:
        	gender=session['gender']
        age = int(session['age'])
        if gender=="Female":
            if age<10:
                caloriegoal=(22.5 * goalWeight) + 499
            elif age < 18:
                caloriegoal=(12.2 * goalWeight) + 746
            elif age < 30:
                caloriegoal=(14.7 * goalWeight) + 496
            elif age < 61:
                caloriegoal=(8.7 * goalWeight) + 829
            else:
                caloriegoal=(10.5 * goalWeight) + 596
        else:
            if age<10:
                caloriegoal=(22.5 * goalWeight) + 495
            elif age < 18:
                caloriegoal=(17.5 * goalWeight) + 651
            elif age < 30:
                caloriegoal=(15.3 * goalWeight) + 679
            elif age < 61:
                caloriegoal=(11.6 * goalWeight) + 879
            else:
                caloriegoal=(13.5 * goalWeight) + 487

        availableCalorie=int((int(caloriegoal)+int(caloriesBurned))-int(calorieConsumed))
        session['availableCalorie'] = availableCalorie
        session['caloriegoal'] = caloriegoal
	progressCaloriePercentage=int((float(session['goal'])/float(session['weight']))*100)
	if progressCaloriePercentage>100:
		progressCaloriePercentage=progressCaloriePercentage-100
	session['progressCaloriePercentage'] = progressCaloriePercentage
	session['distanceLeft'] = abs((int(session['weight'])-int(session['goal'])))
	updateNotification()
    except (Exception) as error : 
	logging.exception("message")

def updateNotification():
    try:
	if session['functionName']=='OnLogin':
		pushNotifyObject['availableCalorieValue'] = session['availableCalorie']
		if int(session['availableCalorie'])>0:
			pushNotifyObject['recommedation']='New Recommendation Available'
			pushNotifyObject['calorieExceeds']=''
			pushNotifyObject['calorieAvailable']='Calorie Goal not Reached. Add Food Items to reach calorie goal and see recommendations.'
		else:
			pushNotifyObject['recommedation']=''
			pushNotifyObject['calorieAvailable']=''
			pushNotifyObject['calorieExceeds']='Calorie Goal Exceeded'
	elif pushNotifyObject['availableCalorieValue']!= session['availableCalorie']:
		if session['functionName']=='FoodEntry':
			if session['availableCalorie']>0:
				pushNotifyObject['recommedation']='New Recommendation Available'
				pushNotifyObject['calorieExceeds']=''
				pushNotifyObject['calorieAvailable']=''
			else:
				pushNotifyObject['recommedation']=''
				pushNotifyObject['calorieAvailable']=''
				pushNotifyObject['calorieExceeds']='Calorie Goal Exceeded'
		if session['functionName']=='OnDashboard':
			if session['availableCalorie']>0:
				pushNotifyObject['recommedation']='New Recommendation Available'
				pushNotifyObject['calorieExceeds']=''
				pushNotifyObject['calorieAvailable']='Calorie Goal not Reached. Add Food Items to reach calorie goal and see recommendations.'
			else:
				pushNotifyObject['recommedation']=''
				pushNotifyObject['calorieAvailable']=''
				pushNotifyObject['calorieExceeds']='Calorie Goal Exceeded'
    except (Exception) as error : 
	logging.exception("message")
    
