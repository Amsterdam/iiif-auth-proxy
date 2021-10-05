from django.core.management.base import BaseCommand

from iiif.object_store import remove_old_zips_from_object_store


class Command(BaseCommand):
    help = "Removes zips that have expired from the object store."

    def handle(self, *args, **options):
        remove_old_zips_from_object_store(logger=self)

    # Added this method so that remove_old_zips_from_object_store() can write to stdout using log.info
    def info(self, log_str):
        self.stdout.write(log_str)
