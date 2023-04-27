from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://{0}:{1}@localhost:5432/{2}'.format('','','')
db = SQLAlchemy(app)
db.Model.metadata.reflect(db.engine)

class S2_Metadata(db.Model):
	index = db.Column(db.String(80), primary_key=True)
	def __repr__(self):
		return '<My metadata>'
