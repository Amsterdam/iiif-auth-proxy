from functools import partial

from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.trace_exporter import AzureExporter


def add_app_name_to_telemetry(app_name, envelope):
    envelope.data.baseData.properties["Application name"] = app_name
    envelope.tags["ai.cloud.role"] = f"{app_name} - {envelope.tags['ai.cloud.role']}"
    return True


def create_azure_trace_config(connection_string, app_name):
    exporter = AzureExporter(
        connection_string=connection_string,
        service_name=app_name,
    )
    exporter.add_telemetry_processor(partial(add_app_name_to_telemetry, app_name))
    return {
        "TRACE": {
            "SAMPLER": "opencensus.trace.samplers.ProbabilitySampler(rate=1)",
            "EXPORTER": exporter,
        }
    }


class AzureLogHandlerWithAppName(AzureLogHandler):
    app_name = None

    @staticmethod
    def set_app_name(name):
        AzureLogHandlerWithAppName.app_name = name

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.app_name:
            telemetry_callback = partial(add_app_name_to_telemetry, self.app_name)
            self.add_telemetry_processor(telemetry_callback)


def create_azure_log_handler_config(connection_string, app_name):
    AzureLogHandlerWithAppName.set_app_name(app_name)
    return {
        "level": "DEBUG",
        "()": AzureLogHandlerWithAppName,
        "connection_string": connection_string,
        "formatter": "json",
    }
