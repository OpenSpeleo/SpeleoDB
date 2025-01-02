from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import Format

# ruff: noqa: E501


class GeoDataFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [
        # -------------------------- KML and related formats ------------------------- #
        #
        ".kml",  # Keyhole Markup Language, used for geographic data visualization.
        ".kmz",  # Compressed KML file, often used in Google Earth.
        #
        # ------------------------- Shapefiles (Esri format) -------------------------- #
        #
        ".shp",  # Shapefile, contains the geometry of features.
        ".shx",  # Shapefile index file, used with .shp.
        ".prj",  # Projection file, describes the coordinate system for shapefiles.
        #
        # Vector data formats
        #
        ".geojson",  # GeoJSON, a JSON-based format for encoding spatial data.
        ".gml",  # Geography Markup Language, XML-based format.
        ".gpkg",  # GeoPackage, an open standard for geospatial data.
        ".dgn",  # DGN, used in MicroStation and GIS applications.
        #
        # ---------------------- Gridded data and raster formats --------------------- #
        #
        ".grd",  # GRD, used for grid or raster data.
        ".flt",  # Floating-point raster file, often paired with .hdr.
        #
        # ------------------------ Other GIS-specific formats ------------------------ #
        #
        ".map",  # MapInfo map files.
        ".tab",  # MapInfo table files.
        ".mif",  # MapInfo Interchange Format, vector data.
        ".mid",  # MapInfo data file paired with .mif.
        ".osm",  # OpenStreetMap data format.
        ".pbf",  # Protocolbuffer Binary Format, compressed OpenStreetMap data.
        ".qgs",  # QGIS project file.
        ".qgz",  # Compressed QGIS project file.
        ".vrt",  # Virtual Raster Tile, used to link raster datasets.
        ".sld",  # Styled Layer Descriptor, for styling geographic data.
        #
        # ------------------------- GPS and tracking formats ------------------------- #
        #
        ".gpx",  # GPS Exchange Format, used for GPS data.
        ".nmea",  # NMEA format, used for GPS data logs.
        ".trk",  # GPS track data format.
        ".plt",  # OziExplorer track log file.
        #
        # -------------------- Proprietary and specialized formats ------------------- #
        #
        ".e00",  # Esri ArcInfo Interchange format.
        ".adf",  # ArcInfo binary coverage files.
        ".grb",  # GRIB, used for meteorological data.
        ".dem",  # Digital Elevation Model data.
        ".dt0",  # SRTM (Shuttle Radar Topography Mission) elevation data.
        ".dt1",  # Higher resolution SRTM data.
        ".lyr",  # Esri Layer file.
        ".bxr",  # Binary Raster (IDRISI format).
        ".rrd",  # Reduced resolution dataset, auxiliary raster data.
        ".ecw",  # Enhanced Compressed Wavelet, a raster format.
        ".img",  # ERDAS IMAGINE raster file.
        ".sdts",  # Spatial Data Transfer Standard format.
        #
        # ----------------------- 3D GIS and elevation formats ----------------------- #
        #
        ".3dm",  # 3D model data, sometimes used in GIS.
        ".3ds",  # 3D Studio files, used for 3D models in GIS.
        ".las",  # LASer file format, for LiDAR data.
        ".laz",  # Compressed LAS format.
        ".dtm",  # Digital Terrain Model.
        ".tin",  # Triangulated Irregular Network, for elevation modeling.
        #
        # ------------------ Time-enabled and multidimensional data ------------------ #
        #
        ".nc",  # NetCDF, used for climate and temporal geospatial data.
        ".hdf",  # Hierarchical Data Format, used for multidimensional data.
        #
        # -------------------------  Surfer - Golden Software- ----------------------- #
        #
        ".svd",  # Surfer grid file.
        ".bln",  # Surfer blanking file.
    ]

    ALLOWED_MIMETYPES = ["*"]
    ASSOC_FILEFORMAT = Format.FileFormat.OTHER

    TARGET_FOLDER = "geospatial"
    TARGET_SAVE_FILENAME = None
    TARGET_DOWNLOAD_FILENAME = None
