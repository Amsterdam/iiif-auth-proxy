from opencensus.ext.azure.log_exporter import AzureLogHandler

from main.settings import APP_NAME


class AzureLogHandlerWithAppName(AzureLogHandler):
    def callback_function(self, envelope):
        envelope.data.baseData.properties["Application name"] = APP_NAME
        envelope.tags["ai.cloud.role"] = (
            f"{APP_NAME} - {envelope.tags['ai.cloud.role']}"
        )
        return True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_telemetry_processor(self.callback_function)
