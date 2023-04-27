#IMPORTS NDVI ONE-GO
import time

import numpy as np
import pandas as pd
from skimage import io
import gdal
from osgeo import osr
import fiona
import rasterio
import rasterio.mask
from pathlib import Path
import os, os.path
import shutil

# Test datasets
redImg = "output/aoi/25b13005-f5ba-404b-9ae3-cbfd9525388e/T33UUB_20180704T103021_B04.tif"
nirImg = "output/aoi/25b13005-f5ba-404b-9ae3-cbfd9525388e/T33UUB_20180704T103021_B08.tif"

# CREATE OVERALL NDVI
def overall_ndvi(id,make_aoi=False):
    if make_aoi==True:
        red_aoi, name = masker(redImg)
        nir_aoi, name = masker(nirImg)
        from skimage import io
        red = io.imread(red_aoi)
        nir = io.imread(nir_aoi)
        ndvi = (nir - red) / (nir + red)
        outputPlace = os.path.dirname(nir_aoi) + "/" + name.split("_")[0] + "_" +name.split("_")[1] + "_NDVI.tif"
        io.imsave(outputPlace, ndvi)
        rasterio_writer(red_aoi,outputPlace,ndvi)
        outputLoc = os.path.dirname(nir_aoi) + "/" + name.split("_")[0] + "_" + name.split("_")[1]  + "_GREEN.tif"
        return outputPlace,outputLoc
    else:
        location = "output/aoi/" + str(id)
        red_image, red_meta = rasterio_reader(location + "/B04.jp2")
        nir_image, nir_meta = rasterio_reader(location + "/B08.jp2")
        np.seterr(divide='ignore', invalid='ignore')
        ndvi = np.divide((nir_image.astype(float) - red_image.astype(float)), (nir_image + red_image))
        outputPlace = location + "/analyser/NDVI.tif"
        nir_meta.update(dtype=ndvi.dtype)
        rasterio_writer_2(outputPlace, ndvi, nir_meta)
    return id, location

#overall_ndvi("6b5f2d2a-5717-4481-bddc-78aee733e161")

def rasterio_reader(inputTIF):
	with rasterio.open(inputTIF) as src:
		image = src.read(1)
		image_meta = src.meta.copy()
	return image, image_meta

def rasterio_writer_2(outputLocation, data, metadata):
	with rasterio.open(outputLocation, 'w', **metadata) as dest:
		dest.write(data, 1)

def rasterio_writer(InputTIF,OutputTIF,data = None):
    with rasterio.open(InputTIF) as src:
        out_meta = src.meta.copy()
        out_image = src.read(1)
    out_meta.update(dtype=data.dtype)
    with rasterio.open(OutputTIF, "w", **out_meta) as dest:
        if data.any() != None:
            dest.write(data,1)
        else:
            pass

#CALCULATE GREEN AREAS
def calculate_green(id,outputLoc=None):
    location = "output/aoi/" + str(id) + "/analyser/"
    ndviOrg, meta = rasterio_reader(location + "NDVI.tif")
    #ndviNew = ndviOrg.copy()
    for i in range(len(ndviOrg)):
        for ii in range(len(ndviOrg[i])):
            if ((ndviOrg[i][ii] >= 0.2) & (ndviOrg[i][ii] <= 0.9)) == True:
                ndviOrg[i][ii] = 1
            elif ((ndviOrg[i][ii] >= 0.2) & (ndviOrg[i][ii] <= 0.9)) == False:
                ndviOrg[i][ii] = 0
    rasterio_writer_2(location + "GREEN.tif", ndviOrg, meta) 
    return id

#id, location = overall_ndvi("6b5f2d2a-5717-4481-bddc-78aee733e161")
#clipper(location + "/analyser/NDVI.tif", "NDVI_Bygning", "data/aux/BYGNING_EPSG32633_Clip_Dissolved.shp")
#calculate_green(id)

def get_proj4(InputTIF):
    srs = osr.SpatialReference()
    src = gdal.Open(InputTIF)
    projsrc = src.GetProjection()
    srs.ImportFromWkt(projsrc)
    proj4 = srs.ExportToWkt()
    return proj4

def masker_iter(with_cleanup=False):
    from tasks.download_sentinel import init_db
    from tasks.download_sentinel import inventory_create
    engine = init_db('emil','12345','afstand')
    #from ndvi_emil import masker
    for element in os.listdir("data"):
        if element.endswith(".SAFE"):
            granule = "data/" + element + "/GRANULE/"
            my_file = os.listdir(granule)
            file_dir = "data/" + element + "/GRANULE/" +  my_file[0] + "/IMG_DATA/"
            for file in os.listdir(file_dir):
                final_dir = file_dir + "/" + str(file)
                id = engine.execute("select index from satellit.s2_metadata where filename = '{0}'".format(element)).fetchone()
                masker(final_dir,id[0])
            if with_cleanup:
                shutil.rmtree("data/" + element)
            from tasks.download_sentinel import inventory_create
            inventory_create('emil','12345','afstand')

def masker(InputTIF, id, OutputTIF='output/aoi', name_add=None, InputSHP='data/aux/kbh_32633.shp', invert=False):
    # CLIP IMAGE WITH SHAPEFILES; Is being used with masker_iter. Do not use for regular clipping
    if name_add is None:
        name_add = ''
    print(InputTIF)
    base = os.path.basename(InputTIF)
    base = os.path.splitext(base)[0] + name_add
    img_name = base.split("_")
    out_path = OutputTIF + "/" + id
    if os.path.exists(out_path):
        pass
    else:
        os.makedirs(out_path + "/analyser", exist_ok=True)
    proj4 = get_proj4(InputTIF)
    with fiona.open(InputSHP, "r") as shapefile:
        features = [feature["geometry"] for feature in shapefile]
    with rasterio.open(InputTIF) as src:
        out_meta = src.meta.copy()
        if invert==False:
            out_image, out_transform = rasterio.mask.mask(src, features, crop=True)
        else:
            out_image, out_transform = rasterio.mask.mask(src, features, crop=False,invert=True, filled=False)
    out_meta.update({"driver": "GTiff",
                 "height": out_image.shape[1],
                 "width": out_image.shape[2],
                 "transform": out_transform,
                 "crs": proj4})
    name = os.path.basename(InputTIF)
    name = name.split("_")
    OutputTIF=out_path + "/" + name[2]
    with rasterio.open(OutputTIF, "w", **out_meta) as dest:
        dest.write(out_image)
    return OutputTIF, base

def green_analysis(id):
	if isinstance(id,list):
		pass
	else:
		location = "output/aoi/" + str(id) + "/analyser/GREEN.tif"
		clipper(location, "NDVI_PG.tif", "data/aux/clippers/privat.shp")
		clipper(location, "NDVI_GA.tif", "data/aux/clippers/groenne_arealer.shp")
		clipper(location, "NDVI_UG.tif", "data/aux/clippers/ukendt_groent.shp")
		## Herfra skal der indsættes noget i en DB. Det må vente
		#calculate_stats("output/aoi/" + str(id) + "/analyser/NDVI_PG.tif","private_green", id)

def clipper(InputTIF, name, InputSHP):
    location = os.path.dirname(InputTIF)
    with fiona.open(InputSHP, "r") as shapefile:
        features = [feature["geometry"] for feature in shapefile]
    with rasterio.open(InputTIF) as src:
        out_image, out_transform = rasterio.mask.mask(src, features, crop=True)
        out_meta = src.meta.copy()
    print(out_image.shape)
    proj4 = get_proj4(InputTIF)
    out_meta.update({"driver": "GTiff",
                 "height": out_image.shape[1],
                 "width": out_image.shape[2],
                 "transform": out_transform,
                 "crs": proj4})

    #rasterio_writer_2(location + name + ".tif", out_image, out_meta)
    location = location + "/" + str(name)
    #rasterio_writer_2(location, out_image, out_meta)
    with rasterio.open(location, "w", **out_meta) as dest:
        dest.write(out_image)

# CALCULATE STATISTICS
def calculate_stats(inputTIF,column, id,table="green"):
    statistics = []
    array, meta = rasterio_reader(inputTIF)
    unique, counts = np.unique(array, return_counts=True)
    totalPixels = len(array)*len(array[0])
    m2Total = totalPixels*100
    m2Green = counts[1]*100
    km2Total = round(m2Total / 1000000, 4)
    km2Green = round(m2Green / 1000000, 4)
    percentage = round((m2Green*100)/m2Total, 4)
    from download_sentinel import init_db
    engine = init_db('emil','12345','afstand')
    engine.execute("insert into satellit.{0} (index, {1}) VALUES ('{3}',{2})".format(table, column, km2Green, id))

#calculate_green("NDVI.tif")
#calculate_stats("green.tif","stats.csv")
#ndviLoc, greenLoc = overall_ndvi(redImg,nirImg)
#green_loc = calculate_green(ndviLoc,greenLoc)
# Subtract buildings
#masker(green_loc,name_add='_udenbyg',InputSHP='data/aux/BYGNING_EPSG32633_Clip_Dissolved.shp')
#masker(greenLoc,name_add='_privat',InputSHP='data/aux/kbh_u_byg_erase.shp')

#id, location = overall_ndvi("6b5f2d2a-5717-4481-bddc-78aee733e161")
#clipper("output/aoi/6b5f2d2a-5717-4481-bddc-78aee733e161/analyser/GREEN.tif", "NDVI_Bygning", "data/aux/BYGNING_EPSG32633_Clip_Dissolved.shp")
#clipper("output/aoi/6b5f2d2a-5717-4481-bddc-78aee733e161/analyser/GREEN.tif", "NDVI_UG.tif", "data/aux/clippers/ukendt_groent.shp")
#clipper("output/aoi/6b5f2d2a-5717-4481-bddc-78aee733e161/analyser/GREEN.tif", "NDVI_GA.tif", "data/aux/clippers/groenne_arealer.shp")
#clipper("output/aoi/6b5f2d2a-5717-4481-bddc-78aee733e161/analyser/NDVI_UG.tif", "NDVI_PG.tif", "data/aux/clippers/ukendt_groent.shp")
calculate_green("d7973697-ac11-403f-8c42-8a70a0879c8b")
calculate_green("6b5f2d2a-5717-4481-bddc-78aee733e161")
calculate_green("931792d9-a203-441a-8a93-094e1a152d3c")


#calculate_green(id)

