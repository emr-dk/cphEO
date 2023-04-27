#!/usr/bin/env python
# -*- coding: utf-8 -*-
from sentinelsat import SentinelAPI, read_geojson, geojson_to_wkt
from datetime import date, timedelta
from time import strftime, strptime
from sqlalchemy import create_engine
from zipfile import ZipFile
import os
from PIL import Image

def init_db(user,password,database):
	engine = create_engine('postgresql://{0}:{1}@localhost:5432/{2}'.format(user,password,database))
	return engine

def get_api(user,password):
	api = SentinelAPI(user,password, 'https://scihub.copernicus.eu/dhus')
	return api

def db_get_filenames(db_user,db_pass,id, schema, table_name, database):
	engine = init_db(db_user,db_pass,database)
	if isinstance(id, list):
		id = tuple(id)
		my_query = engine.execute("SELECT identifier from {1}.{0} where index in {2}".format(schema, table_name, id)).fetchall()
	elif isinstance(id,str):
		my_query = engine.execute("SELECT identifier from {1}.{0} where index in ('{2}')".format(schema, table_name, id)).fetchall()
	else:
		print("Der er noget galt med det ID der bruges ... Det skal være enten String eller en liste")
	return my_query

def download_metadata(db_user,db_pass,api_user,api_pass,table_name='s2_metadata',schema='satellit',database='afstand',platformname='Sentinel-2',aoi='data/aux/aoi_4326.geojson',dl_thumbs=True):
	api = get_api(api_user,api_pass)
	engine = init_db(db_user,db_pass,database)
	footprint = geojson_to_wkt(read_geojson(aoi))
	products = api.query(footprint,
			     date=('20150623', 'NOW'),
			     platformname=platformname,
			     cloudcoverpercentage=(0,100))
	products_df = api.to_dataframe(products)
	products_df.to_sql(table_name, engine, schema=schema,if_exists='replace')
	engine.execute('alter table {1}.{0} add primary key(index)'.format(table_name,schema))
	engine.execute('alter table {1}.{0} add column thumb_loc text'.format(table_name, schema)) 
	download_thumbnails(db_user,db_pass,api_user,api_pass)

def update_metadata(db_user,db_pass,api_user,api_pass,table_name="s2_metadata",schema='satellit',database='afstand',platformname='Sentinel-2',aoi='data/aux/aoi_4326.geojson',dl_thumbs=True):
	api = get_api(api_user,api_pass)
	engine=init_db(db_user,db_pass,database)
	last_date = engine.execute("select endposition from satellit.s2_metadata order by endposition desc limit 1").fetchone()
	#my_struct_time = strptime(last_date[0], "%Y-%m-%d %H:%M:%S.%f")
	#print(my_struct_time)
	tomorrow = last_date[0] + timedelta(days=1)
	my_time = str(tomorrow.strftime("%Y%m%d"))
	#my_time = str(my_time.tm_year) + str(my_time.tm_mon) + str(my_time.tm_mday)
	footprint = geojson_to_wkt(read_geojson(aoi))
	products = api.query(footprint,
			     date=(my_time, 'NOW'),
			     platformname=platformname,
			     cloudcoverpercentage=(0,100))
	products_df = api.to_dataframe(products)
	products_df.to_sql(table_name, engine, schema=schema, if_exists='append')
	engine = init_db(db_user,db_pass,database)
	import requests
	from requests.auth import HTTPBasicAuth
	query = engine.execute('select index,link_icon,title from {0}.{1} where thumb_loc is NULL'.format(schema,table_name,)).fetchall()
	for link in query:
		print(link)
		r = requests.get(link[1], auth=HTTPBasicAuth(api_user,api_pass))
		path = "thumbnails/" + link[2] + ".jpg"
		if r.status_code == 200:
			open("static/" + path, 'wb').write(r.content)
		engine.execute("update {0}.{1} set thumb_loc='{2}' where index='{3}'".format(schema,table_name,path,link[0]))

def download_file(db_user,db_pass,api_user,api_pass,id,table_name='s2_metadata', schema='satellit', database='afstand'):
	api = get_api(api_user,api_pass)
	if isinstance(id,list):
		for file in id:
			query = db_get_filenames(db_user,db_pass,file, table_name, schema, database)
			api.download(file,'data')
			unzip_file(file,db_user,db_pass,table_name,schema,database,list=True)
	else:
		api.download(id,'data')
		unzip_file(id,db_user,db_pass,table_name,schema,database,list=False)

def unzip_file(id, db_user,db_pass,table_name,schema,database,list,folder='data'):
	query = db_get_filenames(db_user,db_pass,id,table_name,schema,database)
	my_list = [element[0] for element in query]
	for element in my_list:
		file_name = folder + '/' + element + '.zip'
		with ZipFile(file_name, 'r') as zip_ref:
			zip_ref.extractall(folder)
			zip_ref.close()
	delete_zips()

def delete_zips(folder='data',id=None):
	my_zips = os.listdir(folder)
	for file in my_zips:
		if file.endswith('.zip'):
			os.remove(folder + "/" + file)

def inventory_create(db_user, db_pass, database):
	engine = init_db(db_user, db_pass, database)
	engine.execute("truncate satellit.download_status")
	for element in os.listdir('output/aoi'):
		for file in os.listdir('output/aoi/' + str(element)):
			my_file = os.path.splitext(file)
			if my_file[0][-3:] == 'TCI':
				print(my_file)
				im = Image.open('output/aoi/' + str(element) + "/" + str(file))
				size = 128, 128
				im.thumbnail(size)
				output_img = 'aoi/' + str(element) + ".jpg"
				im.save("static/" + output_img, 'JPEG')
				engine.execute("insert into satellit.download_status (index, dl, example) values ('{0}',{1},'{2}')".format(element, True, output_img))

def download_thumbnails(db_user,db_pass,api_user,api_pass,folder='thumbnails',id=None,schema='satellit',database='afstand',table_name='s2_metadata'):
	engine = init_db(db_user,db_pass,database)
	import requests
	from requests.auth import HTTPBasicAuth
	if id is None:
		query = engine.execute('select index,link_icon,title from {0}.{1} where cloudcoverpercentage < 30 and processinglevel = "Level-1C"'.format(schema,table_name,)).fetchall()
		for link in query:
			r = requests.get(link[1], auth=HTTPBasicAuth(api_user,api_pass))
			path = folder + "/" + link[2] + ".jpg"
			print(path)
			if r.status_code == 200:
				open("static/" + path, 'wb').write(r.content)
			engine.execute("update {0}.{1} set thumb_loc='{2}' where index='{3}'".format(schema,table_name,path,link[0]))

#download_thumbnails('emil','12345','hy42','PqwurxnX1')
#download_metadata('emil','12345','hy42','PqwurxnX1')
#download_file('emil','12345','hy42','PqwurxnX1','25b13005-f5ba-404b-9ae3-cbfd9525388e')
#download_file('emil','12345','hy42','PqwurxnX1',['026b9f03-3d50-43b3-bec5-8204e8c8a442','0026c920-f7dc-466b-90fa-e0cb4d79818e'])
#download_thumbnails('emil','12345')
