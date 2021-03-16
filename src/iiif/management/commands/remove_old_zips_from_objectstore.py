from django.core.management.base import BaseCommand

from iiif import tools


class Command(BaseCommand):
    help = "Adds either -1, 0 or 1 to count_in and count_out for privacy reasons."

    def handle(self, *args, **options):
        tools.remove_old_zips_from_object_store()
