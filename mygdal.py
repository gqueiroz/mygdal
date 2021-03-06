# -*- coding: utf-8 -*-

from osgeo import osr, gdal
import numpy
import datetime

__error_stacks_length__ = 'DiffStacksLength'
__error_stacks_length_msg__ = 'The tif stacks\' length are different.'
__error_missing_file__ = 'MissingFile'
__error_missing_file_msg__ = 'The file %s does not exist in the file system.'
__error_time_line_length__ = 'WrongTimeLineLength'
__error_time_line_length_msg__ = 'Time line length (%s) is different of stack time series length (%s).'
__error_wrong_coordinates_format__ = \
    'you must inform a list of coordinates or a string file path to coordinates.'
__error_outbounds__ = 'OutOfBounds'
__error_outbounds_msg__ = 'Coordinate/pixel index out of bounds.'
__error_required_tag__ = 'RequiredTagMissing'
__error_required_tag_msg__ = 'Tag \'%s\' is required but is missing in your file.'
__error_invalid_bbox__ = 'InvalidBoundBox'
__error_invalid_bbox_msg__ = 'Invalid bound box.'
__error_bands_tags__ = 'BandsTagsError'
__error_bands_tags_msg__ = 'bands_paths and bands_factors tags must have the same length.'


def ord_pair(i, j):
    return numpy.array([i, j])


def to_float(value, decimal):
    if decimal != '.':
        value.replace(decimal, '.')
    return float(value)


def to_date(value, date_format):
    return datetime.datetime.strptime(value, date_format)


class Mygdal:
    # GeoTransform Constants Indexes
    GT_X = 0
    GT_Y = 1
    GT_X_UL = 0
    GT_X_RES = 1
    GT_X_SKEW = 2
    GT_Y_UL = 3
    GT_Y_SKEW = 4
    GT_Y_RES = 5

    def __init__(self, filename):
        self.dataset = gdal.Open(filename)
        if not self.dataset:
            raise Exception(__error_missing_file__, __error_missing_file_msg__ % filename)
        self.srs_wkt = self.dataset.GetProjectionRef()
        self.srs = osr.SpatialReference()
        self.srs.ImportFromWkt(self.srs_wkt)
        self.width = self.dataset.RasterXSize
        self.height = self.dataset.RasterYSize
        self.size = numpy.array([self.width, self.height], dtype=numpy.dtype(int))
        geo_transform = self.dataset.GetGeoTransform()
        self.geo_resolution = ord_pair(geo_transform[Mygdal.GT_X_RES], geo_transform[Mygdal.GT_Y_RES])
        self.geo_skew = ord_pair(geo_transform[Mygdal.GT_Y_SKEW], geo_transform[Mygdal.GT_X_SKEW])
        self.geo_ul = ord_pair(geo_transform[Mygdal.GT_X_UL], geo_transform[Mygdal.GT_Y_UL])
        self.geo_lr = self.pixels_to_geolocs(ord_pair(self.width - 1, self.height - 1))
        self.geo_size = self.geo_lr - self.geo_ul
        self.geo_size_abs = numpy.abs(self.geo_size)
        self.values_nodata = numpy.array([self.dataset.GetRasterBand(i).GetNoDataValue()
                                          for i in range(1, self.dataset.RasterCount + 1)])

    def close_dataset(self):
        self.dataset = None

    def get_random_geolocs(self, n=1, bbox_ul=None, bbox_lr=None, seed=None):
        if seed:
            numpy.random.seed(seed)
        ul = self.geo_ul
        lr = self.geo_lr
        if numpy.any((ul * numpy.sign(self.geo_resolution)) > (lr * numpy.sign(self.geo_resolution))):
            raise Exception(__error_invalid_bbox__, __error_invalid_bbox_msg__)
        if bbox_ul:
            if numpy.any(bbox_ul < (ul * numpy.sign(self.geo_resolution))):
                raise Exception(__error_outbounds__, __error_outbounds_msg__)
            ul = bbox_ul
        if bbox_lr:
            if numpy.any(bbox_lr > (lr * numpy.sign(self.geo_resolution))):
                raise Exception(__error_outbounds__, __error_outbounds_msg__)
            lr = bbox_lr
        return ul + numpy.random.rand(n, 2) * (lr - ul)

    def get_random_pixels(self, n=1, bbox_ul=None, bbox_lr=None, seed=None):
        if seed:
            numpy.random.seed(seed)
        ul = numpy.array([0, 0], dtype=numpy.dtype(int))
        lr = self.size - 1
        if numpy.any(ul > lr):
            raise Exception(__error_invalid_bbox__, __error_invalid_bbox_msg__)
        if bbox_ul:
            if numpy.any(bbox_ul < ul):
                raise Exception(__error_outbounds__, __error_outbounds_msg__)
            ul = bbox_ul
        if bbox_lr:
            if numpy.any(bbox_lr > lr):
                raise Exception(__error_outbounds__, __error_outbounds_msg__)
            lr = bbox_lr
        return ul + numpy.array(numpy.random.rand(n, 2) * (lr - ul), dtype=numpy.dtype(int))

    def are_valid_geolocs(self, geolocs):
        """
        Verifies if each point in geolocs belongs to image bounding box.
        Points in @geolocs must be in same system of reference than image's.
        Returns True if all points are valid, False otherwise.
        :param geolocs: numpy.array
        :return: bool
        """
        return numpy.any((geolocs < (self.geo_ul * numpy.sign(self.geo_resolution))) *
                         (geolocs > (self.geo_lr * numpy.sign(self.geo_resolution))))

    def are_valid_pixels(self, pixels):
        """
        Verifies if each pixel in pixels belongs to image size.
        Pixels in @pixels parameter must be in same system of reference than image's.
        Returns True if all pixels are valid, False otherwise.
        :param pixels: numpy.array
        :return: bool
        """
        return numpy.any((pixels < numpy.array([0, 0])) * (pixels > self.size))

    def pixels_to_geolocs(self, pixels):
        result = numpy.array([])
        if pixels is not None and len(pixels):
            result = self.geo_ul + self.geo_resolution * pixels + self.geo_skew * pixels
        return result

    def geolocs_to_pixels(self, geolocs):
        result = numpy.array([])
        if geolocs is not None and len(geolocs):
            result = (geolocs - self.geo_ul)
            with numpy.errstate(divide='ignore', invalid='ignore'):
                result_geo_resolution = numpy.floor_divide(result, self.geo_resolution)
                result_geo_skew = numpy.floor_divide(result, self.geo_skew)
                result_geo_resolution[~numpy.isfinite(result_geo_resolution)] = 0
                result_geo_skew[~numpy.isfinite(result_geo_skew)] = 0
            result = numpy.array(result_geo_resolution + result_geo_skew, dtype=numpy.dtype(int))
        return result

    def read_pixel_values(self, pixel):
        result = self.dataset.ReadAsArray(int(pixel[Mygdal.GT_X]), int(pixel[Mygdal.GT_Y]), xsize=1, ysize=1)
        return numpy.reshape(result, len(result))

    def mask_nodata_pixel_bands(self, pixel_bands):
        return pixel_bands != self.values_nodata

    def reproject_geolocs_from(self, geolocs, geo_srs_wkt_from):
        """
        Reprojects all points in @geolocs from a given system of reference to the image's one.
        Return an array containing the given points.
        :param geolocs: numpy.array
        :param geo_srs_wkt_from: string
        :return: numpy.array
        """
        if self.srs_wkt == geo_srs_wkt_from:
            return geolocs
        srs_from = osr.SpatialReference()
        srs_from.ImportFromWkt(geo_srs_wkt_from)
        transform = osr.CoordinateTransformation(srs_from, self.srs)
        result = numpy.array(transform.TransformPoints(geolocs))[:, 0:2]
        return result


class MyTCSV:
    TAG_DELIMITER = 'delimiter'
    TAG_HAS_HEADER = 'has_header'
    TAG_DECIMAL = 'decimal_point'
    TAG_QUOTE = 'quote'

    def __init__(self, filename, encoding='utf-8', delimiter=',', has_header='False', decimal='.', quote='"'):
        self.file = open(filename, encoding=encoding)
        self.__row__ = None
        self.data = []
        self.field_names = []
        self.__fetch_tags__()
        self.tags[MyTCSV.TAG_DELIMITER] = self.get_tag_value(MyTCSV.TAG_DELIMITER, delimiter)
        self.tags[MyTCSV.TAG_HAS_HEADER] = self.get_tag_value(MyTCSV.TAG_HAS_HEADER, has_header)
        self.tags[MyTCSV.TAG_DECIMAL] = self.get_tag_value(MyTCSV.TAG_DECIMAL, decimal)
        self.tags[MyTCSV.TAG_QUOTE] = self.get_tag_value(MyTCSV.TAG_QUOTE, quote)
        self.__prepare_data_fetch__()

    def __fetch_tags__(self):
        """
        Loads all tags as raw strings without any post process.
        All postprocessing treatment is made in __prepare_data_fetch__() method.
        """
        self.tags = {}
        for self.__row__ in self.file:
            self.__row__ = self.__row__.strip()
            if self.__row__[0] == '#':
                tag_index = self.__row__.find('=', 1)
                if tag_index != -1:
                    tag_name = self.__row__[1:tag_index].strip()
                    tag_value = self.__row__[tag_index + 1:].strip()
                    self.tags[tag_name] = tag_value
                else:
                    continue
            else:
                break

    def __prepare_data_fetch__(self):
        """
        Process data header and file's tags. It lets the first data row loaded in __row__ member.
        Tags are processed by calling __transform_tag_value__() method.
        """
        row = self.__row__.split(self.tags[MyTCSV.TAG_DELIMITER])
        if self.tags[MyTCSV.TAG_HAS_HEADER].lower() == 'true':
            for value in row:
                self.field_names.append(value.strip().strip(self.tags[MyTCSV.TAG_QUOTE]))
            try:
                self.__row__ = next(self.file)
            except StopIteration:
                self.__row__ = ''
        for key, value in self.tags.items():
            self.tags[key] = self.__transform_tag_value__(key, value)

    def __process_row_data__(self):
        """
        Process data row loaded in __row__ by calling __transform_row_data__() method
        and stores it into object's data member.
        """
        row = self.__transform_row_data__(self.__row__.split(self.tags[MyTCSV.TAG_DELIMITER]))
        if len(self.data):
            for i in range(len(row)):
                self.data[i] = numpy.append(self.data[i], row[i])
        else:
            for i in range(len(row)):
                self.data.append(numpy.array([row[i]], dtype=type(row[i])))

    def fetch_data(self):
        """
        Loads all file's data to internal data member. Each fetched row is processed by
        __process_row_data__() method.
        """
        self.__process_row_data__()
        for self.__row__ in self.file:
            self.__row__ = self.__row__.strip()
            self.__process_row_data__()

    def __transform_tag_value__(self, tag_name, tag_value):
        """
        Process tags values to it final data type (e.g. numbers, dates, lists).
        This method is called by __prepare_data_fetch__() and is executed after
        all header preparation process. This means that resolve_field_ref() method
        can be used in further overriding implementations.
        :param tag_name: string
        :param tag_value: string
        :return: object
        """
        if tag_name == MyTCSV.TAG_HAS_HEADER:
            return tag_name.lower() == 'true'
        return tag_value

    def __transform_row_data__(self, fields):
        """
        Process each fetched row data passed in @fields parameter. At this point, @fields
        is a list of values preprocessed by __process_row_data__. Further implementations of
        this method may access specific fields by its index and looking for it in @fields parameter.
        Any change must be returned by this method, otherwise it will be lost.
        :param fields: list
        :return: list
        """
        for i in range(len(fields)):
            fields[i] = fields[i].strip().strip(self.tags[MyTCSV.TAG_QUOTE])
        return fields

    def get_tag_value(self, tag_name, default=None):
        try:
            return self.tags[tag_name]
        except KeyError:
            if default or default == 0:
                return default
            raise Exception(__error_required_tag__, __error_required_tag_msg__ % tag_name)

    def has_tag_name(self, tag_name):
        return tag_name in self.tags

    def resolve_field_ref(self, field_ref):
        """
        If the data has header, tags may contains references to fields's name.
        This method resolves this kind of reference by substituting the name for the field index.
        If a number is passed as an argument of @field_ref, it is automatically returned as such.
        :param field_ref: string
        :return: integer
        """
        if self.tags[MyTCSV.TAG_HAS_HEADER]:
            try:
                return int(field_ref)
            except ValueError:
                return self.field_names.index(field_ref)
        else:
            return int(field_ref)

    def get_data_key_indexes(self, field_ref):
        result = {}
        field = self.resolve_field_ref(field_ref)
        for i in range(len(self.data[field])):
            key = self.data[field][i]
            if key in result:
                result[key] = numpy.append(result[key], i)
            else:
                result[key] = numpy.array([i])
        return result

    def close(self):
        self.data = None


class Timeline(MyTCSV):
    TAG_DATE_FIELD = 'date_field'
    TAG_DATE_FORMAT = 'date_format'
    TAG_DOY_FILE = 'doy_tif_filepath'
    TAG_DAY_FACTOR = 'doy_factor'

    def __init__(self, filename, date_format='%Y-%m-%d', doy_file='doy.tif', day_factor=1.0):
        super(Timeline, self).__init__(filename)
        self.tags[Timeline.TAG_DATE_FORMAT] = self.get_tag_value(Timeline.TAG_DATE_FORMAT, date_format)
        self.tags[Timeline.TAG_DOY_FILE] = self.get_tag_value(Timeline.TAG_DOY_FILE, doy_file)
        self.tags[Timeline.TAG_DAY_FACTOR] = self.get_tag_value(Timeline.TAG_DAY_FACTOR, day_factor)
        self.doy_stack = Mygdal(self.tags[Timeline.TAG_DOY_FILE])

    def __transform_tag_value__(self, tag_name, tag_value):
        if tag_name == Timeline.TAG_DATE_FIELD:
            return self.resolve_field_ref(tag_value)
        elif tag_name == Timeline.TAG_DAY_FACTOR:
            return to_float(tag_value, self.tags[MyTCSV.TAG_DECIMAL])
        return super(Timeline, self).__transform_tag_value__(tag_value, tag_value)

    def __transform_row_data__(self, fields):
        result = super(Timeline, self).__transform_row_data__(fields)
        result[self.tags[Timeline.TAG_DATE_FIELD]] = to_date(fields[self.tags[Timeline.TAG_DATE_FIELD]],
                                                             self.tags[Timeline.TAG_DATE_FORMAT])
        return result

    def close(self):
        self.doy_stack.close_dataset()
        super(Timeline, self).close()

    def read_pixel_dates(self, pixel):
        doys = self.doy_stack.read_pixel_values(pixel)
        mask_nodata = self.doy_stack.mask_nodata_pixel_bands(doys)
        dates = self.data[self.tags[Timeline.TAG_DATE_FIELD]]
        if len(doys) != len(dates):
            raise Exception(__error_time_line_length__, __error_time_line_length_msg__ % (len(dates), len(doys)))
        return numpy.array([datetime.datetime(dates[i].year, 1, 1) +
                            datetime.timedelta(days=doys[i] * self.tags[Timeline.TAG_DAY_FACTOR])
                            if mask_nodata[i] else dates[i] for i in range(len(dates))])

    @staticmethod
    def mask_timespan_dates(dates, date_from=None, date_to=None):
        return (dates >= date_from) * (dates <= date_to)


class Samples(MyTCSV):
    TAG_X_FIELD = 'x_field'
    TAG_Y_FIELD = 'y_field'
    TAG_PROJ_WKT = 'projection_wkt'
    TAG_FROM_DT_FIELD = 'from_date_field'
    TAG_TO_DT_FIELD = 'to_date_field'
    TAG_DATE_FORMAT = 'date_format'
    TAG_CLASS_FIELD = 'class_field'
    TAG_TIMELINE_FILE = 'timeline_filepath'
    TAG_BANDS_PATHS = 'bands_filepaths'
    TAG_BANDS_FACTORS = 'bands_factors'

    def __init__(self, filename, date_format='%Y-%m-%d', timeline_file='timeline.csv', bands_files='ndvi.tif,evi.tif'):
        super(Samples, self).__init__(filename)
        self.tags[Samples.TAG_DATE_FORMAT] = self.get_tag_value(Samples.TAG_DATE_FORMAT, date_format)
        self.tags[Samples.TAG_TIMELINE_FILE] = self.get_tag_value(Samples.TAG_TIMELINE_FILE, timeline_file)
        self.tags[Samples.TAG_BANDS_PATHS] = self.get_tag_value(Samples.TAG_BANDS_PATHS, bands_files)
        self.timeline = Timeline(self.tags[Samples.TAG_TIMELINE_FILE])
        self.bands = [Mygdal(value) for value in self.tags[Samples.TAG_BANDS_PATHS]]
        self.bands_factor = [value for value in self.tags[Samples.TAG_BANDS_FACTORS]]
        if len(self.bands) != len(self.bands_factor):
            raise Exception(__error_bands_tags__, __error_bands_tags_msg__)

    def __transform_tag_value__(self, tag_name, tag_value):
        if tag_name == Samples.TAG_X_FIELD:
            return self.resolve_field_ref(tag_value)
        elif tag_name == Samples.TAG_Y_FIELD:
            return self.resolve_field_ref(tag_value)
        elif tag_name == Samples.TAG_CLASS_FIELD:
            return self.resolve_field_ref(tag_value)
        elif tag_name == Samples.TAG_FROM_DT_FIELD:
            return self.resolve_field_ref(tag_value)
        elif tag_name == Samples.TAG_TO_DT_FIELD:
            return self.resolve_field_ref(tag_value)
        elif tag_name == Samples.TAG_BANDS_PATHS:
            return [value.strip() for value in self.tags[Samples.TAG_BANDS_PATHS].strip().split(',')]
        elif tag_name == Samples.TAG_BANDS_FACTORS:
            return [to_float(value.strip(), self.tags[MyTCSV.TAG_DECIMAL])
                    for value in self.tags[Samples.TAG_BANDS_FACTORS].strip().split(',')]
        return super(Samples, self).__transform_tag_value__(tag_value, tag_value)

    def __transform_row_data__(self, fields):
        result = super(Samples, self).__transform_row_data__(fields)
        result[self.tags[Samples.TAG_X_FIELD]] = to_float(fields[self.tags[Samples.TAG_X_FIELD]],
                                                          self.tags[MyTCSV.TAG_DECIMAL])
        result[self.tags[Samples.TAG_Y_FIELD]] = to_float(fields[self.tags[Samples.TAG_Y_FIELD]],
                                                          self.tags[MyTCSV.TAG_DECIMAL])
        result[self.tags[Samples.TAG_FROM_DT_FIELD]] = to_date(fields[self.tags[Samples.TAG_FROM_DT_FIELD]],
                                                               self.tags[Samples.TAG_DATE_FORMAT])
        result[self.tags[Samples.TAG_TO_DT_FIELD]] = to_date(fields[self.tags[Samples.TAG_TO_DT_FIELD]],
                                                             self.tags[Samples.TAG_DATE_FORMAT])
        return result

    def fetch_data(self):
        self.timeline.fetch_data()
        super(Samples, self).fetch_data()

    def close(self):
        for value in self.bands:
            value.close_dataset()
        self.timeline.close()
        super(Samples, self).close()

    def read_samples_geolocs(self, samples_index=None):
        x_result = self.data[self.tags[Samples.TAG_X_FIELD]]
        y_result = self.data[self.tags[Samples.TAG_Y_FIELD]]
        if samples_index is not None:
            x_result = [x_result[index] for index in samples_index]
            y_result = [y_result[index] for index in samples_index]
        return numpy.array([x_result, y_result]).T

    def reproject_samples_to(self, mygdal_obj, samples_index=None):
        result = mygdal_obj.reproject_geolocs_from(self.read_samples_geolocs(samples_index),
                                                   self.tags[Samples.TAG_PROJ_WKT])
        return result

    def get_samples_timeseries(self, samples_index=None, filter_sample_interval=False):
        result = []
        samples_pixels = self.timeline.doy_stack.geolocs_to_pixels(self.reproject_samples_to(self.timeline.doy_stack,
                                                                                             samples_index))
        for i in range(len(samples_pixels)):
            pixel_timeseries = []
            date_from = self.data[self.tags[Samples.TAG_FROM_DT_FIELD]][i]
            date_to = self.data[self.tags[Samples.TAG_FROM_DT_FIELD]][i]
            pixel_dates = self.timeline.read_pixel_dates(samples_pixels[i])
            for j in range(len(self.bands)):
                pixel_values = self.bands[j].read_pixel_values(samples_pixels[i])
                mask = (pixel_dates != self.timeline.doy_stack.values_nodata) * \
                       (pixel_values != self.bands[j].values_nodata)
                if filter_sample_interval:
                    if date_from and date_to:
                        mask = mask * (pixel_dates >= date_from) * (pixel_dates <= date_to)
                    elif date_from:
                        mask *= pixel_dates >= date_from
                    elif date_to:
                        mask *= pixel_dates <= date_to
                pixel_timeseries.append([pixel_values[mask] * self.bands_factor[j], pixel_dates[mask]])
            result.append(pixel_timeseries)
        return result
