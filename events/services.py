import openpyxl
from io import BytesIO
from django.db import transaction
from django.utils import timezone
from .models import Event, Location
from .tasks import update_single_location_weather


def export_events_to_xlsx(queryset):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Events"

    columns = [
        'Title', 'Description', 'Pub Date', 'Start Date',
        'End Date', 'Location Name', 'Latitude', 'Longitude', 'Rating'
    ]
    sheet.append(columns)

    for event in queryset.select_related('location'):
        sheet.append([
            event.title,
            event.description,
            event.pub_date.replace(tzinfo=None) if event.pub_date else '',
            event.start_date.replace(tzinfo=None) if event.start_date else '',
            event.end_date.replace(tzinfo=None) if event.end_date else '',
            event.location.name,
            event.location.latitude,
            event.location.longitude,
            event.rating
        ])

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output

def import_events_from_xlsx(file_obj, user):
    workbook = openpyxl.load_workbook(file_obj)
    sheet = workbook.active
    events_created = 0

    with transaction.atomic():
        for row in sheet.iter_rows(min_row=2, values_only=True):
            title, desc, pub_d, start_d, end_d, loc_name, lat, lon, rating = row

            location, _ = Location.objects.get_or_create(
                name=loc_name,
                defaults={'latitude': lat, 'longitude': lon}
            )

            Event.objects.create(
                title=title,
                description=desc,
                pub_date=pub_d or timezone.now(),
                start_date=start_d or timezone.now(),
                end_date=end_d or timezone.now(),
                location=location,
                author=user,
                rating=rating or 0,
                status='draft'
            )
            events_created += 1

            location_id = location.id
            transaction.on_commit(
                lambda: update_single_location_weather.delay(location_id)
            )

        return events_created
