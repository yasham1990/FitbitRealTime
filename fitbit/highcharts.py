import json


class Chart():
    def __init__(self, title, **kwargs):
        """
        Initialize with Defaults
        :return:
        """
        self.debug = False
        self.chart = {
            "zoomType": kwargs.get('zoomType', 'x')
        }
        self.credits = {
            "enabled": False
        }
        self.title = {
            "text": title
        }
        self.xAxis = {
            "type": kwargs.get("xType"),
            "categories": kwargs.get('xCategories', []),
            "title": {
                "text": kwargs.get("xTitle", None)
            }
        }
        self.yAxis = {
            "title": {
                "text": kwargs.get("yTitle", None)
            },
            "floor": 0

        }
        self.legend = {
            "enabled": False,
            "layout": "vertical",
            "alight": "right",
            "verticalAlign": "middle",
            "borderWidth": 0
        }
        self.series = kwargs.get("series", [])

    def get_object(self):
        return {
            "chart": self.chart,
            "credits": self.credits,
            "title": self.title,
            "legend": self.legend,
            "xAxis": self.xAxis,
            "yAxis": self.yAxis,
            "series": self.series
        }

    def get_json(self):
        return json.dumps(self.get_object())

    def add_series(self, name, data, type="line"):
        self.series.append({
            "name": name,
            "type": type,
            "data": self._clean_data(data)
        })
        return self

    def add_raw_series(self, series):
        self.series = series
        return self

    def set_x_categories(self, categories):
        self.xAxis['categories'] = categories
        return self

    def _clean_data(self, data):
        output = []
        for line in data:
            if isinstance(line, str) or isinstance(line, unicode):
                try:
                    output.append(float(line))
                except Exception:
                    output.append(line)
            elif isinstance(line, list):
                output.append(self._clean_data(line))
            else:
                output.append(line)
        return output