import logging

from django.core.management.base import BaseCommand

from iiif.queue_zip_consumer import AzureZipQueueConsumer

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Start zip consumer to process zip requests"

    def handle(self, *args, **options):
        log.info("Zip Consumer started")

        consumer = AzureZipQueueConsumer()
        consumer.run()
