from tornado.wsgi import WSGIContainer
from tornado.ioloop import IOLoop
from tornado.web import FallbackHandler, RequestHandler, Application
import tornado.websocket
from flask_debugtoolbar import DebugToolbarExtension
from config import DEBUG
import threading
from views import *

if not DEBUG:
    toolbar = DebugToolbarExtension(app)

subscribers = set() 
class WSocketHandler(tornado.websocket.WebSocketHandler): #Tornado Websocket Handler

    def check_origin(self, origin):
        return True

    def open(self):
        self.stream.set_nodelay(True)
        subscribers.add(self) #Join client to our league

    def on_close(self):
        if self in subscribers:
            subscribers.remove(self) #Remove client


tr = WSGIContainer(app)

application = Application([
(r'/ws', WSocketHandler), #For Sockets
(r".*", FallbackHandler, dict(fallback=tr)),
])

def f():
	try:
		for subscriber in subscribers:
	    		subscriber.write_message(pushNotifyObject)
	    		pushNotifyObject['recommedation']=''
	    		pushNotifyObject['calorieAvailable']=''
	    		pushNotifyObject['calorieExceeds']=''
		threading.Timer(5, f).start()
    	except Exception as error : 
		logging.exception("message")

if __name__ == "__main__":
  application.listen(5000, address='0.0.0.0',ssl_options={ 
        "certfile": "./certi/domain.crt",
        "keyfile": "./certi/domain.key",
    })
  print(":::::::::::::::::::Connected through SSL::::::::::::::")
  IOLoop.current().add_callback(f)
  IOLoop.instance().start()
