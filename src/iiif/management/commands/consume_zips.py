import logging

from django.core.management.base import BaseCommand

from iiif.queue_zip_consumer import AzureZipQueueConsumer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Start zip consumer to process zip requests"

    def handle(self, *args, **options):
        logger.info("Zip Consumer started")

        try:
            consumer = AzureZipQueueConsumer()
            consumer.run()
        except Exception as e:
            logger.exception(e)
