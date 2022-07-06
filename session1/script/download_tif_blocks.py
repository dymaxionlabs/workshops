import fiona
import ee
import os

ee.Initialize()


def maskclouds(image):
    band_qa = image.select('QA60')
    cloud_mask = ee.Number(2).pow(10).int()
    cirrus_mask = ee.Number(2).pow(11).int()
    mask = band_qa.bitwiseAnd(cloud_mask).eq(0) and(
        band_qa.bitwiseAnd(cirrus_mask).eq(0))
    return image.updateMask(mask).divide(10000)


def obtain_image_sentinel(collection, time_range, area):
    """ Selection of median, cloud-free image from a collection of images in the Sentinel 2 dataset
    See also: https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2

    Parameters:
        collection (): name of the collection
        time_range (['YYYY-MT-DY','YYYY-MT-DY']): must be inside the available data
        area (ee.geometry.Geometry): area of interest

    Returns:
        sentinel_median (ee.image.Image)
     """
# First, method to remove cloud from the image
    sentinel_filtered = (ee.ImageCollection(collection).
                         filterBounds(area).
                         filterDate(time_range[0], time_range[1]).
                         filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)).
                         map(maskclouds))
    sentinel_median = sentinel_filtered.median()
    return sentinel_median

files = ['../data/informal_settlements_epsg4326_claseA_buff2000_dissolve.gpkg']

collection = 'COPERNICUS/S2'
for dataset in files:
    print('Processing file {f}.'.format(f=dataset))
    dataset_name, _ = os.path.splitext(os.path.basename(dataset))
    polys = fiona.open(dataset)
    for i, poly in enumerate(polys):
        if i==0:
            continue
        poly_coords = poly['geometry']['coordinates']
        fid = poly['properties']['id']
        country = poly['properties']['country']
        year = poly['properties']['year']
        id_img = f"{country}_{year}_{fid}"
        time_range_polys = [f"{year}-01-01", f"{year}-12-31"]
        patch_id = 'patch_{f}'.format(f=fid)
        area_poly = ee.Geometry.Polygon(poly_coords)
        img = obtain_image_sentinel(collection, time_range_polys, area_poly)
        out_image = ee.Image(img).select(['B4', 'B3', 'B2', 'B8'])
        task = ee.batch.Export.image.toCloudStorage(
            image = out_image,
            bucket = 'dym-quilmes-trucks-temp',
            fileNamePrefix = f"informal-settlements-sentinel2-RGBNIR/imagenes/{country}/{id_img}",
            maxPixels = 8030040147504,
            scale = 10,
            region = area_poly)
        task.start()
        print(task.status())
