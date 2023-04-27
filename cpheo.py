#!/usr/bin/env python
# -*- coding: utf-8 -*-
from flask import Flask,jsonify, render_template, request, redirect, url_for, json
import psycopg2
import multiprocessing
#from celery import Celery
from celery import Celery
from tasks.tasks import make_celery

app = Flask(__name__)

app.config.update(
    CELERY_BROKER_URL='redis://localhost:6379',
    CELERY_RESULT_BACKEND='redis://localhost:6379'
)
celery = make_celery(app)

def init_db(db_user,db_pass,database):
	conn = psycopg2.connect("dbname={0} user={1} password={2} host=localhost port=5432".format(database,db_user,db_pass))
	cur = conn.cursor()
	return cur

@app.route("/")
def hello_eo():
	return render_template("welcome.html")

@app.route("/metadata/reset")
def metadata_reset():
	# Her skal man kunne initiere eller lave reset på metadata
	from cpheo import dl_metadata
	dl_metadata.delay('','','','')
	return redirect(url_for('download_status'))

@app.route("/metadata/update")
def metadata_update():
	from cpheo import upd_metadata
	upd_metadata.delay('','','','')
	return redirect(url_for('download_status'))

@app.route("/metadata/<table>")
def metadata(table):
	cur = init_db('','','afstand')
	cur.execute("SELECT a.index,a.cloudcoverpercentage,to_char(a.ingestiondate, 'YYYY-MM-DD'),a.thumb_loc,to_char(a.endposition,'YYYY-MM-DD'),b.dl from satellit.{0} as a left outer join satellit.download_status as b on a.index = b.index order by a.endposition desc".format(table))
	my_metadata = cur.fetchall()
	# Lige nu faar man al data i metadatatabellen
	return render_template('metadata_show.html', metadata=my_metadata)

@app.route("/inventory/create")
def inventory_creator():
	from cpheo import inv_create
	inv_create.delay()
	return redirect(url_for('download_status'))

@app.route("/inventory/all")
def inventory():
	cur = init_db('','','afstand')
	cur.execute("SELECT index, example from satellit.download_status")
	inventory = cur.fetchall()
	return render_template('inventory.html',inventory=inventory)

@app.route("/download/status")
def download_status():
	i = celery.control.inspect()
	return render_template('status.html', active=i.active(), registered=i.registered(), scheduled=i.scheduled())

@app.route("/analysis/green")
def analyse_green():
	pass

@app.route("/download/manual/<image_id>")
def download_image_backdoor(image_id):
	from cpheo import dl_file
	image_id = image_id.split(",")
	if len(image_id) > 1:
		download_file.delay('','','','',image_id)
	else:
		download_file.delay('','','','',image_id[0])
	# Her kan man downloade et specifikt billede
	return redirect(url_for('download_status'))

@app.route("/download/", methods=['POST'])
def download_image():
        from cpheo import dl_file, cleanup_files
        image_id = request.form['indexFiles']
        image_id = image_id.split(",")
        if len(image_id) > 1:
                dl_file.delay('','','','',image_id)
                cleanup_files.delay(True)
        else:
                dl_file.delay('','','','',image_id[0])
                cleanup_files.delay(True)
        # Her kan man downloade et specifikt billede
        return redirect(url_for('download_status'))

@app.route("/download/all")
def download_all():
	# Her kan man downloade alle billeder
	return "Hello"

@app.route("/cleanup/all")
def cleanup_all():
	# Denne kommando skal slette alle zip filer for at rydde op paa serveren
	return "Hello"

if __name__ == "__main__":
    app.run(host='0.0.0.0')

@celery.task()
def dl_file(db_user,db_pass,api_user,api_pass,id):
	from tasks.download_sentinel import download_file
	download_file(db_user, db_pass, api_user, api_pass, id)

@celery.task()
def dl_metadata(db_user,db_pass,api_user,api_pass):
	from tasks.download_sentinel import download_metadata
	download_metadata(db_user,db_pass,api_user,api_pass)

@celery.task()
def upd_metadata(db_user,db_pass,api_user,api_pass):
	from tasks.download_sentinel import update_metadata
	update_metadata(db_user,db_pass,api_user,api_pass)

@celery.task()
def cleanup_files(with_cleanup):
	from tasks.ndvi_ import masker_iter
	masker_iter(with_cleanup=with_cleanup)

@celery.task()
def inv_create():
	from tasks.download_sentinel import inventory_create
	inventory_create('','','afstand')

@celery.task()
def anal_green():
	pass
