import logging

from django.core.management.base import BaseCommand
from opentelemetry import trace

from zip_consumer.queue_zip_consumer import AzureZipQueueConsumer

tracer = trace.get_tracer(__name__)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Start zip consumer to process zip requests"

    def handle(self, *args, **options):
        with tracer.start_as_current_span("Import API") as span:
            self._handle(*args, **options)

    def _handle(self, *args, **options) -> None:
        logger.info("Zip Consumer started")

        try:
            consumer = AzureZipQueueConsumer()
            consumer.run()
        except Exception as e:
            logger.exception(e)
