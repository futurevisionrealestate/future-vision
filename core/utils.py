import csv
from datetime import date, datetime

from django.http import HttpResponse
from django.utils.text import slugify


def parse_date(value, fallback=None):
    if not value:
        return fallback
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return fallback


def csv_response(filename, headers, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{slugify(filename)}.csv"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return response


def date_range_from_request(request, default_days=30):
    today = date.today()
    start = parse_date(request.GET.get("start"), today.replace(day=1))
    end = parse_date(request.GET.get("end"), today)
    if start and end and start > end:
        start, end = end, start
    return start, end
